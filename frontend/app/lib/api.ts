/**
 * Typed client for the PulseIQ Customer Pulse FastAPI backend. Types mirror api/main.py and
 * src/analytics.py.
 */

/** Backend base URL; set NEXT_PUBLIC_API_URL in .env.local (inlined into the browser bundle at build). */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8006";

export type Sentiment = "negative" | "neutral" | "positive";

export type AspectSentiment = {
  aspect: string;
  name: string;
  sentiment: Sentiment;
  score: number;
  polarity: number;
  evidence: string;
};

export type Entity = { type: "product" | "location"; value: string };

/** POST /api/v1/analyze: the guide's nested response shape. */
export type Analysis = {
  review_id: string;
  text: string;
  sentiment: { label: Sentiment; score: number; polarity: number; probabilities: Record<Sentiment, number> };
  emotion: { label: string; score: number };
  intent: { label: string; score: number };
  topics: string[];
  aspects: AspectSentiment[];
  entities: Entity[];
  clauses: { text: string; aspects: string[] }[];
  model_version: string;
  processed_at: string;
};

export type BatchResponse = {
  count: number;
  model_version: string;
  summary: {
    sentiment: Record<Sentiment, number>;
    aspects: { aspect: string; mentions: number; negative: number }[];
  };
  results: Analysis[];
};

/** A processed review (flat output schema + review contract). */
export type Review = {
  review_id: string;
  customer_id: string | null;
  timestamp: string;
  text: string;
  rating: number | null;
  product: string;
  channel: string;
  country: string;
  city: string;
  language: string;
  sentiment_label: Sentiment;
  sentiment_score: number;
  sentiment_polarity: number;
  sentiment_probabilities: Record<Sentiment, number>;
  emotion: string;
  emotion_score: number;
  intent: string;
  intent_score: number;
  topics: string[];
  aspects: AspectSentiment[];
  entities: Entity[];
  model_version: string;
  processed_at: string;
  source: "batch" | "stream" | "live";
  source_labels: Record<string, string> | null;
};

export type Period = { start: string; end: string; days: number | null };

export type SentimentStats = {
  reviews: number;
  negative: number;
  neutral: number;
  positive: number;
  negative_rate: number | null;
  positive_rate: number | null;
  avg_polarity: number | null;
};

export type SentimentMetrics = {
  as_of: string;
  period: Period;
  current: SentimentStats;
  previous: SentimentStats | null;
};

export type TopicRow = {
  aspect: string;
  name: string;
  mentions: number;
  negative: number;
  neutral: number;
  positive: number;
  negative_rate: number | null;
  net_sentiment: number | null;
  share_of_reviews: number | null;
  previous_negative_rate: number | null;
  negative_rate_change: number | null;
};

export type TopicMetrics = { as_of: string; period: Period; topics: TopicRow[] };

export type DistributionItem = { label: string; count: number; share: number | null; previous_share: number | null };
export type DistributionMetrics = { as_of: string; period: Period; items: DistributionItem[] };

export type TrendPoint = {
  period: string;
  reviews: number;
  negative: number;
  neutral: number;
  positive: number;
  negative_rate: number | null;
  positive_rate: number | null;
  avg_polarity: number | null;
  aspect_mentions?: number;
  aspect_negative_rate?: number | null;
};

export type Trends = {
  as_of: string;
  period: Period;
  granularity: "day" | "week";
  aspect: string | null;
  points: TrendPoint[];
};

export type Driver = {
  dimension: string;
  value: string;
  share_of_negatives: number;
  baseline_share_of_negatives: number;
  lift: number;
  negative_mentions: number;
};

export type Alert = {
  id: string;
  scope: string;
  name: string;
  kind: "deterioration" | "improvement";
  severity: "critical" | "high" | "medium" | "info";
  headline: string;
  current: { mentions: number; negative: number; negative_rate: number };
  baseline: { mentions: number; negative: number; negative_rate: number };
  point_change: number;
  relative_change: number | null;
  z_score: number;
  drivers: Driver[];
  action: string | null;
};

export type AlertsResponse = {
  as_of: string;
  current_window: [string, string];
  baseline_window: [string, string];
  rules: { min_mentions: number; min_point_change: number; min_relative_change: number; min_z: number };
  alerts: Alert[];
};

export type SegmentRow = {
  value: string;
  mentions: number;
  negative: number;
  negative_rate: number | null;
  baseline_negative_rate: number | null;
};

