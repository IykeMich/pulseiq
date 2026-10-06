"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type SegmentRow } from "../../lib/api";
import { useFilters } from "../../lib/filters";
import { formatCount, formatDay, formatPercent, formatPoints, humanize } from "../../lib/format";
import { AlertCard } from "../../components/AlertCard";
import { FilterBar } from "../../components/FilterBar";
import { QueryState } from "../../components/QueryState";
import { ReviewDrawer } from "../../components/ReviewDrawer";
import { StatTile } from "../../components/StatTile";
import { BarList } from "../../components/charts/BarList";
import { ChartFrame } from "../../components/charts/ChartFrame";
import { LineChart } from "../../components/charts/LineChart";
import { StackedColumns } from "../../components/charts/StackedColumns";

const DIMENSIONS = ["product", "channel", "city", "country"] as const;

function SegmentTable({ rows }: { rows: SegmentRow[] }) {
  const visible = rows.filter((row) => row.mentions > 0).slice(0, 8);
  if (!visible.length) return <p className="empty">No mentions in the last 7 days.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th className="num">Mentions</th>
            <th className="num">Negative</th>
            <th className="num">Neg. rate</th>
            <th className="num">Baseline</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => {
            const change = row.negative_rate !== null && row.baseline_negative_rate !== null
              ? row.negative_rate - row.baseline_negative_rate : null;
            return (
              <tr key={row.value}>
                <td>{humanize(row.value)}</td>
                <td className="num">{row.mentions}</td>
                <td className="num">{row.negative}</td>
                <td className={`num ${change !== null && change > 0.1 ? "bad-text" : ""}`}>{formatPercent(row.negative_rate, 0)}</td>
                <td className="num muted">{formatPercent(row.baseline_negative_rate, 0)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Issue detail: alert, 90-day trend, affected segments, evidence, measured findings and action. */
export default function IssuePage() {
  const { aspect } = useParams<{ aspect: string }>();
  const { query } = useFilters();
  const [dimension, setDimension] = useState<(typeof DIMENSIONS)[number]>("product");
  const [openReview, setOpenReview] = useState<string | null>(null);
  const issueQuery = useQuery({ queryKey: ["issue", aspect, query], queryFn: () => api.issue(aspect, query) });
  const issue = issueQuery.data;
  const change = issue && issue.current.negative_rate !== null && issue.baseline.negative_rate !== null
    ? issue.current.negative_rate - issue.baseline.negative_rate : null;
  const totalNegative = issue ? Object.values(issue.emotions).reduce((sum, count) => sum + count, 0) : 0;

  return (
    <>
      <header className="page-header">
        <div>
          <p className="small"><Link href="/aspects">← Aspect explorer</Link></p>
          <h1>{issue?.name ?? humanize(aspect)}</h1>
          <p className="muted small">
            {issue
              ? `Last 7 days (${formatDay(issue.current_window[0])} – ${formatDay(issue.current_window[1], true)}) vs the previous 28 days`
              : "Issue detail"}
          </p>
        </div>
      </header>
      <FilterBar hideRange note="Issue windows are fixed: last 7 days vs previous 28" />
      <QueryState isPending={issueQuery.isPending} error={issueQuery.error} />

      {issue && (
        <div className={`stack ${issueQuery.isPlaceholderData ? "loading-dim" : ""}`}>
          {issue.alert && <AlertCard alert={issue.alert} />}

          <div className="stat-tiles">
            <StatTile label="Mentions, last 7 days" value={formatCount(issue.current.mentions)} />
            <StatTile label="Negative mentions" value={formatCount(issue.current.negative)} />
            <StatTile
              label="Negative rate"
              value={formatPercent(issue.current.negative_rate)}
              delta={change}
              deltaLabel={change === null ? undefined : `${formatPoints(change)} vs baseline`}
              upIsGood={false}
            />
            <StatTile label="Baseline negative rate" value={formatPercent(issue.baseline.negative_rate)} deltaLabel={`${formatCount(issue.baseline.mentions)} mentions in 28 days`} />
          </div>

          <div className="grid grid-2">
            <ChartFrame
              title="Negative rate, 90 days"
              subtitle="7-day rolling share of mentions that are negative"
              table={{
                columns: ["Day", "Mentions", "Negative", "7-day negative rate"],
                rows: issue.trend.map((p) => [p.period, p.mentions, p.negative, formatPercent(p.negative_rate_7d)]),
              }}
            >
              <LineChart
                points={issue.trend}
                series={[{ key: "negative_rate_7d", label: "Negative rate (7-day)", color: "var(--series-1)" }]}
                formatValue={(v) => formatPercent(v, 0)}
                height={220}
              />
            </ChartFrame>
            <ChartFrame
              title="Mentions per day"
              legend={[
                { label: "Negative", color: "var(--negative)" },
                { label: "Other", color: "var(--neutral)" },
              ]}
              table={{ columns: ["Day", "Negative", "Other"], rows: issue.trend.map((p) => [p.period, p.negative, p.mentions - p.negative]) }}
            >
              <StackedColumns
                points={issue.trend.map((p) => ({ ...p, other: p.mentions - p.negative }))}
                segments={[
                  { key: "negative", label: "Negative", color: "var(--negative)" },
                  { key: "other", label: "Other", color: "var(--neutral)" },
                ]}
                height={220}
              />
            </ChartFrame>
          </div>

          <div className="grid grid-main">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Affected segments</h2>
                  <p className="panel-subtitle">Last 7 days, with the 28-day baseline negative rate</p>
                </div>
                <div className="segmented" role="group" aria-label="Segment dimension">
                  {DIMENSIONS.map((value) => (
                    <button key={value} type="button" aria-pressed={dimension === value} onClick={() => setDimension(value)}>
                      {humanize(value)}
                    </button>
                  ))}
                </div>
              </div>
              <SegmentTable rows={issue.segments[dimension]} />
            </section>
            <section className="panel">
              <h2 className="panel-title" style={{ marginBottom: 10 }}>In the negative reviews</h2>
              {totalNegative ? (
                <div className="stack">
                  <div>
                    <p className="panel-subtitle" style={{ marginBottom: 6 }}>Emotion</p>
                    <BarList
                      items={Object.entries(issue.emotions).map(([label, count]) => ({ label: humanize(label), value: count / totalNegative }))}
                      formatValue={(v) => formatPercent(v, 0)}
                      max={1}
                    />
                  </div>
                  <div>
                    <p className="panel-subtitle" style={{ marginBottom: 6 }}>Intent</p>
                    <BarList
                      items={Object.entries(issue.intents).slice(0, 5).map(([label, count]) => ({ label: humanize(label), value: count / totalNegative }))}
                      formatValue={(v) => formatPercent(v, 0)}
                      max={1}
                    />
                  </div>
                </div>
              ) : (
                <p className="empty">No negative mentions in the last 7 days.</p>
              )}
            </section>
          </div>

          <div className="grid grid-2">
            <section className="panel">
              <h2 className="panel-title">Measured findings</h2>
              <p className="panel-subtitle" style={{ marginBottom: 10 }}>Every sentence below is computed from the data</p>
              <ul className="stack" style={{ gap: 8 }}>
                {issue.findings.map((finding) => <li key={finding} className="small">• {finding}</li>)}
              </ul>
              <h3 className="panel-title" style={{ margin: "16px 0 6px" }}>Recommended action</h3>
              <p className="small">{issue.recommended_action}</p>
              <p className="note tiny" style={{ marginTop: 14 }}>
                A generated explanation (Amazon Bedrock, grounded in this evidence) is the AWS phase of the build
                guide and is not part of this local version. Findings here are measured, not generated.
              </p>
            </section>
            <section className="panel">
              <h2 className="panel-title">Evidence</h2>
              <p className="panel-subtitle" style={{ marginBottom: 6 }}>Most recent negative mentions; select one to see the full analysis</p>
              {issue.evidence.length === 0 && <p className="empty">No negative evidence in the last 7 days.</p>}
              <ul className="review-list">
                {issue.evidence.map((item) => (
                  <li key={item.review_id}>
                    <button type="button" className="review-item" onClick={() => setOpenReview(item.review_id)}>
                      <span className="evidence small">{item.evidence}</span>
                      <span className="muted tiny">
                        {formatDay(item.date, true)} · {item.product} · {humanize(item.channel)} · {item.city} · confidence {formatPercent(item.confidence, 0)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      )}
      {openReview && <ReviewDrawer reviewId={openReview} onClose={() => setOpenReview(null)} />}
    </>
  );
}
