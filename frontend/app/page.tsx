"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { useFilters } from "./lib/filters";
import { formatCount, formatDay, formatPercent, formatPoints, formatSigned, humanize } from "./lib/format";
import { AlertCard } from "./components/AlertCard";
import { FilterBar } from "./components/FilterBar";
import { LiveFeed } from "./components/LiveFeed";
import { QueryState } from "./components/QueryState";
import { StatTile } from "./components/StatTile";
import { BarList } from "./components/charts/BarList";
import { ChartFrame } from "./components/charts/ChartFrame";
import { LineChart } from "./components/charts/LineChart";
import { SentimentBar } from "./components/charts/SentimentBar";
import { StackedColumns } from "./components/charts/StackedColumns";

const SENTIMENT_SEGMENTS = [
  { key: "negative", label: "Negative", color: "var(--negative)" },
  { key: "neutral", label: "Neutral", color: "var(--neutral)" },
  { key: "positive", label: "Positive", color: "var(--positive)" },
];

/** Executive overview: KPIs, alerts, sentiment over time, top issues, emotions, intents, live feed. */
export default function OverviewPage() {
  const router = useRouter();
  const { query, filters } = useFilters();
  const granularity = filters.days === "all" || (typeof filters.days === "number" && filters.days > 90) ? "week" : "day";

  const sentimentQuery = useQuery({ queryKey: ["sentiment", query], queryFn: () => api.sentiment(query) });
  const trendsQuery = useQuery({ queryKey: ["trends", query, granularity], queryFn: () => api.trends(query, granularity) });
  const topicsQuery = useQuery({ queryKey: ["topics", query], queryFn: () => api.topics(query) });
  const alertsQuery = useQuery({ queryKey: ["alerts", query], queryFn: () => api.alerts(query) });
  const emotionsQuery = useQuery({ queryKey: ["emotions", query], queryFn: () => api.emotions(query) });
  const intentsQuery = useQuery({ queryKey: ["intents", query], queryFn: () => api.intents(query) });

  const current = sentimentQuery.data?.current;
  const previous = sentimentQuery.data?.previous;
  const periodLabel = sentimentQuery.data
    ? `${formatDay(sentimentQuery.data.period.start, true)} – ${formatDay(sentimentQuery.data.period.end, true)}`
    : "";
  const vs = (change: number | null | undefined, format: (v: number) => string) =>
    change === null || change === undefined ? undefined : `${format(change)} vs previous period`;
  const negativeChange = current && previous && current.negative_rate !== null && previous.negative_rate !== null
    ? current.negative_rate - previous.negative_rate : null;
  const positiveChange = current && previous && current.positive_rate !== null && previous.positive_rate !== null
    ? current.positive_rate - previous.positive_rate : null;
  // Rounded to the displayed precision so a "−0.00" change doesn't get an arrow.
  const polarityChange = current && previous && current.avg_polarity !== null && previous.avg_polarity !== null
    ? Math.round((current.avg_polarity - previous.avg_polarity) * 100) / 100 : null;
  const volumeChange = current && previous && previous.reviews ? current.reviews / previous.reviews - 1 : null;

  const deteriorations = alertsQuery.data?.alerts.filter((alert) => alert.kind === "deterioration") ?? [];
  const improvements = alertsQuery.data?.alerts.filter((alert) => alert.kind === "improvement") ?? [];
  const points = trendsQuery.data?.points ?? [];
  const topTopics = topicsQuery.data?.topics.slice(0, 6) ?? [];

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Overview</h1>
          <p className="muted small">
            {periodLabel ? `${periodLabel} · data as of ${formatDay(sentimentQuery.data!.as_of, true)}` : "Customer feedback at a glance"}
          </p>
        </div>
      </header>
      <FilterBar />
      <QueryState isPending={sentimentQuery.isPending} error={sentimentQuery.error} />

      <div className="stack">
        <div className="stat-tiles">
          <StatTile
            label="Reviews"
            value={current ? formatCount(current.reviews) : "—"}
            delta={volumeChange}
            deltaLabel={vs(volumeChange, (v) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(0)}%`)}
          />
          <StatTile
            label="Negative rate"
            value={formatPercent(current?.negative_rate)}
            delta={negativeChange}
            deltaLabel={vs(negativeChange, formatPoints)}
            upIsGood={false}
          />
          <StatTile
            label="Positive rate"
            value={formatPercent(current?.positive_rate)}
            delta={positiveChange}
            deltaLabel={vs(positiveChange, formatPoints)}
            upIsGood
          />
          <StatTile
            label="Average sentiment score"
            value={formatSigned(current?.avg_polarity)}
            delta={polarityChange}
            deltaLabel={vs(polarityChange, (v) => formatSigned(v))}
            upIsGood
          />
        </div>

        <div className="grid grid-main">
          <div className="stack">
            <ChartFrame
              title={`Reviews per ${granularity} by sentiment`}
              legend={SENTIMENT_SEGMENTS}
              dimmed={trendsQuery.isPlaceholderData}
              table={{
                columns: ["Period", "Negative", "Neutral", "Positive", "Total"],
                rows: points.map((p) => [p.period, p.negative, p.neutral, p.positive, p.reviews]),
              }}
            >
              <StackedColumns points={points} segments={SENTIMENT_SEGMENTS} />
            </ChartFrame>
            <ChartFrame
              title="Negative rate"
              subtitle="Share of reviews classified negative"
              dimmed={trendsQuery.isPlaceholderData}
              table={{
                columns: ["Period", "Negative rate", "Reviews"],
                rows: points.map((p) => [p.period, formatPercent(p.negative_rate), p.reviews]),
              }}
            >
              <LineChart
                points={points}
                series={[{ key: "negative_rate", label: "Negative rate", color: "var(--series-1)" }]}
                formatValue={(v) => formatPercent(v, 0)}
                height={180}
              />
            </ChartFrame>
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Top issues</h2>
                  <p className="panel-subtitle">Aspects ranked by negative mentions in the period</p>
                </div>
                <Link href="/aspects" className="small">All aspects →</Link>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Aspect</th>
                      <th className="num">Mentions</th>
                      <th>Sentiment mix</th>
                      <th className="num">Negative rate</th>
                      <th className="num">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topTopics.map((topic) => (
                      <tr key={topic.aspect} className="clickable" onClick={() => router.push(`/issues/${topic.aspect}`)}>
                        <td><Link href={`/issues/${topic.aspect}`}>{topic.name}</Link></td>
                        <td className="num">{formatCount(topic.mentions)}</td>
                        <td style={{ width: "30%" }}>
                          <SentimentBar negative={topic.negative} neutral={topic.neutral} positive={topic.positive} />
                        </td>
                        <td className="num">{formatPercent(topic.negative_rate)}</td>
                        <td className={`num ${topic.negative_rate_change && topic.negative_rate_change > 0 ? "bad-text" : topic.negative_rate_change && topic.negative_rate_change < 0 ? "good-text" : ""}`}>
                          {formatPoints(topic.negative_rate_change)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <div className="stack">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Emerging alerts</h2>
                  <p className="panel-subtitle">
                    {alertsQuery.data
                      ? `Last 7 days (${formatDay(alertsQuery.data.current_window[0])} – ${formatDay(alertsQuery.data.current_window[1])}) vs the 28 days before`
                      : "Last 7 days vs the 28 days before"}
                  </p>
                </div>
              </div>
              <QueryState isPending={alertsQuery.isPending} error={alertsQuery.error} />
              {alertsQuery.data && deteriorations.length === 0 && (
                <p className="empty">No significant deterioration. Replay the event stream below to watch alerts appear.</p>
              )}
              <div className="stack" style={{ gap: 10 }}>
                {deteriorations.map((alert) => <AlertCard key={alert.id} alert={alert} compact />)}
                {improvements.map((alert) => <AlertCard key={alert.id} alert={alert} compact />)}
              </div>
            </section>
            <ChartFrame title="Emotions" subtitle="Share of reviews · marker = previous period" dimmed={emotionsQuery.isPlaceholderData}>
              <BarList
                items={(emotionsQuery.data?.items ?? []).map((item) => ({
                  label: humanize(item.label), value: item.share ?? 0, marker: item.previous_share,
                  detail: `${item.count} reviews`,
                }))}
                formatValue={(v) => formatPercent(v, 0)}
              />
            </ChartFrame>
            <ChartFrame title="Intents" subtitle="What customers want · marker = previous period" dimmed={intentsQuery.isPlaceholderData}>
              <BarList
                items={(intentsQuery.data?.items ?? []).filter((item) => item.count > 0).map((item) => ({
                  label: humanize(item.label), value: item.share ?? 0, marker: item.previous_share,
                  detail: `${item.count} reviews`,
                }))}
                formatValue={(v) => formatPercent(v, 0)}
              />
            </ChartFrame>
            <LiveFeed />
          </div>
        </div>
      </div>
    </>
  );
}
