"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useFilters } from "../lib/filters";
import { formatCount, formatDay, humanize } from "../lib/format";
import { FilterBar } from "../components/FilterBar";
import { LabelBadge, SentimentBadge } from "../components/Badges";
import { QueryState } from "../components/QueryState";
import { ReviewDrawer } from "../components/ReviewDrawer";

const PAGE_SIZE = 20;

/** Search and inspect individual reviews with every signal attached. */
export default function FeedbackPage() {
  const { query } = useFilters();
  const optionsQuery = useQuery({ queryKey: ["filters-options"], queryFn: api.filters, staleTime: 300_000 });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [signals, setSignals] = useState({ sentiment: "", aspect: "", emotion: "", intent: "", source: "" });
  const [page, setPage] = useState(1);
  const [openReview, setOpenReview] = useState<string | null>(null);

  // Any filter change starts again from the first page.
  useEffect(() => setPage(1), [query, search, signals]);

  const params = new URLSearchParams(query);
  params.set("search", search);
  Object.entries(signals).forEach(([key, value]) => params.set(key, value));
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));
  const feedbackQuery = useQuery({ queryKey: ["feedback", params.toString()], queryFn: () => api.feedback(params.toString()) });
  const data = feedbackQuery.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const options = optionsQuery.data;
  const setSignal = (key: keyof typeof signals, value: string) => setSignals((previous) => ({ ...previous, [key]: value }));

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Feedback explorer</h1>
          <p className="muted small">Search individual reviews and inspect what the models found in each</p>
        </div>
      </header>
      <FilterBar />
      <section className="panel">
        <form
          className="row"
          style={{ marginBottom: 12 }}
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(searchInput);
          }}
        >
          <input
            type="search"
            placeholder="Search text or review id…"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            style={{ minWidth: 240 }}
          />
          <button type="submit" className="button">Search</button>
          <select value={signals.sentiment} onChange={(event) => setSignal("sentiment", event.target.value)} aria-label="Sentiment">
            <option value="">Any sentiment</option>
            {options?.sentiments.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
          <select value={signals.aspect} onChange={(event) => setSignal("aspect", event.target.value)} aria-label="Aspect">
            <option value="">Any aspect</option>
            {options?.aspects.map((value) => <option key={value.key} value={value.key}>{value.name}</option>)}
          </select>
          <select value={signals.emotion} onChange={(event) => setSignal("emotion", event.target.value)} aria-label="Emotion">
            <option value="">Any emotion</option>
            {options?.emotions.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
          <select value={signals.intent} onChange={(event) => setSignal("intent", event.target.value)} aria-label="Intent">
            <option value="">Any intent</option>
            {options?.intents.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
          <select value={signals.source} onChange={(event) => setSignal("source", event.target.value)} aria-label="Source">
            <option value="">Any source</option>
            <option value="batch">Batch (dataset pack)</option>
            <option value="stream">Stream replay</option>
            <option value="live">Live submissions</option>
          </select>
        </form>

        <QueryState isPending={feedbackQuery.isPending} error={feedbackQuery.error} />
        {data && (
          <div className={feedbackQuery.isPlaceholderData ? "loading-dim" : undefined}>
            <p className="muted small" style={{ marginBottom: 4 }}>{formatCount(data.total)} reviews</p>
            {data.items.length === 0 && <p className="empty">No reviews match these filters.</p>}
            <ul className="review-list">
              {data.items.map((review) => (
                <li key={review.review_id}>
                  <button type="button" className="review-item" onClick={() => setOpenReview(review.review_id)}>
                    <span className="review-text">{review.text}</span>
                    <span className="row">
                      <SentimentBadge sentiment={review.sentiment_label} score={review.sentiment_score} />
                      <LabelBadge label={review.emotion} />
                      <LabelBadge label={review.intent} />
                      {review.aspects.map((aspect) => (
                        <span key={aspect.aspect} className="badge">
                          <span className="swatch" style={{ background: `var(--${aspect.sentiment})` }} aria-hidden="true" />
                          {aspect.name}: {aspect.sentiment}
                        </span>
                      ))}
                    </span>
                    <span className="muted tiny">
                      {review.review_id} · {formatDay(review.timestamp, true)} · {review.product} · {humanize(review.channel)} · {review.city}
                      {review.rating ? ` · ${review.rating}★` : ""} · {humanize(review.source)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="spread" style={{ marginTop: 12 }}>
              <button type="button" className="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button>
              <span className="muted small">Page {page} of {formatCount(pages)}</span>
              <button type="button" className="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button>
            </div>
          </div>
        )}
      </section>
      {openReview && <ReviewDrawer reviewId={openReview} onClose={() => setOpenReview(null)} />}
    </>
  );
}
