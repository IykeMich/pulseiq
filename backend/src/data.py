"""Reading the raw zone and checking it against the review contract (guide Phases 0 and 4).

Raw files are read, never written: cleaning and enrichment happen on the way to processed/.
"""
import json

import pandas as pd

from src.config import CITY_COUNTRY, RAW_FEEDBACK_PATH, RAW_STREAM_PATH, REVIEW_COLUMNS
from src.taxonomy import PRODUCT_ENTITIES


def load_raw_feedback() -> pd.DataFrame:
    return pd.read_csv(RAW_FEEDBACK_PATH, dtype={"review_id": str, "customer_id": str})


def load_stream_events() -> pd.DataFrame:
    return pd.read_csv(RAW_STREAM_PATH, dtype=str)


def quality_report(raw: pd.DataFrame) -> dict:
    """Data-quality checks on the raw batch. Problems are reported, not silently fixed."""
    missing_columns = [column for column in REVIEW_COLUMNS if column not in raw.columns]
    text = raw.get("text", pd.Series(dtype=str)).fillna("")
    timestamps = pd.to_datetime(raw.get("timestamp"), errors="coerce")
    expected_country = raw.city.map(CITY_COUNTRY)
    country_mismatch = expected_country.notna() & (expected_country != raw.country)

    # Product named in the text vs the product column (the text is the customer's own words).
    lowered = text.str.lower()
    named_products = lowered.map(lambda value: [p for p in PRODUCT_ENTITIES if p.lower() in value])
    names_other_product = [
        bool(named) and product not in named for named, product in zip(named_products, raw["product"])
    ]

    checks = [
        {"check": "Required columns present", "status": "pass" if not missing_columns else "fail",
         "detail": "All contract columns found" if not missing_columns else f"Missing: {', '.join(missing_columns)}"},
        {"check": "Text present", "status": "pass" if (text.str.strip() == "").sum() == 0 else "fail",
         "detail": f"{int((text.str.strip() == '').sum())} empty texts"},
        {"check": "Unique review_id", "status": "pass" if raw.review_id.is_unique else "fail",
         "detail": f"{int(raw.review_id.duplicated().sum())} duplicate ids"},
        {"check": "Rating in 1-5", "status": "pass" if raw.rating.between(1, 5).all() else "fail",
         "detail": f"{int((~raw.rating.between(1, 5)).sum())} out of range"},
        {"check": "Timestamp parses", "status": "pass" if timestamps.notna().all() else "fail",
         "detail": f"{int(timestamps.isna().sum())} unparseable"},
        {"check": "Timestamp has time of day",
         "status": "warn" if (timestamps.dt.normalize() == timestamps).all() else "pass",
         "detail": "Every timestamp is midnight, so only daily (not hourly) trends are possible"
         if (timestamps.dt.normalize() == timestamps).all() else "Times of day present"},
        {"check": "City belongs to country", "status": "warn" if country_mismatch.any() else "pass",
         "detail": f"{int(country_mismatch.sum()):,} rows ({country_mismatch.mean():.0%}) pair a city with "
                   "another country, so city and country filters disagree"},
        {"check": "Product column matches the text", "status": "warn" if any(names_other_product) else "pass",
         "detail": f"{sum(names_other_product):,} rows ({sum(names_other_product) / len(raw):.0%}) name a "
                   "different product in the text than in the product column"},
        {"check": "Duplicate texts", "status": "warn" if text.nunique() < len(raw) * 0.5 else "pass",
         "detail": f"{text.nunique():,} unique texts in {len(raw):,} rows"},
    ]
    return {
        "source": RAW_FEEDBACK_PATH.name,
        "rows": int(len(raw)),
        "date_range": [str(timestamps.min().date()), str(timestamps.max().date())],
        "checks": checks,
    }


def write_jsonl(path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def append_jsonl(path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(record) + "\n")


def read_jsonl(path) -> list:
    if not path.exists():
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]
