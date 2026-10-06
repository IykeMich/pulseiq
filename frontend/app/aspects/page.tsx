"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useFilters } from "../lib/filters";
import { formatCount, formatPercent, formatPoints, formatSigned } from "../lib/format";
import { FilterBar } from "../components/FilterBar";
import { QueryState } from "../components/QueryState";
import { SentimentBar } from "../components/charts/SentimentBar";

/** Every aspect in the taxonomy with its sentiment mix, plus themes found without the taxonomy. */
export default function AspectsPage() {
  const router = useRouter();
  const { query } = useFilters();
  const topicsQuery = useQuery({ queryKey: ["topics", query], queryFn: () => api.topics(query) });
  const themesQuery = useQuery({ queryKey: ["themes", query], queryFn: () => api.themes(query) });

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Aspect explorer</h1>
          <p className="muted small">
            Sentiment per business aspect. One review can be positive about one aspect and negative about another.
          </p>
        </div>
      </header>
      <FilterBar />
      <div className="stack">
        <section className={`panel ${topicsQuery.isPlaceholderData ? "loading-dim" : ""}`}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Aspects</h2>
              <p className="panel-subtitle">Select an aspect for its trend, affected segments and evidence</p>
            </div>
            <div className="legend">
              <span><span className="swatch" style={{ background: "var(--negative)" }} />Negative</span>
              <span><span className="swatch" style={{ background: "var(--neutral)" }} />Neutral</span>
              <span><span className="swatch" style={{ background: "var(--positive)" }} />Positive</span>
            </div>
          </div>
          <QueryState isPending={topicsQuery.isPending} error={topicsQuery.error} />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Aspect</th>
                  <th className="num">Mentions</th>
                  <th className="num">Share of reviews</th>
                  <th>Sentiment mix</th>
                  <th className="num">Negative</th>
                  <th className="num">Positive</th>
                  <th className="num">Negative rate</th>
                  <th className="num">vs previous</th>
                  <th className="num">Net score</th>
                </tr>
              </thead>
              <tbody>
                {topicsQuery.data?.topics.map((topic) => (
                  <tr key={topic.aspect} className="clickable" onClick={() => router.push(`/issues/${topic.aspect}`)}>
                    <td><Link href={`/issues/${topic.aspect}`}>{topic.name}</Link></td>
                    <td className="num">{formatCount(topic.mentions)}</td>
                    <td className="num">{formatPercent(topic.share_of_reviews)}</td>
                    <td style={{ width: "22%" }}>
                      <SentimentBar negative={topic.negative} neutral={topic.neutral} positive={topic.positive} />
                    </td>
                    <td className="num">{formatCount(topic.negative)}</td>
                    <td className="num">{formatCount(topic.positive)}</td>
                    <td className="num">{formatPercent(topic.negative_rate)}</td>
                    <td className={`num ${topic.negative_rate_change && topic.negative_rate_change > 0 ? "bad-text" : topic.negative_rate_change && topic.negative_rate_change < 0 ? "good-text" : ""}`}>
                      {formatPoints(topic.negative_rate_change)}
                    </td>
                    <td className="num">{formatSigned(topic.net_sentiment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className={`panel ${themesQuery.isPlaceholderData ? "loading-dim" : ""}`}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Discovered themes in negative feedback</h2>
              <p className="panel-subtitle">
                Unsupervised (NMF over TF-IDF) so new problems surface even if the taxonomy doesn’t name them
                {themesQuery.data ? ` · ${formatCount(themesQuery.data.reviews)} unique negative texts` : ""}
              </p>
            </div>
          </div>
          <QueryState isPending={themesQuery.isPending} error={themesQuery.error} />
          {themesQuery.data && themesQuery.data.themes.length === 0 && (
            <p className="empty">Not enough negative feedback in this slice to find themes.</p>
          )}
          <div className="grid grid-3">
            {themesQuery.data?.themes.map((theme, index) => (
              <article key={index} className="about-card">
                <h3 className="small">{theme.terms.slice(0, 4).join(" · ")}</h3>
                <p className="muted tiny">
                  {formatCount(theme.reviews)} texts · {formatPercent(theme.outside_taxonomy_share, 0)} outside the taxonomy
                </p>
                <ul className="stack" style={{ gap: 4, marginTop: 8 }}>
                  {theme.examples.map((example) => (
                    <li key={example} className="small secondary">“{example}”</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
