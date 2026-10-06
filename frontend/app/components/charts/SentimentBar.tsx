import { formatPercent } from "../../lib/format";

/** A 100% bar of negative / neutral / positive with 2px gaps; values live in the title tooltip. */
export function SentimentBar({ negative, neutral, positive }: { negative: number; neutral: number; positive: number }) {
  const total = negative + neutral + positive;
  if (!total) return <span className="muted tiny">No mentions</span>;
  const parts = [
    { key: "negative", value: negative, color: "var(--negative)" },
    { key: "neutral", value: neutral, color: "var(--neutral)" },
    { key: "positive", value: positive, color: "var(--positive)" },
  ].filter((part) => part.value > 0);
  return (
    <span
      className="sentiment-bar"
      role="img"
      aria-label={parts.map((part) => `${part.key} ${formatPercent(part.value / total, 0)}`).join(", ")}
      title={parts.map((part) => `${part.key}: ${part.value} (${formatPercent(part.value / total, 0)})`).join("\n")}
    >
      {parts.map((part) => (
        <span key={part.key} style={{ width: `${(part.value / total) * 100}%`, background: part.color }} />
      ))}
    </span>
  );
}