export type IssueDetail = {
  aspect: string;
  name: string;
  as_of: string;
  current_window: [string, string];
  baseline_window: [string, string];
  current: { mentions: number; negative: number; negative_rate: number | null };
  baseline: { mentions: number; negative_rate: number | null };
  alert: Alert | null;
  trend: { period: string; mentions: number; negative: number; negative_rate_7d: number | null }[];
  segments: Record<"product" | "channel" | "country" | "city", SegmentRow[]>;
  emotions: Record<string, number>;
  intents: Record<string, number>;
  evidence: {
    review_id: string;
    date: string;
    evidence: string;
    text: string;
    product: string;
    channel: string;
    city: string;
    confidence: number;
  }[];
  findings: string[];
  recommended_action: string;
};

export type FeedbackPage = { total: number; page: number; page_size: number; items: Review[] };

export type Themes = {
  as_of: string;
  period: Period;
  reviews: number;
  themes: { terms: string[]; reviews: number; outside_taxonomy_share: number; examples: string[] }[];
};

export type FilterOptions = {
  product: string[];
  channel: string[];
  country: string[];
  city: string[];
  aspects: { key: string; name: string }[];
  sentiments: Sentiment[];
  emotions: string[];
  intents: string[];
  date_range: [string, string];
};

export type StreamTrace = {
  event_id: string;
  review_id: string;
  source: "live" | "stream";
  text: string;
  product: string | null;
  status: "queued" | "processed" | "failed";
  received_at: string;
  processed_at: string | null;
  latency_ms: number | null;
  sentiment: Sentiment | null;
  aspects: { aspect: string; sentiment: Sentiment }[];
};

export type StreamStatus = {
  version: number;
  processed: number;
  failed: number;
  queue_depth: number;
  replay: { position: number; total: number; running: boolean };
};

export type ClassReport = {
  accuracy: number;
  macro_precision: number;
  macro_recall: number;
  macro_f1: number;
  weighted_f1: number;
  support: number;
  per_class: Record<string, { precision: number; recall: number; f1: number; support: number }>;
  confusion_matrix: { labels: string[]; matrix: number[][] };
};

export type ModelKey = "baseline_tfidf_unigram_lr" | "final_tfidf_word_char_lr";

export type TaskReport = {
  labels: string[];
  selected_model: ModelKey;
  validation_macro_f1: Record<ModelKey, number>;
  selected_C: number;
  validation_macro_f1_by_C: Record<string, number>;
  test: Record<string, ClassReport>;
};

export type AspectScores = {
  detection: { precision: number; recall: number; f1: number; support: number };
  per_aspect: Record<string, { precision: number; recall: number; f1: number; support: number }>;
  sentiment_accuracy: number | null;
  sentiment_evaluated: number;
};

export type ChallengeRow = {
  text: string;
  category: string;
  sentiment: { expected: string; predicted: string };
  emotion: { expected: string; predicted: string };
  intent: { expected: string; predicted: string };
  aspects: {
    expected: { aspect: string; sentiment: string }[];
    predicted: { aspect: string; sentiment: string }[];
  };
};

export type Metrics = {
  model_version: string;
  trained_at: string;
  data: { source: string; unique_reviews: number; train: number; validation: number; test: number;
    sentiment_distribution: Record<string, number> };
  sentiment: TaskReport & {
    challenge_set: Record<ModelKey, { accuracy: number; by_category: Record<string, number> }>;
    error_analysis: {
      by_tag: Record<string, { reviews: number; error_rate: number }>;
      sample_errors: { text: string; rating: number; expected: string; predicted: string; tags: string[] }[];
    };
  };
  emotion: TaskReport;
  intent: TaskReport;
  aspects: { test: AspectScores };
  challenge_set: {
    size: number;
    sentiment_accuracy: number;
    emotion_accuracy: number;
    intent_accuracy: number;
    aspects: AspectScores;
    by_category: Record<string, { size: number; sentiment_accuracy: number }>;
    rows: ChallengeRow[];
  };
  dataset_pack: {
    rows: number;
    unique_texts: number;
    sentiment_unique_texts: ClassReport;
    emotion_agreement: number;
    emotion_label_ceiling: number;
    intent_agreement: number;
    intent_label_ceiling: number;
    primary_aspect_detected: number;
    absa_sample: AspectScores & { unique_texts: number };
  };
};

