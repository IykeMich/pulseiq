"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Analysis } from "../lib/api";
import { formatPercent, formatSigned, humanize } from "../lib/format";
import { LabelBadge, SentimentBadge } from "../components/Badges";

const EXAMPLES = [
  "The app looks great, but payment fails every time and support is slow.",
  "Oh brilliant, the app crashed right as I was paying. Just what I needed.",
  "Someone logged into my account from another country. I'm terrified.",
  "Delivery was not bad at all, honestly quicker than I expected.",
  "Abeg, una dispatch rider no show again. I don tire.",
  "My refund was in my account within 24 hours. Impressive service!",
];

/** Reads the `text` column of a CSV (or the first column), handling quoted fields. */
function parseCsvTexts(content: string): string[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let index = 0; index < content.length; index++) {
    const char = content[index];
    if (quoted) {
      if (char === '"' && content[index + 1] === '"') { field += '"'; index++; }
      else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { row.push(field); field = ""; }
    else if (char === "\n" || char === "\r") {
      if (char === "\r" && content[index + 1] === "\n") index++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += char;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const header = rows[0]?.map((cell) => cell.trim().toLowerCase()) ?? [];
  const textColumn = header.indexOf("text");
  const body = textColumn >= 0 ? rows.slice(1) : rows;
  return body.map((cells) => (cells[Math.max(textColumn, 0)] ?? "").trim()).filter(Boolean);
}

function AnalysisResult({ analysis }: { analysis: Analysis }) {
  const [showJson, setShowJson] = useState(false);
  return (
    <div className="stack">
      <div className="grid grid-3">
        <div className="panel stat-tile">
          <span className="stat-label">Sentiment</span>
          <SentimentBadge sentiment={analysis.sentiment.label} score={analysis.sentiment.score} />
          <span className="muted tiny num">
            Score {formatSigned(analysis.sentiment.polarity)} ·{" "}
            {Object.entries(analysis.sentiment.probabilities).map(([label, p]) => `${label} ${formatPercent(p, 0)}`).join(" · ")}
          </span>
        </div>
        <div className="panel stat-tile">
          <span className="stat-label">Emotion</span>
          <LabelBadge label={analysis.emotion.label} score={analysis.emotion.score} />
        </div>
        <div className="panel stat-tile">
          <span className="stat-label">Intent</span>
          <LabelBadge label={analysis.intent.label} score={analysis.intent.score} />
        </div>
      </div>
      <section className="panel">
        <h3 className="panel-title" style={{ marginBottom: 8 }}>Aspect-based sentiment</h3>
        {analysis.aspects.length === 0 ? (
          <p className="muted small">No aspect from the taxonomy was mentioned.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Aspect</th><th>Sentiment</th><th>Evidence clause</th></tr>
            </thead>
            <tbody>
              {analysis.aspects.map((aspect) => (
                <tr key={aspect.aspect}>
                  <td>{aspect.name}</td>
                  <td><SentimentBadge sentiment={aspect.sentiment} score={aspect.score} /></td>
                  <td className="secondary">“{aspect.evidence}”</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <h3 className="panel-subtitle" style={{ margin: "14px 0 6px" }}>How the text was split into clauses</h3>
        <ol className="stack" style={{ gap: 4 }}>
          {analysis.clauses.map((clause, index) => (
            <li key={index} className="small">
              <span className="muted">{index + 1}.</span> {clause.text}{" "}
              {clause.aspects.length > 0 && <span className="muted tiny">→ {clause.aspects.map(humanize).join(", ")}</span>}
            </li>
          ))}
        </ol>
        <p className="muted tiny" style={{ marginTop: 10 }}>
          Entities: {analysis.entities.map((entity) => `${entity.value} (${entity.type})`).join(", ") || "none"} · model {analysis.model_version}
        </p>
        <button type="button" className="link-button small" style={{ marginTop: 8 }} onClick={() => setShowJson((value) => !value)}>
          {showJson ? "Hide" : "Show"} API response
        </button>
        {showJson && <pre className="json">{JSON.stringify(analysis, null, 2)}</pre>}
      </section>
    </div>
  );
}

/** Try the models on any text, send it into the live stream, or analyze a batch. */
export default function AnalyzePage() {
  const [text, setText] = useState(EXAMPLES[0]);
  const [submission, setSubmission] = useState({ product: "", channel: "web", city: "", country: "" });
  const [batchInput, setBatchInput] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const optionsQuery = useQuery({ queryKey: ["filters-options"], queryFn: api.filters, staleTime: 300_000 });
  const analyzeMutation = useMutation({ mutationFn: api.analyze });
  const submitMutation = useMutation({
    mutationFn: api.submitFeedback,
    onSuccess: (response) =>
      setToast(
        `Event ${response.trace.event_id} queued. It shows up in the dashboard once processed` +
          (response.clock === "simulated" ? " (timestamped at the end of the demo data)." : "."),
      ),
  });
  const batchMutation = useMutation({ mutationFn: api.batch });
  const batchTexts = batchInput.split("\n").map((line) => line.trim()).filter(Boolean);

  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(timeout);
  }, [toast]);

  async function loadCsv(file: File) {
    const texts = parseCsvTexts(await file.text()).slice(0, 500);
    setBatchInput(texts.join("\n"));
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Analyze text</h1>
          <p className="muted small">One review in, every signal out: POST /api/v1/analyze</p>
        </div>
      </header>
      <div className="stack">
        <section className="panel">
          <label htmlFor="review-text" className="panel-title">Customer feedback</label>
          <textarea
            id="review-text"
            rows={3}
            maxLength={2000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            style={{ marginTop: 8 }}
          />
          <div className="row" style={{ marginTop: 8 }}>
            <span className="muted tiny">Try:</span>
            {EXAMPLES.map((example) => (
              <button key={example} type="button" className="badge" style={{ cursor: "pointer" }} onClick={() => setText(example)}>
                {example.length > 38 ? `${example.slice(0, 38)}…` : example}
              </button>
            ))}
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="button button-primary"
              disabled={!text.trim() || analyzeMutation.isPending}
              onClick={() => analyzeMutation.mutate(text)}
            >
              {analyzeMutation.isPending ? "Analyzing…" : "Analyze"}
            </button>
            <span className="muted small" style={{ marginLeft: 8 }}>or send it into the live stream as</span>
            <select value={submission.product} onChange={(event) => setSubmission({ ...submission, product: event.target.value })} aria-label="Product">
              <option value="">No product</option>
              {optionsQuery.data?.product.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <select value={submission.channel} onChange={(event) => setSubmission({ ...submission, channel: event.target.value })} aria-label="Channel">
              {(optionsQuery.data?.channel ?? ["web"]).map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
            <select
              value={submission.city}
              onChange={(event) => setSubmission({ ...submission, city: event.target.value })}
              aria-label="City"
            >
              <option value="">No city</option>
              {optionsQuery.data?.city.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
            <button
              type="button"
              className="button"
              disabled={!text.trim() || submitMutation.isPending}
              onClick={() =>
                submitMutation.mutate({
                  text,
                  product: submission.product || undefined,
                  channel: submission.channel,
                  city: submission.city || undefined,
                })
              }
            >
              Submit as feedback
            </button>
          </div>
          {(analyzeMutation.error || submitMutation.error) && (
            <p className="error-text small" style={{ marginTop: 8 }}>{(analyzeMutation.error ?? submitMutation.error)?.message}</p>
          )}
        </section>

        {analyzeMutation.data && <AnalysisResult analysis={analyzeMutation.data} />}

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Batch analysis</h2>
              <p className="panel-subtitle">One review per line, or upload a CSV with a “text” column (up to 500). Nothing is stored.</p>
            </div>
            <label className="button">
              Upload CSV
              <input type="file" accept=".csv,text/csv" className="visually-hidden" onChange={(event) => event.target.files?.[0] && loadCsv(event.target.files[0])} />
            </label>
          </div>
          <textarea rows={5} value={batchInput} onChange={(event) => setBatchInput(event.target.value)} placeholder={EXAMPLES.join("\n")} />
          <div className="row" style={{ marginTop: 8 }}>
            <button
              type="button"
              className="button button-primary"
              disabled={!batchTexts.length || batchTexts.length > 500 || batchMutation.isPending}
              onClick={() => batchMutation.mutate(batchTexts)}
            >
              {batchMutation.isPending ? "Analyzing…" : `Analyze ${batchTexts.length || ""} reviews`}
            </button>
            {batchTexts.length > 500 && <span className="error-text small">Keep it to 500 lines.</span>}
            {batchMutation.error && <span className="error-text small">{batchMutation.error.message}</span>}
          </div>
          {batchMutation.data && (
            <div className="stack" style={{ marginTop: 14 }}>
              <p className="small">
                {Object.entries(batchMutation.data.summary.sentiment).map(([label, count]) => `${count} ${label}`).join(" · ")}
                {batchMutation.data.summary.aspects.length > 0 && " · Most negative: " +
                  [...batchMutation.data.summary.aspects].sort((a, b) => b.negative - a.negative).slice(0, 3)
                    .map((aspect) => `${humanize(aspect.aspect)} (${aspect.negative}/${aspect.mentions})`).join(", ")}
              </p>
              <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}>
                <table>
                  <thead>
                    <tr><th>Text</th><th>Sentiment</th><th>Emotion</th><th>Intent</th><th>Aspects</th></tr>
                  </thead>
                  <tbody>
                    {batchMutation.data.results.map((result) => (
                      <tr key={result.review_id}>
                        <td style={{ maxWidth: 420 }}>{result.text}</td>
                        <td><SentimentBadge sentiment={result.sentiment.label} /></td>
                        <td>{humanize(result.emotion.label)}</td>
                        <td>{humanize(result.intent.label)}</td>
                        <td className="small">{result.aspects.map((aspect) => `${aspect.name}: ${aspect.sentiment}`).join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </div>
      {toast && <div className="toast" role="status">{toast}</div>}
    </>
  );
}
