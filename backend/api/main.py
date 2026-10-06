"""PulseIQ Customer Pulse API: single-text inference, analytics, alerts and a live event stream.

Run with: uvicorn api.main:app --reload --port 8006 (Swagger UI at /docs).

Inference (POST /api/v1/analyze, /batch) is kept apart from analytical queries
(GET /api/v1/metrics/*, /trends, /alerts, /issues), as the guide's Phase 5 asks. Every model
response carries model_version so the frontend and logs know which model produced it.
"""
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import config
from src.analytics import (
    FeedbackStore, Filters, compute_alerts, discover_themes, filter_options, issue_detail,
    metrics_distribution, metrics_sentiment, metrics_topics, review_detail, search_feedback, trends,
)
from src.analyzer import PulseAnalyzer
from src.data import load_stream_events, read_jsonl
from src.pipeline import load_processed
from src.preprocess import split_clauses
from src.stream import StreamProcessor
from src.taxonomy import ASPECT_KEYS, detect_aspects


class AppState:
    """Everything the endpoints share. Built at start-up (and rebuilt by /stream/reset)."""

    analyzer: PulseAnalyzer
    store: FeedbackStore
    stream: StreamProcessor
    stream_events: list
    replay_position: int = 0
    replay_thread: Optional[threading.Thread] = None
    replay_stop: threading.Event


state = AppState()


def load_analyzer() -> PulseAnalyzer:
    if not (config.ARTIFACT_DIR / "sentiment.joblib").exists():
        from src.train import train
        train()
    return PulseAnalyzer.load(config.ARTIFACT_DIR)


def build_state() -> None:
    """Load the model, the processed batch and any live events received earlier."""
    state.analyzer = getattr(state, "analyzer", None) or load_analyzer()
    live_records = read_jsonl(config.LIVE_PROCESSED_PATH)
    state.store = FeedbackStore(load_processed() + live_records)
    state.stream = StreamProcessor(state.analyzer, state.store)
    state.stream.start()
    state.stream_events = load_stream_events().to_dict("records")
    state.replay_position = sum(1 for record in live_records if record["source"] == "stream")
    state.replay_thread = None
    state.replay_stop = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    build_state()
    yield
    state.replay_stop.set()
    state.stream.stop()


app = FastAPI(title="PulseIQ Customer Pulse API", version="1.0.0", lifespan=lifespan)

# Let the Next.js frontend call this API from the browser. Always allowed: any localhost / 127.0.0.1
# port (local testing) and any https://*.vercel.app URL (Vercel production and preview deployments).
# Other deployed frontends (e.g. a custom domain) go in CORS_ORIGINS, comma-separated.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/") for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?|https://[a-z0-9-]+\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------------------------
# Observability: per-route request count, error count and latency (guide section 18: API metrics)
# ---------------------------------------------------------------------------------------------

route_stats = defaultdict(lambda: {"requests": 0, "errors": 0, "latencies": deque(maxlen=500)})


