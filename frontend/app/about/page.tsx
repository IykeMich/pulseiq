import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Project details · PulseIQ Customer Pulse",
  description:
    "PulseIQ Customer Pulse in plain language: a sentiment and behavioral intelligence platform built with Python, scikit-learn, FastAPI and Next.js.",
};

// Static page: no API calls, so it renders even when the backend is down.
// Every number below is copied from backend/artifacts/metrics.json or the data-quality report.

const FEATURES = [
  { title: "Executive overview", body: "Reviews, negative rate and sentiment score against the previous period, top issues and emerging alerts." },
  { title: "Aspect-based sentiment", body: "One review can praise the app and complain about payment: each aspect gets its own sentiment and evidence clause." },
  { title: "Early warning", body: "The last 7 days are compared with the 28 before. Significant rises become alerts, with the segments driving them." },
  { title: "Issue drill-down", body: "Click an aspect: 90-day trend, affected products, channels and cities, real evidence, measured findings and a recommended action." },
  { title: "Live stream", body: "Replay 1,000 feedback events or submit your own and watch counters, trends and alerts update as events are processed." },
  { title: "Honest model page", body: "Baselines, confusion matrices, real errors, a hand-written challenge set and a cross-dataset check." },
];

const PIPELINE = [
  { title: "Raw zone", body: "The dataset pack, untouched: 20,000 demo reviews plus a 1,000-event stream file. Quality checks flag problems (75% of rows pair a city with the wrong country) rather than hide them." },
  { title: "NLP", body: "Separate classifiers for sentiment, emotion and intent (TF-IDF + logistic regression, chosen per task on validation), a 10-aspect taxonomy matched clause by clause, and entity lookup." },
  { title: "Processed and curated zones", body: "One enriched record per review in a stable output schema, then daily aggregates by product, channel, country and city." },
  { title: "Intelligence API", body: "FastAPI separates single-text inference from analytics: metrics, trends, alerts, issue detail, search, theme discovery and a streaming endpoint." },
  { title: "Dashboard", body: "This Next.js app, with TanStack Query and Recharts charts that refresh when the stream processes new events." },
];

const RESULTS = [
  { value: "0.926", label: "Sentiment macro-F1", note: "vs 0.918 TF-IDF baseline, 0.695 rule-based lexicon" },
  { value: "0.831", label: "Emotion macro-F1", note: "7 emotions; the simpler model won on validation" },
  { value: "0.830", label: "Intent macro-F1", note: "10 customer intents" },
  { value: "0.982", label: "Aspect detection F1", note: "93% of detected aspects get the right sentiment" },
];

const HIGHLIGHTS = [
  "Evaluation before decoration: every task is compared with a baseline on a held-out test set, and the richer model is deployed only where it wins on validation (it lost for emotion, so the baseline ships).",
  "Where it fails is shown, not hidden: 60 hand-written hard cases (negation, sarcasm, typos, Nigerian-English expressions) score 75% on sentiment, and written-out negation is a known weakness.",
  "Cross-dataset honesty: the dashboard's demo data was never used for training. Sentiment on it scores 0.73 macro-F1, and the page explains that its emotion labels cap any model at 56% agreement.",
  "Alerts need evidence: a rise must be at least 8 points, 20% relative and significant (z ≥ 2) before it is raised, and a segment is only named as the driver when it holds a real share of the negatives.",
  "A stable output schema (sentiment, emotion, intent, topics, aspects, model version) means models can change without touching storage, API or UI.",
];

const STACK = [
  { group: "ML / NLP", items: ["Python", "scikit-learn", "pandas", "NumPy"] },
  { group: "Backend", items: ["FastAPI", "Uvicorn", "pytest"] },
  { group: "Frontend", items: ["Next.js", "React", "TypeScript", "TanStack Query", "Recharts"] },
  { group: "AWS (next phase)", items: ["S3", "Glue", "Athena", "Kinesis", "Bedrock", "App Runner"] },
];

const RUN_LOCALLY = `# Backend (from backend/)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m src.train          # models + metrics
python -m src.pipeline       # raw -> processed -> curated
uvicorn api.main:app --reload --port 8006

# Frontend (from frontend/)
npm install
cp .env.example .env.local
npm run dev                  # http://localhost:3006`;

/** "Project details" page for recruiters and hiring managers: plain language first, depth second. */
export default function AboutPage() {
  return (
    <div className="about">
      <header className="panel">
        <p className="small"><Link href="/">← Back to the dashboard</Link></p>
        <h1 style={{ fontSize: "1.5rem", margin: "6px 0" }}>PulseIQ Customer Pulse</h1>
        <p className="secondary">
          A sentiment and behavioral intelligence platform that turns unstructured customer feedback into
          structured signals, detects emerging problems, explains what is driving them and points to an action.
        </p>
      </header>

      <section className="panel">
        <h2>The problem</h2>
        <p>
          Companies collect thousands of reviews, tickets and survey comments, but a single “positive / negative”
          label hides what matters: which part of the experience is failing, for whom, since when, and what to do.
          PulseIQ reads every piece of feedback for sentiment, emotion, intent and aspect-level opinions, watches
          those signals over time, and raises an alert with evidence when something changes.
        </p>
      </section>

      <section className="panel">
        <h2>What it does</h2>
        <ul className="about-grid">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="about-card">
              <h3>{feature.title}</h3>
              <p className="muted small">{feature.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>How it works</h2>
        <ol className="pipeline-list">
          {PIPELINE.map((step, index) => (
            <li key={step.title}>
              <span className="step-number" aria-hidden="true">{index + 1}</span>
              <div>
                <h3 className="small">{step.title}</h3>
                <p className="muted small">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel">
        <h2>Results</h2>
        <dl className="stat-tiles">
          {RESULTS.map((result) => (
            <div key={result.label} className="stat-tile about-card">
              <dt className="stat-label">{result.label}</dt>
              <dd className="stat-value">{result.value}</dd>
              <dd className="muted tiny">{result.note}</dd>
            </div>
          ))}
        </dl>
        <p className="muted small" style={{ marginTop: 12 }}>
          Scores are on a held-out test set of a seeded synthetic training corpus written in the dataset pack’s
          taxonomy. All data is <strong>synthetic</strong>: it demonstrates the engineering, not real customer behaviour.
        </p>
      </section>

      <section className="panel">
        <h2>Engineering highlights</h2>
        <ul className="stack" style={{ gap: 8 }}>
          {HIGHLIGHTS.map((highlight) => <li key={highlight} className="small">• {highlight}</li>)}
        </ul>
      </section>

      <section className="panel">
        <h2>Tech stack</h2>
        <div className="about-grid">
          {STACK.map((group) => (
            <div key={group.group}>
              <h3 className="small" style={{ marginBottom: 6 }}>{group.group}</h3>
              <div className="row">
                {group.items.map((item) => <span key={item} className="badge">{item}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Run it locally</h2>
        <pre className="code">{RUN_LOCALLY}</pre>
      </section>
    </div>
  );
}
