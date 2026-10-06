"""Event-driven processing (guide Phase 8), local version of Kinesis -> consumer -> store.

    POST /api/v1/feedback or a stream replay
      -> raw event appended to raw/live/events.jsonl (raw first: nothing is lost if analysis fails)
      -> queue (stands in for Kinesis)
      -> consumer thread: NLP inference -> processed/live_enriched.jsonl -> in-memory store
      -> the dashboard sees a new data version and refetches

Every event leaves a trace (received, processed, latency) so the UI can show the pipeline working.
"""
import queue
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from src.analytics import FeedbackStore
from src import config
from src.data import append_jsonl
from src.pipeline import build_record


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StreamProcessor:
    def __init__(self, analyzer, store: FeedbackStore):
        self.analyzer = analyzer
        self.store = store
        self.events: "queue.Queue[Optional[dict]]" = queue.Queue()
        self.traces: deque = deque(maxlen=100)
        self.processed_count = 0
        self.failed_count = 0
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run, name="pulse-stream-consumer", daemon=True)
            self._worker.start()

    def stop(self) -> None:
        if self._worker and self._worker.is_alive():
            self.events.put(None)
            self._worker.join(timeout=5)

    def publish(self, review: dict, source: str) -> dict:
        """Accept one review event: persist it raw, queue it and return its trace."""
        event = {
            "event_id": review.pop("event_id", None) or f"evt_{uuid.uuid4().hex[:12]}",
            "event_type": "feedback.created",
            "source": source,
            "received_at": utc_now(),
            "review": review,
        }
        append_jsonl(config.LIVE_RAW_PATH, event)
        trace = {
            "event_id": event["event_id"],
            "review_id": review["review_id"],
            "source": source,
            "text": review["text"],
            "product": review.get("product"),
            "status": "queued",
            "received_at": event["received_at"],
            "processed_at": None,
            "latency_ms": None,
            "sentiment": None,
            "aspects": [],
            "_started": time.perf_counter(),
        }
        with self._lock:
            self.traces.appendleft(trace)
        self.events.put(event)
        return public_trace(trace)

    def queue_depth(self) -> int:
        return self.events.qsize()

    def recent(self, limit: int = 20) -> list:
        with self._lock:
            return [public_trace(trace) for trace in list(self.traces)[:limit]]

    def wait_until_idle(self, timeout: float = 10.0) -> bool:
        """Block until the queue is drained (used by tests and the replay endpoint's caller)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.events.unfinished_tasks == 0:
                return True
            time.sleep(0.02)
        return False

    def _run(self) -> None:
        while True:
            event = self.events.get()
            if event is None:
                self.events.task_done()
                return
            trace = self._find_trace(event["event_id"])
            try:
                output = self.analyzer.analyze(event["review"]["text"])
                record = build_record(event["review"], output, event["source"])
                append_jsonl(config.LIVE_PROCESSED_PATH, record)
                self.store.append([record])
                with self._lock:
                    self.processed_count += 1
                    if trace:
                        trace.update({
                            "status": "processed",
                            "processed_at": utc_now(),
                            "latency_ms": round((time.perf_counter() - trace["_started"]) * 1000, 1),
                            "sentiment": output["sentiment_label"],
                            "aspects": [{"aspect": a["aspect"], "sentiment": a["sentiment"]} for a in output["aspects"]],
                        })
            except Exception as error:  # keep consuming; the failure is visible in the trace
                with self._lock:
                    self.failed_count += 1
                    if trace:
                        trace.update({"status": "failed", "error": str(error)})
            finally:
                self.events.task_done()

    def _find_trace(self, event_id: str) -> Optional[dict]:
        with self._lock:
            return next((trace for trace in self.traces if trace["event_id"] == event_id), None)


def public_trace(trace: dict) -> dict:
    return {key: value for key, value in trace.items() if not key.startswith("_")}
