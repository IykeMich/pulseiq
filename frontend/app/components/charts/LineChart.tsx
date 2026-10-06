"use client";

import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AXIS_LINE, AXIS_TICK, CHART_MARGIN, GRID_STROKE, TooltipCard, dayTick, dayTitle, niceTicks } from "./chartTheme";

export type LineSeries = { key: string; label: string; color: string };

/**
 * Multi-series line chart over dates (Recharts): 2px lines, hairline grid, an end dot on each
 * series, and a crosshair tooltip listing every series at the hovered date. Null values leave a
 * gap rather than drawing through missing data.
 */
export function LineChart<Point extends { period: string }>({
  points,
  series,
  formatValue,
  height = 220,
  minMax = 0,
  domain,
}: {
  points: Point[];
  series: LineSeries[];
  formatValue: (value: number) => string;
  height?: number;
  /** Smallest y maximum, so a flat series doesn't fill the whole height. */
  minMax?: number;
  /** Fixed [min, max] for signed values (e.g. -1..1); default is 0..auto. */
  domain?: [number, number];
}) {
  const value = (point: Point, key: string) => (point as Record<string, unknown>)[key] as number | null | undefined;
  const ticks = domain
    ? [domain[0], (domain[0] + domain[1]) / 2, domain[1]]
    : niceTicks(Math.max(minMax, ...points.flatMap((point) => series.map((s) => value(point, s.key) ?? 0)), 0.0001));
  const lastIndex = Object.fromEntries(
    series.map((s) => [s.key, points.map((point) => value(point, s.key)).findLastIndex((v) => v !== null && v !== undefined)]),
  );

  return (
    <div className="chart" style={{ height }} role="img" aria-label={series.map((s) => s.label).join(", ")}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart data={points} margin={CHART_MARGIN}>
          <CartesianGrid vertical={false} stroke={GRID_STROKE} />
          <XAxis dataKey="period" tickFormatter={dayTick} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} minTickGap={28} />
          <YAxis
            tickFormatter={formatValue}
            tick={AXIS_TICK}
            axisLine={false}
            tickLine={false}
            width={48}
            domain={[ticks[0], ticks[ticks.length - 1]]}
            ticks={ticks}
          />
          <Tooltip
            cursor={{ stroke: "var(--text-muted)", strokeWidth: 1 }}
            content={({ active, label }) => {
              if (!active || label === undefined) return null;
              const point = points.find((p) => p.period === label);
              if (!point) return null;
              return (
                <TooltipCard
                  title={dayTitle(label)}
                  rows={series.map((s) => {
                    const v = value(point, s.key);
                    return { label: s.label, value: v === null || v === undefined ? "—" : formatValue(v), color: s.color, shape: "line" };
                  })}
                />
              );
            }}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.label}
              type="linear"
              stroke={s.color}
              strokeWidth={2}
              connectNulls={false}
              isAnimationActive={false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              dot={(props: { cx?: number; cy?: number; index?: number }) =>
                props.index === lastIndex[s.key] && props.cx !== undefined && props.cy !== undefined ? (
                  <circle key={`end-${s.key}`} cx={props.cx} cy={props.cy} r={4} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
                ) : (
                  <g key={`dot-${s.key}-${props.index}`} />
                )
              }
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
}
