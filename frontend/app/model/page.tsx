"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type ClassReport, type ModelKey, type TaskReport } from "../lib/api";
import { formatCount, formatDateTime, formatPercent, humanize } from "../lib/format";
import { QueryState } from "../components/QueryState";
import { BarList } from "../components/charts/BarList";

const MODEL_NAMES: Record<string, string> = {
  majority_class: "Majority class",
  rule_based_lexicon: "Rule-based lexicon",
  baseline_tfidf_unigram_lr: "Baseline: TF-IDF words + LR",
  final_tfidf_word_char_lr: "Word+char: words, negation, char n-grams + LR",
};

/** "3/4" style count from an accuracy on a category of known size. */
const outOf = (accuracy: number, size: number) => `${Math.round(accuracy * size)}/${size}`;

const f = (value: number) => value.toFixed(3);

/** Confusion matrix as a heat table: each cell's shade is its share of the true class (row). */
function ConfusionMatrix({ report }: { report: ClassReport }) {
  const { labels, matrix } = report.confusion_matrix;
  return (
    <div className="table-wrap">
      <table style={{ width: "auto" }}>
        <thead>
          <tr>
            <th>True ↓ / Predicted →</th>
            {labels.map((label) => <th key={label} className="num">{humanize(label)}</th>)}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, rowIndex) => {
            const total = row.reduce((sum, value) => sum + value, 0) || 1;
            return (
              <tr key={labels[rowIndex]}>
                <th scope="row">{humanize(labels[rowIndex])}</th>
                {row.map((value, columnIndex) => {
                  const share = value / total;
                  return (
                    <td
                      key={columnIndex}
                      className="heat-cell"
                      title={`${humanize(labels[rowIndex])} predicted as ${humanize(labels[columnIndex])}: ${value} (${formatPercent(share, 0)})`}
                      style={{
                        background: `color-mix(in srgb, var(--series-1) ${Math.round(share * 85)}%, var(--surface))`,
                        color: share > 0.5 ? "#ffffff" : "var(--text)",
                      }}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PerClass({ report }: { report: ClassReport }) {
  return (
    <BarList
      items={Object.entries(report.per_class).map(([label, scores]) => ({
        label: humanize(label), value: scores.f1, detail: `precision ${f(scores.precision)} · recall ${f(scores.recall)} · n=${scores.support}`,
      }))}
      formatValue={f}
      max={1}
    />
  );
}

function TaskSection({ title, task, note }: { title: string; task: TaskReport; note?: string }) {
  const [showMatrix, setShowMatrix] = useState(false);
  const other: ModelKey = task.selected_model === "baseline_tfidf_unigram_lr" ? "final_tfidf_word_char_lr" : "baseline_tfidf_unigram_lr";
  const final = task.test[task.selected_model];
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="panel-subtitle">
            Deployed: {MODEL_NAMES[task.selected_model]} (higher validation macro-F1:{" "}
            {f(task.validation_macro_f1[task.selected_model])} vs {f(task.validation_macro_f1[other])})
          </p>
          <p className="panel-subtitle">
            Test macro-F1 {f(final.macro_f1)} vs {f(task.test[other].macro_f1)} for the other candidate · accuracy {formatPercent(final.accuracy)}
          </p>
        </div>
        <button type="button" className="link-button small" onClick={() => setShowMatrix((value) => !value)}>
          {showMatrix ? "Per-class F1" : "Confusion matrix"}
        </button>
      </div>
      {showMatrix ? <ConfusionMatrix report={final} /> : <PerClass report={final} />}
      {note && <p className="muted tiny" style={{ marginTop: 10 }}>{note}</p>}
    </section>
  );
}

/** Model version, evaluation against baselines, real errors, cross-dataset check, data quality. */
export default function ModelPage() {
  const modelQuery = useQuery({ queryKey: ["model"], queryFn: api.model });
  const qualityQuery = useQuery({ queryKey: ["quality"], queryFn: api.quality });
  const [mistakesOnly, setMistakesOnly] = useState(true);
  const model = modelQuery.data;
  const metrics = model?.metrics;

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Model & data</h1>
          <p className="muted small">
            {model ? `${model.model_version} · trained ${formatDateTime(model.trained_at)} on ${formatCount(model.training_reviews)} reviews` : "Evaluation results"}
          </p>
        </div>
      </header>
      <QueryState isPending={modelQuery.isPending} error={modelQuery.error} />
      {metrics && (
        <div className="stack">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Sentiment: baselines vs word+char model</h2>
                <p className="panel-subtitle">
                  Held-out test set of {formatCount(metrics.data.test)} synthetic reviews (train {formatCount(metrics.data.train)} /
                  validation {formatCount(metrics.data.validation)}); C chosen on validation, test used once
                </p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th className="num">Accuracy</th>
                    <th className="num">Macro precision</th>
                    <th className="num">Macro recall</th>
                    <th className="num">Macro-F1</th>
                    <th className="num">Neutral F1</th>
                    <th className="num">Challenge set</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(metrics.sentiment.test).map(([key, report]) => (
                    <tr key={key}>
                      <td>
                        {key === metrics.sentiment.selected_model ? <strong>{MODEL_NAMES[key]}</strong> : MODEL_NAMES[key] ?? key}
                        {key === metrics.sentiment.selected_model && <span className="badge" style={{ marginLeft: 6 }}>Deployed</span>}
                      </td>
                      <td className="num">{f(report.accuracy)}</td>
                      <td className="num">{f(report.macro_precision)}</td>
                      <td className="num">{f(report.macro_recall)}</td>
                      <td className="num">{f(report.macro_f1)}</td>
                      <td className="num">{f(report.per_class.neutral.f1)}</td>
                      <td className="num">
                        {key in metrics.sentiment.challenge_set ? formatPercent(metrics.sentiment.challenge_set[key as ModelKey].accuracy, 0) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(() => {
              const base = metrics.sentiment.test.baseline_tfidf_unigram_lr;
              const wide = metrics.sentiment.test.final_tfidf_word_char_lr;
              const challengeBase = metrics.sentiment.challenge_set.baseline_tfidf_unigram_lr.by_category;
              const challengeWide = metrics.sentiment.challenge_set.final_tfidf_word_char_lr.by_category;
              const sizes = metrics.challenge_set.by_category;
              const compareCategories = (test: (wide: number, base: number) => boolean) =>
                Object.keys(challengeWide)
                  .filter((category) => test(challengeWide[category], challengeBase[category]))
                  .map((category) => `${humanize(category).toLowerCase()} (${outOf(challengeBase[category], sizes[category].size)} → ${outOf(challengeWide[category], sizes[category].size)})`)
                  .join(", ");
              return (
                <p className="small" style={{ marginTop: 12 }}>
                  <strong>Why the word+char model is deployed:</strong> it wins on validation and test, by a modest margin
                  (macro-F1 {f(wide.macro_f1)} vs {f(base.macro_f1)}), most on the hardest class, neutral (mixed reviews):
                  F1 {f(base.per_class.neutral.f1)} → {f(wide.per_class.neutral.f1)}. On the 60 hand-written cases the two are close
                  ({formatPercent(metrics.sentiment.challenge_set.final_tfidf_word_char_lr.accuracy, 0)} vs{" "}
                  {formatPercent(metrics.sentiment.challenge_set.baseline_tfidf_unigram_lr.accuracy, 0)}): better on{" "}
                  {compareCategories((wide, base) => wide > base) || "no category"}, worse on{" "}
                  {compareCategories((wide, base) => wide < base) || "no category"}. With 3–6 cases per category that is a hint,
                  not proof; written-out negation stays weak ({outOf(challengeWide.negation, sizes.negation.size)}) because the
                  negation marker only reaches 3 words. Macro-F1 is the headline because classes are uneven.
                </p>
              );
            })()}
            <div className="grid grid-2" style={{ marginTop: 14 }}>
              <div>
                <p className="panel-subtitle" style={{ marginBottom: 6 }}>Deployed model confusion matrix (test)</p>
                <ConfusionMatrix report={metrics.sentiment.test[metrics.sentiment.selected_model]} />
              </div>
              <div>
                <p className="panel-subtitle" style={{ marginBottom: 6 }}>Error rate by difficulty (test)</p>
                <BarList
                  items={Object.entries(metrics.sentiment.error_analysis.by_tag)
                    .sort((a, b) => b[1].error_rate - a[1].error_rate)
                    .map(([tag, value]) => ({ label: humanize(tag), value: value.error_rate, detail: `${value.reviews} reviews` }))}
                  formatValue={(v) => formatPercent(v, 0)}
                  color="var(--negative)"
                />
                <p className="muted tiny" style={{ marginTop: 8 }}>
                  “Rating mismatch” reviews have a star rating that contradicts the text (a wrong tap), so their label is wrong, not the model.
                </p>
              </div>
            </div>
          </section>

          <section className="panel">
            <h2 className="panel-title">Real model errors</h2>
            <p className="panel-subtitle" style={{ marginBottom: 8 }}>A sample of wrong test predictions, kept for manual review</p>
            <div className="table-wrap" style={{ maxHeight: 340, overflowY: "auto" }}>
              <table>
                <thead><tr><th>Text</th><th>Rating</th><th>Label</th><th>Predicted</th><th>Tags</th></tr></thead>
                <tbody>
                  {metrics.sentiment.error_analysis.sample_errors.map((error, index) => (
                    <tr key={index}>
                      <td style={{ maxWidth: 520 }}>{error.text}</td>
                      <td className="num">{error.rating}★</td>
                      <td>{error.expected}</td>
                      <td className="bad-text">{error.predicted}</td>
                      <td className="tiny muted">{error.tags.join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid grid-2">
            <TaskSection
              title="Emotion"
              task={metrics.emotion}
              note="Surprise is the hardest class: positive surprise reads like joy, so it is most often predicted as joy. Here the simpler model generalises better."
            />
            <TaskSection
              title="Intent"
              task={metrics.intent}
              note="Delivery and payment issues are most often predicted as refund requests: the same reviews frequently ask for the money back."
            />
          </div>

          <section className="panel">
            <h2 className="panel-title">Aspect detection and aspect sentiment (test)</h2>
            <p className="panel-subtitle" style={{ marginBottom: 10 }}>
              Detection F1 {f(metrics.aspects.test.detection.f1)} (precision {f(metrics.aspects.test.detection.precision)}, recall{" "}
              {f(metrics.aspects.test.detection.recall)}) · sentiment correct on {formatPercent(metrics.aspects.test.sentiment_accuracy)} of
              correctly detected aspects. The taxonomy keywords share vocabulary with the generator, so the challenge set below is
              the fairer test.
            </p>
            <BarList
              items={Object.entries(metrics.aspects.test.per_aspect).map(([aspect, scores]) => ({
                label: humanize(aspect), value: scores.f1, detail: `precision ${f(scores.precision)} · recall ${f(scores.recall)} · n=${scores.support}`,
              }))}
              formatValue={f}
              max={1}
            />
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Hand-written challenge set</h2>
                <p className="panel-subtitle">
                  {metrics.challenge_set.size} hard cases written separately from the generator: sentiment{" "}
                  {formatPercent(metrics.challenge_set.sentiment_accuracy, 0)} · emotion {formatPercent(metrics.challenge_set.emotion_accuracy, 0)} ·
                  intent {formatPercent(metrics.challenge_set.intent_accuracy, 0)} · aspect detection F1 {f(metrics.challenge_set.aspects.detection.f1)}
                </p>
              </div>
              <label className="small row">
                <input type="checkbox" checked={mistakesOnly} onChange={(event) => setMistakesOnly(event.target.checked)} />
                Sentiment mistakes only
              </label>
            </div>
            <div className="grid grid-main">
              <div className="table-wrap" style={{ maxHeight: 380, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Text</th><th>Category</th><th>Expected</th><th>Predicted</th><th>Aspects predicted</th></tr></thead>
                  <tbody>
                    {metrics.challenge_set.rows
                      .filter((row) => !mistakesOnly || row.sentiment.expected !== row.sentiment.predicted)
                      .map((row) => (
                        <tr key={row.text}>
                          <td style={{ maxWidth: 380 }}>{row.text}</td>
                          <td className="small">{humanize(row.category)}</td>
                          <td>{row.sentiment.expected}</td>
                          <td className={row.sentiment.expected === row.sentiment.predicted ? "" : "bad-text"}>{row.sentiment.predicted}</td>
                          <td className="tiny">{row.aspects.predicted.map((a) => `${a.aspect}:${a.sentiment}`).join(", ") || "—"}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <div>
                <p className="panel-subtitle" style={{ marginBottom: 6 }}>Sentiment accuracy by category</p>
                <BarList
                  items={Object.entries(metrics.challenge_set.by_category)
                    .sort((a, b) => a[1].sentiment_accuracy - b[1].sentiment_accuracy)
                    .map(([category, value]) => ({ label: humanize(category), value: value.sentiment_accuracy, detail: `${value.size} cases` }))}
                  formatValue={(v) => formatPercent(v, 0)}
                  max={1}
                />
              </div>
            </div>
          </section>

          <section className="panel">
            <h2 className="panel-title">Cross-dataset check: the dataset pack</h2>
            <p className="panel-subtitle" style={{ marginBottom: 10 }}>
              The dashboard runs on the pack ({formatCount(metrics.dataset_pack.rows)} rows, only {formatCount(metrics.dataset_pack.unique_texts)} unique
              texts), but the models never trained on it
            </p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Check</th><th className="num">Result</th><th className="num">Best possible</th><th>Reading</th></tr></thead>
                <tbody>
                  <tr>
                    <td>Sentiment macro-F1 (unique texts)</td>
                    <td className="num">{f(metrics.dataset_pack.sentiment_unique_texts.macro_f1)}</td>
                    <td className="num">1.000</td>
                    <td className="small">Domain shift: plain statements in the pack (“I am testing X…”) are often read as negative</td>
                  </tr>
                  <tr>
                    <td>Primary aspect detected</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.primary_aspect_detected)}</td>
                    <td className="num">100%</td>
                    <td className="small">Every pack text names its aspect explicitly</td>
                  </tr>
                  <tr>
                    <td>Emotion agreement</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.emotion_agreement)}</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.emotion_label_ceiling)}</td>
                    <td className="small">Identical texts carry different emotions in the pack, so no model can exceed the ceiling</td>
                  </tr>
                  <tr>
                    <td>Intent agreement</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.intent_agreement)}</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.intent_label_ceiling)}</td>
                    <td className="small">The pack derives intent from the aspect (a happy delivery review is “delivery issue”)</td>
                  </tr>
                  <tr>
                    <td>Aspect sentiment (ABSA sample)</td>
                    <td className="num">{formatPercent(metrics.dataset_pack.absa_sample.sentiment_accuracy)}</td>
                    <td className="num">100%</td>
                    <td className="small">Sample texts state sentiment literally (“performance that is positive”), unlike real reviews</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid grid-2">
            <section className="panel">
              <h2 className="panel-title">Data quality (raw zone)</h2>
              <QueryState isPending={qualityQuery.isPending} error={qualityQuery.error} />
              {qualityQuery.data && (
                <>
                  <p className="panel-subtitle" style={{ marginBottom: 8 }}>
                    {qualityQuery.data.source} · {formatCount(qualityQuery.data.rows)} rows · {qualityQuery.data.date_range.join(" to ")}
                  </p>
                  <ul className="stack" style={{ gap: 8 }}>
                    {qualityQuery.data.checks.map((check) => (
                      <li key={check.check} className="small">
                        <span className={`badge ${check.status === "pass" ? "sev-info" : check.status === "warn" ? "sev-high" : "sev-critical"}`}>
                          {check.status === "pass" ? "✓ Pass" : check.status === "warn" ? "! Warn" : "✕ Fail"}
                        </span>{" "}
                        <strong>{check.check}</strong> <span className="muted">— {check.detail}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
            <section className="panel">
              <h2 className="panel-title">API health (since start-up)</h2>
              <div className="table-wrap" style={{ marginTop: 8 }}>
                <table>
                  <thead><tr><th>Route</th><th className="num">Requests</th><th className="num">5xx</th><th className="num">p50</th><th className="num">p95</th></tr></thead>
                  <tbody>
                    {model.api.map((route) => (
                      <tr key={route.route}>
                        <td className="small"><code>{route.route}</code></td>
                        <td className="num">{route.requests}</td>
                        <td className="num">{route.errors}</td>
                        <td className="num">{route.p50_ms} ms</td>
                        <td className="num">{route.p95_ms} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      )}
    </>
  );
}
