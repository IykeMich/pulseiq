/** A KPI: label, value and an optional delta vs a named period, colored by whether up is good. */
export function StatTile({
  label,
  value,
  delta,
  deltaLabel,
  upIsGood,
}: {
  label: string;
  value: string;
  delta?: number | null;
  deltaLabel?: string;
  upIsGood?: boolean;
}) {
  // Changes too small to show in the displayed precision count as no change (no arrow, no color).
  const meaningful = delta !== undefined && delta !== null && Math.abs(delta) >= 0.0005 ? delta : null;
  let deltaClass = "muted";
  if (meaningful !== null && upIsGood !== undefined) {
    deltaClass = meaningful > 0 === upIsGood ? "good-text" : "bad-text";
  }
  return (
    <div className="panel stat-tile">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {deltaLabel && (
        <span className={`stat-delta ${deltaClass}`}>
          {meaningful !== null ? (meaningful > 0 ? "▲ " : "▼ ") : ""}
          {deltaLabel}
        </span>
      )}
    </div>
  );
}
