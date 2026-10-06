"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { formatDateTime, formatPercent, formatSigned, humanize } from "../lib/format";
import { LabelBadge, SentimentBadge } from "./Badges";
import { QueryState } from "./QueryState";

/** Side panel with every signal the pipeline produced for one review. */
export function ReviewDrawer({ reviewId, onClose }: { reviewId: string; onClose: () => void }) {
  const reviewQuery = useQuery({ queryKey: ["review", reviewId], queryFn: () => api.review(reviewId) });
  const review = reviewQuery.data;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Review detail" onClick={(event) => event.stopPropagation()}>
        <div className="spread">
          <h2 className="panel-title">{reviewId}</h2>
          <button type="button" className="button" onClick={onClose}>Close</button>
        </div>
        <QueryState isPending={reviewQuery.isPending} error={reviewQuery.error} />
        {review && (
          <>
            <p className="review-text">{review.text}</p>
            <div className="row">
              <SentimentBadge sentiment={review.sentiment_label} score={review.sentiment_score} />
              <LabelBadge label={review.emotion} score={review.emotion_score} />
              <LabelBadge label={review.intent} score={review.intent_score} />
            </div>
            <section>
              <h3 className="section-heading small" style={{ marginBottom: 6 }}>Aspect sentiment</h3>
              {review.aspects.length === 0 ? (
                <p className="muted small">No taxonomy aspect mentioned.</p>
              ) : (
                <ul className="stack" style={{ gap: 8 }}>
                  {review.aspects.map((aspect) => (
                    <li key={aspect.aspect}>
                      <div className="row">
                        <strong className="small">{aspect.name}</strong>
                        <SentimentBadge sentiment={aspect.sentiment} score={aspect.score} />
                      </div>
                      <p className="muted small">“{aspect.evidence}”</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <dl className="kv">
              <dt>Polarity</dt><dd className="num">{formatSigned(review.sentiment_polarity)} (P(pos) − P(neg))</dd>
              <dt>Probabilities</dt>
              <dd className="num">
                {Object.entries(review.sentiment_probabilities).map(([label, p]) => `${label} ${formatPercent(p, 0)}`).join(" · ")}
              </dd>
              <dt>Rating</dt><dd>{review.rating ?? "—"}</dd>
              <dt>Product</dt><dd>{review.product}</dd>
              <dt>Channel</dt><dd>{humanize(review.channel)}</dd>
              <dt>Location</dt><dd>{review.city}, {review.country}</dd>
              <dt>Received</dt><dd>{formatDateTime(review.timestamp)}</dd>
              <dt>Source</dt><dd>{humanize(review.source)}</dd>
              <dt>Entities</dt><dd>{review.entities.map((entity) => entity.value).join(", ") || "—"}</dd>
              <dt>Model</dt><dd>{review.model_version}</dd>
            </dl>
            {review.source_labels && (
              <section className="note">
                <strong className="small">Labels shipped with the dataset pack</strong>
                <p className="small">
                  {Object.entries(review.source_labels).map(([key, value]) => `${humanize(key)}: ${humanize(value)}`).join(" · ")}
                </p>
                <p className="tiny muted">
                  Shown for comparison only. The pack’s emotion and intent labels vary for identical texts, so they are not ground truth.
                </p>
              </section>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