export type ModelInfo = {
  model_version: string;
  trained_at: string;
  models: Record<string, { selected: ModelKey; type: string; C: number; classes: string[] }>;
  aspect_method: string;
  training_reviews: number;
  metrics: Metrics;
  api: { route: string; requests: number; errors: number; p50_ms: number; p95_ms: number }[];
};

export type QualityReport = {
  source: string;
  rows: number;
  date_range: [string, string];
  checks: { check: string; status: "pass" | "warn" | "fail"; detail: string }[];
  processed_at: string;
  processed_rows: number;
  unique_texts_analyzed: number;
  model_version: string;
};

export type FeedbackSubmission = {
  text: string;
  rating?: number;
  product?: string;
  channel?: string;
  country?: string;
  city?: string;
};

/** Error carrying the HTTP status and FastAPI's `detail` message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/**
 * fetch() wrapper: prefixes the base URL, sends JSON, and turns network failures and non-2xx
 * responses into ApiError so TanStack Query exposes them as `error`.
 */
async function requestJson<ResponseBody>(path: string, requestOptions?: RequestInit): Promise<ResponseBody> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...requestOptions,
      headers: { "Content-Type": "application/json", ...requestOptions?.headers },
    });
  } catch {
    // fetch only rejects on network errors (server down, CORS), never on HTTP status codes.
    throw new ApiError(`Can't reach the API at ${API_BASE_URL}. Is uvicorn running?`, 0);
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail = errorBody?.detail;
    const errorMessage =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail[0]?.msg
          ? String(detail[0].msg)
          : `Request failed (${response.status})`;
    throw new ApiError(errorMessage, response.status);
  }
  return response.json();
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

/** One function per backend endpoint, used as queryFn / mutationFn in the components. */
export const api = {
  health: () => requestJson<{ status: string; model_version: string }>("/health"),
  filters: () => requestJson<FilterOptions>("/api/v1/filters"),
  model: () => requestJson<ModelInfo>("/api/v1/model"),
  quality: () => requestJson<QualityReport>("/api/v1/quality"),

  analyze: (text: string) => requestJson<Analysis>("/api/v1/analyze", post({ text })),
  batch: (texts: string[]) =>
    requestJson<BatchResponse>("/api/v1/batch", post({ reviews: texts.map((text) => ({ text })) })),

  sentiment: (query: string) => requestJson<SentimentMetrics>(`/api/v1/metrics/sentiment?${query}`),
  topics: (query: string) => requestJson<TopicMetrics>(`/api/v1/metrics/topics?${query}`),
  emotions: (query: string) => requestJson<DistributionMetrics>(`/api/v1/metrics/emotions?${query}`),
  intents: (query: string) => requestJson<DistributionMetrics>(`/api/v1/metrics/intents?${query}`),
  trends: (query: string, granularity: "day" | "week", aspect = "") =>
    requestJson<Trends>(`/api/v1/trends?${query}&granularity=${granularity}&aspect=${encodeURIComponent(aspect)}`),
  alerts: (query: string) => requestJson<AlertsResponse>(`/api/v1/alerts?${query}`),
  issue: (aspect: string, query: string) =>
    requestJson<IssueDetail>(`/api/v1/issues/${encodeURIComponent(aspect)}?${query}`),
  themes: (query: string) => requestJson<Themes>(`/api/v1/themes?${query}`),

  feedback: (query: string) => requestJson<FeedbackPage>(`/api/v1/feedback?${query}`),
  review: (reviewId: string) => requestJson<Review>(`/api/v1/feedback/${encodeURIComponent(reviewId)}`),
  submitFeedback: (submission: FeedbackSubmission) =>
    requestJson<{ accepted: boolean; clock: "real" | "simulated"; trace: StreamTrace }>(
      "/api/v1/feedback",
      post(submission),
    ),

  streamStatus: () => requestJson<StreamStatus>("/api/v1/stream/status"),
  streamRecent: (limit = 12) => requestJson<{ events: StreamTrace[] }>(`/api/v1/stream/recent?limit=${limit}`),
  streamReplay: (count: number, intervalMs: number) =>
    requestJson<StreamStatus>("/api/v1/stream/replay", post({ count, interval_ms: intervalMs })),
  streamStop: () => requestJson<StreamStatus>("/api/v1/stream/stop", { method: "POST" }),
  streamReset: () => requestJson<StreamStatus>("/api/v1/stream/reset", { method: "POST" }),
};
