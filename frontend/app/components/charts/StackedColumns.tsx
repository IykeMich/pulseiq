"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_LINE, AXIS_TICK, CHART_MARGIN, GRID_STROKE, TooltipCard, dayTick, dayTitle, niceTicks } from "./chartTheme";

export type StackSegment = { key: string; label: string; color: string };

/**
 * Stacked columns over dates (Recharts), e.g. reviews per day by sentiment. Columns are capped at
 * 24px, segments are separated by a 2px surface-colored edge, and the top segment has a rounded end.
 * Hovering a column shows every segment and the total.
 */
export function StackedColumns<Point extends { period: string }>({
  points,
  segments,
  height = 200,
}: {
  points: Point[];
  segments: StackSegment[];
  height?: number;
}) {
  const count = (point: Point, key: string) => Number((point as Record<string, unknown>)[key] ?? 0);
  const ticks = niceTicks(Math.max(1, ...points.map((point) => segments.reduce((sum, s) => sum + count(point, s.key), 0))));

  return (
    <div className="chart" style={{ height }} role="img" aria-label={`Stacked columns: ${segments.map((s) => s.label).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={points} margin={CHART_MARGIN} barCategoryGap="12%">
          <CartesianGrid vertical={false} stroke={GRID_STROKE} />
          <XAxis dataKey="period" tickFormatter={dayTick} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} minTickGap={28} />
          <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={48} domain={[0, ticks[ticks.length - 1]]} ticks={ticks}
            tickFormatter={(v: number) => v.toLocaleString()} />
          <Tooltip
            cursor={{ fill: "var(--surface-muted)" }}
            content={({ active, label }) => {
              if (!active || label === undefined) return null;
              const point = points.find((p) => p.period === label);
              if (!point) return null;
              const total = segments.reduce((sum, segment) => sum + count(point, segment.key), 0);
              return (
                <TooltipCard
                  title={dayTitle(label)}
                  rows={[...segments].reverse().map((segment) => ({
                    label: segment.label, value: count(point, segment.key).toLocaleString(), color: segment.color, shape: "box" as const,
                  }))}
                  footer={{ label: "Total", value: total.toLocaleString(), color: "", shape: "box" }}
                />
              );
            }}
          />
          {segments.map((segment, index) => (
            <Bar
              key={segment.key}
              dataKey={segment.key}
              name={segment.label}
              stackId="stack"
              fill={segment.color}
              maxBarSize={24}
              stroke="var(--surface)"
              strokeWidth={1}
              radius={index === segments.length - 1 ? [4, 4, 0, 0] : 0}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
