import type { Alert, Sentiment } from "../lib/api";
import { humanize } from "../lib/format";

const SENTIMENT_COLORS: Record<Sentiment, string> = {
  negative: "var(--negative)",
  neutral: "var(--neutral)",
  positive: "var(--positive)",
};

/** Sentiment label with a colored swatch beside it (the text itself stays in ink). */
export function SentimentBadge({ sentiment, score }: { sentiment: Sentiment; score?: number }) {
  return (
    <span className="badge">
      <span className="swatch" style={{ background: SENTIMENT_COLORS[sentiment] }} aria-hidden="true" />
      {humanize(sentiment)}
      {score !== undefined && <span className="muted">{Math.round(score * 100)}%</span>}
    </span>
  );
}

export function LabelBadge({ label, score }: { label: string; score?: number }) {
  return (
    <span className="badge">
      {humanize(label)}
      {score !== undefined && <span className="muted">{Math.round(score * 100)}%</span>}
    </span>
  );
}

const SEVERITY_ICONS: Record<Alert["severity"], string> = { critical: "▲▲", high: "▲", medium: "△", info: "▼" };

/** Status color always ships with an icon and a label, never color alone. */
export function SeverityBadge({ severity }: { severity: Alert["severity"] }) {
  return (
    <span className={`badge sev-${severity}`}>
      <span aria-hidden="true">{SEVERITY_ICONS[severity]}</span>
      {severity === "info" ? "Improvement" : humanize(severity)}
    </span>
  );
}

export const sentimentColor = (sentiment: Sentiment) => SENTIMENT_COLORS[sentiment];
