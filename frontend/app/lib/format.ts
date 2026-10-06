/** Display helpers shared by the components. */

/** 0.4874 -> "48.7%". */
export function formatPercent(fraction: number | null | undefined, digits = 1): string {
  return fraction === null || fraction === undefined ? "—" : `${(fraction * 100).toFixed(digits)}%`;
}

/** Change in percentage points: 0.081 -> "+8.1 pts". */
export function formatPoints(change: number | null | undefined): string {
  if (change === null || change === undefined) return "—";
  const points = change * 100;
  return `${points > 0 ? "+" : ""}${points.toFixed(1)} pts`;
}

/** Signed score: 0.12 -> "+0.12". */
export function formatSigned(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

const integerFormatter = new Intl.NumberFormat("en-US");
export function formatCount(value: number): string {
  return integerFormatter.format(value);
}

/** "2026-09-03" -> "Sep 3"; with year: "Sep 3, 2026". */
export function formatDay(isoDate: string, withYear = false): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  });
}

export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** "refund_request" -> "Refund request". */
export function humanize(label: string): string {
  const text = label.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const SENTIMENT_ORDER = ["negative", "neutral", "positive"] as const;
