"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useFilters } from "../lib/filters";
import { formatPercent, formatSigned } from "../lib/format";
import { FilterBar } from "../components/FilterBar";
import { QueryState } from "../components/QueryState";
import { ChartFrame } from "../components/charts/ChartFrame";
import { LineChart } from "../components/charts/LineChart";
import { StackedColumns } from "../components/charts/StackedColumns";

const SENTIMENT_SEGMENTS = [
  { key: "negative", label: "Negative", color: "var(--negative)" },
  { key: "neutral", label: "Neutral", color: "var(--neutral)" },
  { key: "positive", label: "Positive", color: "var(--positive)" },
];

/** Daily or weekly sentiment movement, optionally compared with one aspect. */
export default function TrendsPage() {
  const { query } = useFilters();
  const [granularity, setGranularity] = useState<"day" | "week">("week");
  const [aspect, setAspect] = useState("");
  const optionsQuery = useQuery({ queryKey: ["filters-options"], queryFn: api.filters, staleTime: 300_000 });
  const trendsQuery = useQuery({
    queryKey: ["trends", query, granularity, aspect],
    queryFn: () => api.trends(query, granularity, aspect),
  });
  const points = trendsQuery.data?.points ?? [];
  const aspectName = optionsQuery.data?.aspects.find((option) => option.key === aspect)?.name;

  const rateSeries = [
    { key: "negative_rate", label: "All reviews", color: "var(--series-1)" },
    ...(aspect ? [{ key: "aspect_negative_rate", label: `${aspectName} mentions`, color: "var(--series-2)" }] : []),
  ];

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Sentiment trends</h1>
          <p className="muted small">How sentiment moves over time, for any segment and aspect</p>
        </div>
        <div className="row">
          <div className="segmented" role="group" aria-label="Granularity">
            {(["day", "week"] as const).map((value) => (
              <button key={value} type="button" aria-pressed={granularity === value} onClick={() => setGranularity(value)}>
                {value === "day" ? "Daily" : "Weekly"}
              </button>
            ))}
          </div>
          <label>
            <span className="visually-hidden">Compare with aspect</span>
            <select value={aspect} onChange={(event) => setAspect(event.target.value)}>
              <option value="">Compare with an aspect…</option>
              {optionsQuery.data?.aspects.map((option) => (
                <option key={option.key} value={option.key}>{option.name}</option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <FilterBar />
      <QueryState isPending={trendsQuery.isPending} error={trendsQuery.error} />

      <div className="stack">
        <ChartFrame
          title="Negative rate"
          subtitle={aspect ? `All reviews vs ${aspectName} mentions` : "Share of reviews classified negative"}
          legend={rateSeries.map((s) => ({ label: s.label, color: s.color, shape: "line" as const }))}
          dimmed={trendsQuery.isPlaceholderData}
          table={{
            columns: ["Period", "All reviews", ...(aspect ? [`${aspectName}`, `${aspectName} mentions`] : [])],
            rows: points.map((p) => [
              p.period, formatPercent(p.negative_rate),
              ...(aspect ? [formatPercent(p.aspect_negative_rate), p.aspect_mentions ?? 0] : []),
            ]),
          }}
        >
          <LineChart points={points} series={rateSeries} formatValue={(v) => formatPercent(v, 0)} height={260} />
        </ChartFrame>

        <div className="grid grid-2">
          <ChartFrame
            title="Average sentiment score"
            subtitle="Mean of P(positive) − P(negative), from −1 to +1"
            dimmed={trendsQuery.isPlaceholderData}
            table={{ columns: ["Period", "Score"], rows: points.map((p) => [p.period, formatSigned(p.avg_polarity)]) }}
          >
            <LineChart
              points={points}
              series={[{ key: "avg_polarity", label: "Score", color: "var(--series-1)" }]}
              formatValue={(v) => formatSigned(v)}
              domain={[-1, 1]}
              height={200}
            />
          </ChartFrame>
          <ChartFrame
            title="Volume by sentiment"
            legend={SENTIMENT_SEGMENTS}
            dimmed={trendsQuery.isPlaceholderData}
            table={{
              columns: ["Period", "Negative", "Neutral", "Positive"],
              rows: points.map((p) => [p.period, p.negative, p.neutral, p.positive]),
            }}
          >
            <StackedColumns points={points} segments={SENTIMENT_SEGMENTS} height={200} />
          </ChartFrame>
        </div>
      </div>
    </>
  );
}
