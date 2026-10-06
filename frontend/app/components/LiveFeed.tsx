"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { formatDateTime, humanize } from "../lib/format";
import { SentimentBadge } from "./Badges";

/**
 * The streaming demo (guide Phase 8): replay the dataset pack's event file into the pipeline and
 * watch each event go received -> analyzed -> stored, while the dashboard above refreshes.
 */
export function LiveFeed() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({ queryKey: ["stream-status"], queryFn: api.streamStatus, retry: false });
  const recentQuery = useQuery({
    queryKey: ["stream-recent"],
    queryFn: () => api.streamRecent(8),
    refetchInterval: statusQuery.data?.replay.running || statusQuery.data?.queue_depth ? 1500 : 5000,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["stream-status"] });
  const replay = useMutation({ mutationFn: () => api.streamReplay(200, 120), onSettled: refresh });
  const stop = useMutation({ mutationFn: api.streamStop, onSettled: refresh });
  const reset = useMutation({
    mutationFn: api.streamReset,
    onSettled: () => queryClient.invalidateQueries(),
  });
  const status = statusQuery.data;
  const running = status?.replay.running ?? false;
  const exhausted = status ? status.replay.position >= status.replay.total : false;
  const error = replay.error ?? reset.error ?? stop.error;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Live event stream</h2>
          <p className="panel-subtitle">
            {status
              ? `${status.replay.position} of ${status.replay.total} stream events replayed · ${status.processed} processed · queue ${status.queue_depth}`
              : "Connecting…"}
          </p>
        </div>
        {running && <span className="live-dot" aria-label="Streaming" />}
      </div>
      <div className="row" style={{ marginBottom: 10 }}>
        {running ? (
          <button type="button" className="button" onClick={() => stop.mutate()}>Pause</button>
        ) : (
          <button type="button" className="button button-primary" disabled={exhausted || replay.isPending} onClick={() => replay.mutate()}>
            Replay next 200 events
          </button>
        )}
        <button type="button" className="button" disabled={reset.isPending || (!status?.processed && !status?.replay.position)} onClick={() => reset.mutate()}>
          Reset
        </button>
      </div>
      {error && <p className="error-text small">{error.message}</p>}
      <p className="pipeline-steps" aria-label="Pipeline">
        <span>event</span><span>raw log</span><span>queue</span><span>NLP</span><span>processed store</span><span>dashboard</span>
      </p>
      {recentQuery.data?.events.length ? (
        <ul>
          {recentQuery.data.events.map((event) => (
            <li key={event.event_id} className="feed-item">
              <div className="spread">
                <span className="muted tiny">
                  {humanize(event.source)} · {event.product ?? "—"} · {formatDateTime(event.received_at)}
                </span>
                <span className="tiny num muted">
                  {event.status === "processed" && event.latency_ms !== null
                    ? `${event.latency_ms >= 1000 ? `${(event.latency_ms / 1000).toFixed(1)} s` : `${Math.round(event.latency_ms)} ms`} end-to-end`
                    : humanize(event.status)}
                </span>
              </div>
              <span className="small">{event.text}</span>
              {event.sentiment && (
                <div className="row">
                  <SentimentBadge sentiment={event.sentiment} />
                  {event.aspects.map((aspect) => (
                    <span key={aspect.aspect} className="badge">{humanize(aspect.aspect)}: {aspect.sentiment}</span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty">No live events yet. Replay the stream, or submit feedback from Analyze text.</p>
      )}
    </section>
  );
}
