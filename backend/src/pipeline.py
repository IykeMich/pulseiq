"""Batch pipeline: raw -> processed -> curated (guide Phase 4, run locally).

Run from backend/:  python -m src.pipeline

  raw/         the dataset pack file, exactly as delivered (read only)
  processed/   reviews_enriched.jsonl: the review contract + model output, one line per review
  curated/     business-ready tables: daily_sentiment.csv, aspect_daily.csv, alerts.json,
               data_quality_report.json

The run is idempotent: it rebuilds processed/ and curated/ from raw/ every time, so running it
twice gives the same result. In AWS the same steps map to S3 prefixes and a Glue job.
"""
import json
from datetime import datetime, timezone

import pandas as pd

from src.analytics import FeedbackStore, Filters, compute_alerts
from src.analyzer import PulseAnalyzer
from src import config
from src.config import PACK_LABEL_COLUMNS, REVIEW_COLUMNS
from src.data import load_raw_feedback, quality_report, read_jsonl, write_jsonl


def build_record(raw: dict, output: dict, source: str) -> dict:
    """Join the review contract fields with the model output (the processed-zone schema)."""
    record = {column: raw.get(column) for column in REVIEW_COLUMNS}
    record["rating"] = None if pd.isna(record["rating"]) else int(record["rating"])
    labels = {column: raw[column] for column in PACK_LABEL_COLUMNS if column in raw and pd.notna(raw[column])}
    return {**record, **output, "source": source, "source_labels": labels or None}


def run_pipeline(analyzer: PulseAnalyzer = None) -> dict:
    analyzer = analyzer or PulseAnalyzer.load()
    raw = load_raw_feedback()
    report = quality_report(raw)

    # Identical texts get identical model output, so each unique text is analyzed once.
    unique_texts = raw.text.fillna("").drop_duplicates().tolist()
    outputs = dict(zip(unique_texts, analyzer.analyze_texts(unique_texts)))
    records = [build_record(row, outputs[row["text"] if isinstance(row["text"], str) else ""], "batch")
               for row in raw.to_dict("records")]
    write_jsonl(config.PROCESSED_PATH, records)

    write_curated(FeedbackStore(records))
    report["processed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["processed_rows"] = len(records)
    report["unique_texts_analyzed"] = len(unique_texts)
    report["model_version"] = analyzer.model_version
    config.QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.QUALITY_REPORT_PATH.write_text(json.dumps(report, indent=2))
    return report


def write_curated(store: FeedbackStore) -> None:
    """Daily aggregates by segment, the way Athena or Power BI would query them."""
    reviews, aspects = store.snapshot()
    config.CURATED_DIR.mkdir(parents=True, exist_ok=True)
    dimensions = ["date", "product", "channel", "country", "city"]
    daily = (
        reviews.assign(date=reviews.date.dt.strftime("%Y-%m-%d"))
        .groupby(dimensions)
        .agg(reviews=("review_id", "size"),
             negative=("sentiment_label", lambda s: int((s == "negative").sum())),
             neutral=("sentiment_label", lambda s: int((s == "neutral").sum())),
             positive=("sentiment_label", lambda s: int((s == "positive").sum())),
             avg_polarity=("sentiment_polarity", "mean"))
        .round(4).reset_index()
    )
    daily.to_csv(config.CURATED_DIR / "daily_sentiment.csv", index=False)
    aspect_daily = (
        aspects.assign(date=aspects.date.dt.strftime("%Y-%m-%d"))
        .groupby(["date", "aspect", "product", "channel", "country", "city"])
        .agg(mentions=("review_id", "size"),
             negative=("aspect_sentiment", lambda s: int((s == "negative").sum())),
             positive=("aspect_sentiment", lambda s: int((s == "positive").sum())))
        .reset_index()
    )
    aspect_daily.to_csv(config.CURATED_DIR / "aspect_daily.csv", index=False)
    (config.CURATED_DIR / "alerts.json").write_text(json.dumps(compute_alerts(store, Filters(days=None)), indent=2))


def load_processed() -> list:
    """Processed batch records, running the pipeline first if they don't exist yet."""
    if not config.PROCESSED_PATH.exists():
        run_pipeline()
    return read_jsonl(config.PROCESSED_PATH)


if __name__ == "__main__":
    result = run_pipeline()
    print(f"Processed {result['processed_rows']:,} reviews ({result['unique_texts_analyzed']:,} unique texts) "
          f"with {result['model_version']}")
    for check in result["checks"]:
        print(f"  [{check['status']:4s}] {check['check']}: {check['detail']}")
    print(f"Wrote {config.PROCESSED_PATH} and curated tables in {config.CURATED_DIR}")
