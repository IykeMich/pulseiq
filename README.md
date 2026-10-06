# PulseIQ: Customer Pulse

An enterprise sentiment and behavioral intelligence platform. It turns unstructured customer
feedback into structured signals (sentiment, emotion, intent, aspect-level opinions), detects
emerging problems, shows the evidence behind them and suggests an action. It is served by a FastAPI
backend and a Next.js dashboard. Built from the *PulseIQ Sentiment Intelligence AWS Build Guide*
(Customer Pulse, the first of its three projects), with the AWS phases left for later.

```
raw/ (dataset pack, untouched) ──► quality checks
        │
        ▼
NLP: sentiment · emotion · intent (TF-IDF + LR)   aspects: taxonomy per clause + clause sentiment
        │
        ▼
processed/ (stable output schema) ──► curated/ (daily aggregates, alerts)
        │
        ▼
FastAPI: /analyze /batch · /metrics /trends /alerts /issues /feedback /themes · /feedback (POST) + stream
        │                                                          ▲
        ▼                                                          │
Next.js dashboard ◄── refetches when the stream processes events ──┘
```

## Structure

The project has the same layout as the recommendation-systems projects: `backend/` (Python API,
models, data) and `frontend/` (Next.js), deployable separately.

| Path | What it holds |
| --- | --- |
| `backend/data/raw/` | The dataset pack exactly as delivered: `customer_feedback/customer_feedback_demo.csv` (20,000 reviews) and `streaming/streaming_feedback_events.csv` (1,000 events). `live/` collects events received through the API at runtime |
| `backend/data/processed/` | `reviews_enriched.jsonl`: review contract + model output, one line per review (rebuilt by the pipeline, git-ignored) |
| `backend/data/curated/` | `daily_sentiment.csv`, `aspect_daily.csv`, `alerts.json`, `data_quality_report.json` |
| `backend/data/training/` | `synthetic_labeled_reviews.csv`: the model training corpus (see *The data*) |
| `backend/data/samples/` | `challenge_set.csv` (60 hand-written hard cases) and the pack's `aspect_sentiment_demo.csv` |
| `backend/data/schemas/` | JSON Schemas for the review contract and the model output (guide Phase 0) |
| `backend/data/reference/` | The pack's taxonomies and README; the label sets in `src/config.py` come from here |
| `backend/scripts/generate_training_data.py` | Seeded generator for the training corpus |
| `backend/src/config.py` | Paths (local mirror of the guide's S3 layout), label sets, alert thresholds |
| `backend/src/preprocess.py` | Cleaning that keeps negation and `!`/`?`, negation marking, clause splitting, the rule-based lexicon baseline |
| `backend/src/taxonomy.py` | 10-aspect keyword taxonomy (strong/weak keywords), entity gazetteer, action playbook |
| `backend/src/models.py` | The baseline and word+char scikit-learn pipelines |
| `backend/src/analyzer.py` | `PulseAnalyzer`: text → stable output schema |
| `backend/src/train.py` / `evaluate.py` | Training, model selection, evaluation, challenge set and dataset-pack check → `artifacts/` |
| `backend/src/pipeline.py` | Batch pipeline: raw → processed → curated |
| `backend/src/analytics.py` | Metrics, trends, alerts, issue detail, search, theme discovery |
| `backend/src/stream.py` | Event queue + consumer thread (local stand-in for Kinesis) |
| `backend/api/main.py` | FastAPI app |
| `backend/artifacts/` | `sentiment.joblib`, `emotion.joblib`, `intent.joblib`, `metrics.json`, `model_metadata.json` |
| `backend/tests/` | 23 pytest tests: preprocessing, analyzer, analytics (including a planted alert) and API |
| `frontend/` | Next.js dashboard (TanStack Query for data, Recharts for charts): Overview, Sentiment trends, Aspect explorer, Issue detail, Feedback explorer, Analyze text, Model & data, and the `/about` project-details page |

## Run it locally

Backend commands run from `customer_pulse/backend/`, frontend commands from `customer_pulse/frontend/`.

```bash
# 1. Environment (once), from backend/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Models + evaluation → artifacts/ (about 2 minutes; committed artifacts make this optional)
python -m src.train

# 3. Batch pipeline: raw → processed → curated (about 6 seconds)
python -m src.pipeline

# 4. API (terminal 1)
uvicorn api.main:app --reload --port 8006       # Swagger: http://localhost:8006/docs

# 5. Frontend (terminal 2, in frontend/)
npm install
cp .env.example .env.local                      # NEXT_PUBLIC_API_URL=http://localhost:8006
npm run dev                                     # http://localhost:3006
```

Tests: `python -m pytest -q` (from `backend/`). To regenerate the training corpus:
`python scripts/generate_training_data.py`, then retrain and re-run the pipeline.

Ports 8006/3006 don't collide with the recommendation projects (8001–8005 / 3001–3005).

## The demo (guide section 21)

1. **Overview:** KPIs against the previous period, sentiment over time, top issues, emotions,
   intents and alerts. On the batch data alone, no alert fires: the pack's negative rate is flat.
2. **Live event stream** (Overview, bottom right): press **Replay next 200 events** a few times.
   Each event from `streaming_feedback_events.csv` is written to the raw log, queued, analyzed
   and stored. The dashboard polls `/stream/status` and refetches whenever the data version
   changes. After the replay, a **Delivery** alert appears (negative rate up from about 33% to 50%, z ≈ 2.3).
3. **Investigate →** opens the issue page: 90-day trend, affected products, channels and cities
   against their baseline, emotion and intent mix, evidence clauses, measured findings and the
   playbook action. Click any evidence to see every signal for that review.
4. **Analyze text:** paste any review to see its clause split, aspect sentiment and raw API
   response. **Submit as feedback** sends it through the same stream.
5. **Model & data:** baselines, confusion matrices, real errors, the challenge set, the
   cross-dataset check, data-quality results and live API latency.

**Reset** (next to Replay) deletes the live and replayed events and goes back to the batch data.

## The data

**Dashboard data: the PulseIQ Dataset Pack** (synthetic, `data/raw/`). It drives the app and
sets the label contract: 10 aspects, 7 emotions and 10 intents from its taxonomy files. The
pipeline's quality checks report what the pack contains rather than hiding it:

* 20,000 rows but only 900 unique texts (about 9 sentence templates × 10 products × 10 aspects).
* Every timestamp is midnight, so trends are daily, not hourly.
* 75% of rows pair a city with another country (Lagos, United States), so city and country filters disagree.
* The same text carries different emotion labels (2.3 on average), and intent is derived from the
  aspect (a happy delivery review is labeled `delivery_issue`).
* The negative rate is flat over 21 months. The stream file (Oct 1–5) is more negative, which is
  what makes the live demo raise an alert.

**Training data: a seeded synthetic corpus** (`data/training/`, 18,000 rows, 15,977 unique texts).
As the pack's README says, its demo files aren't meant for genuine training, so the models learn
from a separate generator written in the pack's taxonomy. It has 1–3 aspects per review with their
own opinions, contrast words, emotion and intent cues, sarcasm, very short reviews, typos,
Nigerian-English expressions, plain factual statements and star ratings with real-world noise.
Sentiment comes from the rating (1–2 negative, 3 neutral, 4–5 positive), as in public review
datasets. Duplicate texts are dropped before the 70/15/15 split, so no text sits in two splits.

**Challenge set** (`data/samples/challenge_set.csv`): 60 hard cases written by hand and
separately from the generator, covering negation, sarcasm, mixed opinions, short texts, typos,
domain slang, implicit aspects and questions. This is the "small evaluation set you personally
inspect" from guide section 18.

All data is synthetic. It demonstrates the engineering, not real customer behaviour.

## Results

Held-out test set (2,397 reviews). For each task the candidate with the higher **validation**
macro-F1 is deployed. The richer model is not assumed to win.

| Task | Rule-based lexicon | TF-IDF baseline | Word+char model | Deployed |
| --- | --- | --- | --- | --- |
| Sentiment (macro-F1) | 0.695 | 0.918 | **0.926** | word+char |
| Emotion (macro-F1) | — | **0.831** | 0.797 | baseline |
| Intent (macro-F1) | — | 0.842 | 0.830 | word+char (won on validation, 0.855 vs 0.829) |

* **Aspect detection** (test): F1 0.982 (precision 0.988, recall 0.976). Sentiment is right for
  92.8% of correctly detected aspects. The keywords share vocabulary with the generator, so this is optimistic.
* **Challenge set** (deployed models): sentiment 75%, emotion 58%, intent 58%, aspect
  detection F1 0.83. Weakest categories: written-out negation (2/5) and mixed opinions (3/6).
* **Where it fails** (test error rate): mixed reviews 20%, sarcasm 13%, typos 9%, plain reviews
  2%. "Rating mismatch" reviews (56%) have stars that contradict the text, so the label is wrong, not the model.
* **Cross-dataset check on the pack** (never trained on): sentiment macro-F1 0.73 on its 900
  unique texts. Emotion agreement is 44% against a ceiling of 56%: no model can do better,
  because identical texts carry different labels. Intent agreement is 12% against a 66% ceiling,
  because the pack derives intent from the aspect. Every primary aspect is detected.

**Transparency note on the pack score.** The first cross-check scored 0.49. The model read plain
statements ("I used X today and completed a transaction involving refund") as negative, because
the training corpus had almost no opinion-free text and aspect words like "refund" appeared almost
only in complaints. The generator gained factual and "this is about X" statements written in its
own words, not copied from the pack. That lifted the score to 0.73, so the pack is no longer a
fully blind test. A residual error remains: "I had a great experience…" lands on neutral, because
the sarcasm templates taught the model that "great" is ambiguous.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness + model version |
| POST | `/api/v1/analyze` | One text → sentiment, emotion, intent, topics, aspects, entities, clauses (guide response shape) |
| POST | `/api/v1/batch` | Up to 500 texts → results + summary (nothing stored) |
| GET | `/api/v1/metrics/sentiment` · `/topics` · `/emotions` · `/intents` | Period metrics with the previous period for comparison |
| GET | `/api/v1/trends?granularity=day\|week&aspect=` | Time series, optionally with one aspect |
| GET | `/api/v1/alerts` | Last 7 days vs the previous 28, overall and per aspect, with drivers and actions |
| GET | `/api/v1/issues/{aspect}` | Trend, segments, evidence, findings, recommended action |
| GET | `/api/v1/feedback` · `/feedback/{id}` | Search and inspect reviews |
| POST | `/api/v1/feedback` | Live feedback → event stream (202) |
| GET | `/api/v1/themes` | NMF themes in negative feedback (unsupervised discovery) |
| GET | `/api/v1/stream/status` · `/stream/recent` | Data version, queue depth, recent event traces |
| POST | `/api/v1/stream/replay` · `/stop` · `/reset` | Replay the pack's event file; reset to the batch data |
| GET | `/api/v1/model` · `/quality` · `/filters` | Metrics and metadata, data-quality report, filter options |

Every analytics endpoint takes the same filters: `days` (or `all=true`), `product`, `channel`,
`country` and `city`. Inputs are validated (text 1–2,000 characters, batch ≤ 500), and write and
inference endpoints are rate-limited per client (120 requests a minute). Per-route request counts,
5xx errors and p50/p95 latency are shown on the Model page.

## Deliberate choices

* **Alert rule:** the negative rate must rise at least 8 points, at least 20% relative, with a
  two-proportion z-score of at least 2, on at least 15 mentions. A segment is named as "where it's
  concentrated" only if it holds 25% or more of the negatives. Smaller over-representations are
  listed as leads to check.
* **Issue windows are fixed** (7 vs 28 days), so the date-range filter applies to the other pages only.
* **Live feedback is timestamped now.** If the data ends more than 14 days before the wall clock
  (an old demo dataset), it is timestamped one minute after the latest review, so it still lands
  in the current window.
* **The guide's `aspects[]` and `aspect_sentiments[]` are merged** into one list of
  `{aspect, sentiment, score, evidence}` objects, so they can't drift apart.
* **Identical texts are analyzed once** in the batch pipeline (900 unique texts for 20,000 rows).
* **Findings are measured, not generated.** The Bedrock explanation layer (guide Phase 9) is an
  AWS phase. The issue page says so rather than faking it.

## Known limitations

* No transformer comparison yet (guide Phase 1's last step). The next step is a small fine-tuned
  DistilBERT or sentence-embedding model compared on the same splits and challenge set.
* Written-out negation and mixed opinions are the weakest cases. The negation marker reaches only 3 words.
* The intent taxonomy has no "general feedback" class, so opinion-free statements become `product_question`.
* The stream consumer is an in-process queue. State resets on restart unless `data/raw/live/`
  survives, and it is not horizontally scalable (Kinesis is the AWS answer).
* Render-style hosts have temporary disks: live events and replays reset on every deploy.

## Deploying (without AWS for now)

* **Frontend → Vercel:** set the root directory to `customer_pulse/frontend` and set
  `NEXT_PUBLIC_API_URL` to the backend URL (it's inlined at build time, so redeploy after changing it).
* **Backend → Render or similar:** set the root directory to `customer_pulse/backend`. The repo's
  `render.yaml` defines it. Build: `pip install -r requirements.txt`. Start:
  `uvicorn api.main:app --host 0.0.0.0 --port $PORT --forwarded-allow-ips='*'`. The last flag makes
  uvicorn trust Render's proxy headers, so the rate limit applies per visitor rather than to everyone
  at once. Health check: `/health`. Python 3.11. The API runs the pipeline on start-up when
  `data/processed/` is missing. In a clean-copy test that took 6.6 s, with memory peaking at
  about 325 MB (Render's free tier allows 512 MB). CORS always allows localhost and `*.vercel.app`;
  set `CORS_ORIGINS` for a custom domain.
* **Free tier sleeps** after about 15 idle minutes, so the first visit waits for a cold start and
  the dashboard shows "API offline" briefly. Live and replayed events reset on every restart.
* **Don't host the backend on Vercel:** the stream consumer thread and file writes need a long-running process.

## AWS path (next)

The local layout already mirrors the guide's design: `data/raw|processed|curated` map to
`s3://pulseiq-data/...` prefixes, `src/pipeline.py` to a Glue job, `curated/*.csv` to Athena
tables, `src/stream.py` to Kinesis → Lambda, and the API to App Runner or ECS behind CloudWatch.
The issue page's measured findings and evidence are the grounded context a Bedrock explanation
would use.