@app.middleware("http")
async def record_latency(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    if route is not None:
        stats = route_stats[f"{request.method} {route.path}"]
        stats["requests"] += 1
        stats["errors"] += response.status_code >= 500
        stats["latencies"].append((time.perf_counter() - started) * 1000)
    return response


def ops_summary() -> list:
    rows = []
    for route, stats in sorted(route_stats.items()):
        latencies = np.array(stats["latencies"]) if stats["latencies"] else np.array([0.0])
        rows.append({
            "route": route, "requests": stats["requests"], "errors": stats["errors"],
            "p50_ms": round(float(np.percentile(latencies, 50)), 1),
            "p95_ms": round(float(np.percentile(latencies, 95)), 1),
        })
    return rows


# Simple per-client rate limit for the write/inference endpoints (the API is public in a demo).
RATE_LIMIT_PER_MINUTE = 120
_request_log = defaultdict(deque)


def rate_limited(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.time()
    log = _request_log[client]
    while log and now - log[0] > 60:
        log.popleft()
    if len(log) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Too many requests, please slow down")
    log.append(now)


# ---------------------------------------------------------------------------------------------
# Shared query parameters
# ---------------------------------------------------------------------------------------------

def filters_dependency(
    days: Optional[int] = Query(default=30, ge=1, le=1000, description="Period length; omit with all=true"),
    all: bool = Query(default=False, description="Use the whole date range instead of `days`"),
    product: str = "", channel: str = "", country: str = "", city: str = "",
) -> Filters:
    return Filters(product=product or None, channel=channel or None, country=country or None,
                   city=city or None, days=None if all else days)


def nested_view(output: dict, review_id: str, text: str) -> dict:
    """The guide's API response shape, built from the flat output schema."""
    return {
        "review_id": review_id,
        "text": text,
        "sentiment": {"label": output["sentiment_label"], "score": output["sentiment_score"],
                      "polarity": output["sentiment_polarity"],
                      "probabilities": output["sentiment_probabilities"]},
        "emotion": {"label": output["emotion"], "score": output["emotion_score"]},
        "intent": {"label": output["intent"], "score": output["intent_score"]},
        "topics": output["topics"],
        "aspects": output["aspects"],
        "entities": output["entities"],
        "clauses": [{"text": clause, "aspects": detect_aspects(clause)} for clause in split_clauses(text)],
        "model_version": output["model_version"],
        "processed_at": output["processed_at"],
    }


# ---------------------------------------------------------------------------------------------
# Health, model and data
# ---------------------------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "model_version": state.analyzer.model_version}


@app.get("/api/v1/model")
def model_info():
    """Model metadata, evaluation results (artifacts/metrics.json) and live API metrics."""
    metadata = json.loads((config.ARTIFACT_DIR / "model_metadata.json").read_text())
    metrics = json.loads((config.ARTIFACT_DIR / "metrics.json").read_text())
    return {**metadata, "metrics": metrics, "api": ops_summary()}


@app.get("/api/v1/quality")
def quality():
    """Data-quality report written by the batch pipeline."""
    if not config.QUALITY_REPORT_PATH.exists():
        raise HTTPException(404, "Run python -m src.pipeline first")
    return json.loads(config.QUALITY_REPORT_PATH.read_text())


@app.get("/api/v1/filters")
def filters():
    return filter_options(state.store)


# ---------------------------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------------------------

class AnalyzeIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    review_id: Optional[str] = Field(default=None, max_length=64)


@app.post("/api/v1/analyze", dependencies=[Depends(rate_limited)])
def analyze(body: AnalyzeIn):
    """One text -> sentiment, emotion, intent, topics, aspect sentiment and entities."""
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Text is empty")
    review_id = body.review_id or f"adhoc_{uuid.uuid4().hex[:10]}"
    return nested_view(state.analyzer.analyze(text), review_id, text)


class BatchIn(BaseModel):
    reviews: List[AnalyzeIn] = Field(min_length=1, max_length=500)


@app.post("/api/v1/batch", dependencies=[Depends(rate_limited)])
def batch(body: BatchIn):
    """Analyze up to 500 uploaded texts at once and summarise them (nothing is stored)."""
    texts = [review.text.strip() for review in body.reviews]
    outputs = state.analyzer.analyze_texts(texts)
    results = [
        nested_view(output, review.review_id or f"batch_{index + 1:04d}", text)
        for index, (review, text, output) in enumerate(zip(body.reviews, texts, outputs))
    ]
    sentiment_counts = {label: 0 for label in config.SENTIMENT_LABELS}
    aspect_counts = {aspect: {"mentions": 0, "negative": 0} for aspect in ASPECT_KEYS}
    for output in outputs:
        sentiment_counts[output["sentiment_label"]] += 1
        for aspect in output["aspects"]:
            aspect_counts[aspect["aspect"]]["mentions"] += 1
            aspect_counts[aspect["aspect"]]["negative"] += aspect["sentiment"] == "negative"
    return {
        "count": len(results),
        "model_version": state.analyzer.model_version,
        "summary": {
            "sentiment": sentiment_counts,
            "aspects": [{"aspect": key, **counts} for key, counts in aspect_counts.items() if counts["mentions"]],
        },
        "results": results,
    }


# ---------------------------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------------------------

@app.get("/api/v1/metrics/sentiment")
def sentiment_metrics(filters: Filters = Depends(filters_dependency)):
    return metrics_sentiment(state.store, filters)


@app.get("/api/v1/metrics/topics")
def topic_metrics(filters: Filters = Depends(filters_dependency)):
    return metrics_topics(state.store, filters)


@app.get("/api/v1/metrics/emotions")
def emotion_metrics(filters: Filters = Depends(filters_dependency)):
    return metrics_distribution(state.store, filters, "emotion")


@app.get("/api/v1/metrics/intents")
def intent_metrics(filters: Filters = Depends(filters_dependency)):
    return metrics_distribution(state.store, filters, "intent")


@app.get("/api/v1/trends")
def trend_series(
    filters: Filters = Depends(filters_dependency),
    granularity: str = Query(default="day", pattern="^(day|week)$"),
    aspect: str = "",
):
    if aspect and aspect not in ASPECT_KEYS:
        raise HTTPException(404, "Unknown aspect")
    return trends(state.store, filters, granularity, aspect or None)


@app.get("/api/v1/alerts")
def alerts(filters: Filters = Depends(filters_dependency)):
    """Current 7 days vs the previous 28 (the `days` filter does not apply; segment filters do)."""
    return compute_alerts(state.store, filters)


@app.get("/api/v1/issues/{aspect}")
def issue(aspect: str, filters: Filters = Depends(filters_dependency)):
    if aspect not in ASPECT_KEYS:
        raise HTTPException(404, "Unknown aspect")
    return issue_detail(state.store, aspect, filters)


@app.get("/api/v1/themes")
def themes(filters: Filters = Depends(filters_dependency)):
    return discover_themes(state.store, filters)


# ---------------------------------------------------------------------------------------------
# Feedback explorer and live ingestion
# ---------------------------------------------------------------------------------------------

@app.get("/api/v1/feedback")
def feedback(
    filters: Filters = Depends(filters_dependency),
    search: str = "", sentiment: str = "", aspect: str = "", emotion: str = "", intent: str = "",
    source: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return search_feedback(state.store, filters, search, sentiment, aspect, emotion, intent, source, page, page_size)


@app.get("/api/v1/feedback/{review_id}")
def feedback_detail(review_id: str):
    review = review_detail(state.store, review_id)
    if review is None:
        raise HTTPException(404, "Unknown review_id")
    return review


class FeedbackIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    product: Optional[str] = Field(default=None, max_length=60)
    channel: Optional[str] = Field(default="web", max_length=30)
    country: Optional[str] = Field(default=None, max_length=60)
    city: Optional[str] = Field(default=None, max_length=60)
    customer_id: Optional[str] = Field(default=None, max_length=40)


def live_timestamp() -> tuple:
    """Now, unless the data is far behind the wall clock (an old demo dataset): then one minute after
    the latest review, so new feedback still lands in the current alert window."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    latest = state.store.reviews.moment.max().to_pydatetime().replace(tzinfo=timezone.utc)
    if latest <= now <= latest + timedelta(days=14):
        return now.strftime("%Y-%m-%dT%H:%M:%SZ"), "real"
    return (latest + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "simulated"


@app.post("/api/v1/feedback", status_code=202, dependencies=[Depends(rate_limited)])
def submit_feedback(body: FeedbackIn):
    """Accept new feedback as an event; it is analyzed asynchronously by the stream consumer."""
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Text is empty")
    timestamp, clock = live_timestamp()
    review = {
        "review_id": f"rv_live_{uuid.uuid4().hex[:8]}", "customer_id": body.customer_id,
        "timestamp": timestamp, "text": text, "rating": body.rating, "product": body.product,
        "channel": body.channel, "country": body.country, "city": body.city, "language": "en",
    }
    trace = state.stream.publish(review, source="live")
    return {"accepted": True, "clock": clock, "trace": trace}


@app.get("/api/v1/stream/status")
def stream_status():
    """Polled by the dashboard: when `version` changes, it refetches its metrics."""
    return {
        "version": state.store.version,
        "processed": state.stream.processed_count,
        "failed": state.stream.failed_count,
        "queue_depth": state.stream.queue_depth(),
        "replay": {
            "position": state.replay_position,
            "total": len(state.stream_events),
            "running": bool(state.replay_thread and state.replay_thread.is_alive()),
        },
    }


@app.get("/api/v1/stream/recent")
def stream_recent(limit: int = Query(default=20, ge=1, le=100)):
    return {"events": state.stream.recent(limit)}


class ReplayIn(BaseModel):
    count: int = Field(default=100, ge=1, le=1000)
    interval_ms: int = Field(default=150, ge=0, le=5000)


def _replay(count: int, interval_ms: int, stop: threading.Event) -> None:
    for _ in range(count):
        if stop.is_set() or state.replay_position >= len(state.stream_events):
            return
        event = state.stream_events[state.replay_position]
        state.replay_position += 1
        review = {
            "event_id": event["event_id"], "review_id": event["entity_id"], "customer_id": None,
            "timestamp": event["event_time"] + "Z", "text": event["text"], "rating": None,
            "product": event["product"], "channel": event["channel"], "country": None, "city": None,
            "language": "en",
        }
        state.stream.publish(review, source="stream")
        if interval_ms:
            time.sleep(interval_ms / 1000)


@app.post("/api/v1/stream/replay")
def stream_replay(body: ReplayIn):
    """Replay the next `count` events of streaming_feedback_events.csv, one every `interval_ms`."""
    if state.replay_thread and state.replay_thread.is_alive():
        raise HTTPException(409, "A replay is already running")
    if state.replay_position >= len(state.stream_events):
        raise HTTPException(409, "All stream events have been replayed; reset to start again")
    state.replay_stop = threading.Event()
    state.replay_thread = threading.Thread(
        target=_replay, args=(body.count, body.interval_ms, state.replay_stop), daemon=True)
    state.replay_thread.start()
    return stream_status()


@app.post("/api/v1/stream/stop")
def stream_stop():
    state.replay_stop.set()
    return stream_status()


@app.post("/api/v1/stream/reset")
def stream_reset():
    """Forget every live and replayed event and go back to the batch data."""
    state.replay_stop.set()
    if state.replay_thread:
        state.replay_thread.join(timeout=5)
    state.stream.wait_until_idle()
    state.stream.stop()
    for path in (config.LIVE_RAW_PATH, config.LIVE_PROCESSED_PATH):
        path.unlink(missing_ok=True)
    build_state()
    return stream_status()
