"use client";

import { Bar, ComposedChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_TICK, TooltipCard } from "./chartTheme";

type BarItem = { label: string; value: number; marker?: number | null; detail?: string };

/** A short vertical tick drawn at a comparison value (e.g. the previous period). */
function MarkerTick(props: { cx?: number; cy?: number }) {
  if (props.cx === undefined || props.cy === undefined) return <g />;
  return <rect x={props.cx - 1} y={props.cy - 8} width={2} height={16} rx={1} fill="var(--text)" />;
}

/**
 * Horizontal bars (Recharts) with the category on the left and the values in an aligned column on
 * the right (so a comparison marker never collides with a value label). Hover shows the detail.
 */
export function BarList({
  items,
  formatValue,
  max,
  color = "var(--series-1)",
}: {
  items: BarItem[];
  formatValue: (value: number) => string;
  max?: number;
  color?: string;
}) {
  const hasMarkers = items.some((item) => item.marker !== undefined && item.marker !== null);
  const scaleMax = max ?? Math.max(...items.flatMap((item) => [item.value, item.marker ?? 0]), 0.0001);
  const height = Math.max(60, items.length * 26 + 8);
  const data = items.map((item) => ({ ...item, valueLabel: formatValue(item.value) }));

  return (
    <div className="chart" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} layout="vertical" margin={{ top: 4, right: 0, bottom: 4, left: 0 }}>
          <XAxis type="number" hide domain={[0, scaleMax]} />
          <YAxis type="category" dataKey="label" width={130} tick={{ ...AXIS_TICK, fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={false} tickLine={false} interval={0} />
          <YAxis yAxisId="values" type="category" dataKey="valueLabel" orientation="right" width={52}
            tick={{ ...AXIS_TICK, fill: "var(--text-secondary)", fontSize: 12 }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip
            cursor={{ fill: "var(--surface-muted)" }}
            content={({ active, payload }) => {
              const item = active && payload?.[0] ? (payload[0].payload as BarItem) : null;
              if (!item) return null;
              return (
                <TooltipCard
                  title={item.label}
                  rows={[
                    { label: "Value", value: formatValue(item.value), color, shape: "box" },
                    ...(item.marker !== undefined && item.marker !== null
                      ? [{ label: "Previous", value: formatValue(item.marker), color: "var(--text)", shape: "line" as const }]
                      : []),
                  ]}
                  footer={item.detail ? { label: item.detail, value: "", color: "", shape: "box" } : undefined}
                />
              );
            }}
          />
          <Bar dataKey="value" fill={color} barSize={10} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          {hasMarkers && <Scatter dataKey="marker" shape={MarkerTick} isAnimationActive={false} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
