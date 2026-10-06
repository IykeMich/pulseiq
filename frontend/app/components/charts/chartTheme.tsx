"use client";

import { formatDay } from "../../lib/format";

/** Shared Recharts styling: recessive hairline grid and axes, muted 11px tick labels. */
export const AXIS_TICK = { fill: "var(--text-muted)", fontSize: 11 };
export const AXIS_LINE = { stroke: "var(--axis)" };
export const GRID_STROKE = "var(--grid)";
export const CHART_MARGIN = { top: 10, right: 16, bottom: 0, left: 0 };

type TooltipRow = { label: string; value: string; color: string; shape: "line" | "box" };

/** The tooltip body every chart uses: date first, then one row per series, values in bold. */
export function TooltipCard({ title, rows, footer }: { title: string; rows: TooltipRow[]; footer?: TooltipRow }) {
  return (
    <div className="chart-tooltip chart-tooltip-static">
      <div className="tip-title">{title}</div>
      {rows.map((row) => (
        <div className="tip-row" key={row.label}>
          <span>
            {row.shape === "line" ? (
              <span className="line-key" style={{ background: row.color }} />
            ) : (
              <span className="swatch" style={{ background: row.color, display: "inline-block", marginRight: 6 }} />
            )}
            {row.label}
          </span>
          <strong>{row.value}</strong>
        </div>
      ))}
      {footer && (
        <div className="tip-row muted">
          <span>{footer.label}</span>
          <strong>{footer.value}</strong>
        </div>
      )}
    </div>
  );
}

export const dayTick = (value: string) => formatDay(value);
export const dayTitle = (value: unknown) => (typeof value === "string" ? formatDay(value, true) : "");

/** Rounded axis ticks from 0: a max of 0.77 gives [0, 0.2, 0.4, 0.6, 0.8]. */
export function niceTicks(maxValue: number, count = 4): number[] {
  if (maxValue <= 0) return [0, 1];
  const rawStep = maxValue / count;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rawStep) ?? rawStep;
  const ticks: number[] = [];
  for (let value = 0; value <= maxValue + step * 0.999; value += step) ticks.push(Number(value.toPrecision(10)));
  return ticks;
}
