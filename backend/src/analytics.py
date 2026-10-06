"""The intelligence layer (guide Phases 5-7): metrics, trends, alerts, issue drill-down and search.

Everything works on two in-memory tables held by FeedbackStore:
  reviews  one row per review (contract fields + model output)
  aspects  one row per (review, aspect) with that aspect's sentiment and evidence clause

Time windows end at `as_of`, the latest date in the data, so the demo data (which ends in the
past) behaves like a live system. Alerts compare the last 7 days with the 28 days before them.
"""
import math
import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.config import (
    ALERT_BASELINE_DAYS, ALERT_CURRENT_DAYS, ALERT_MIN_MENTIONS, ALERT_MIN_POINT_CHANGE,
    ALERT_MIN_RELATIVE_CHANGE, ALERT_MIN_Z, EMOTION_LABELS, INTENT_LABELS, SENTIMENT_LABELS,
)
from src.taxonomy import ASPECT_KEYS, ASPECTS, PLAYBOOK

DIMENSIONS = ["product", "channel", "country", "city"]
REVIEW_FIELDS = [
    "review_id", "customer_id", "timestamp", "text", "rating", "product", "channel", "country",
    "city", "language", "sentiment_label", "sentiment_score", "sentiment_polarity",
    "sentiment_probabilities", "emotion", "emotion_score", "intent", "intent_score", "topics",
    "aspects", "entities", "model_version", "processed_at", "source", "source_labels",
]


# ---------------------------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------------------------

def to_frames(records: list) -> tuple:
    """Records (processed JSONL rows) -> (reviews, aspects) DataFrames."""
    reviews = pd.DataFrame(records, columns=REVIEW_FIELDS)
    moments = pd.to_datetime(reviews.timestamp, utc=True, format="ISO8601").dt.tz_localize(None)
    reviews["date"] = moments.dt.normalize()
    reviews["moment"] = moments
    for dimension in DIMENSIONS:
        reviews[dimension] = reviews[dimension].fillna("Unknown")
    aspect_rows = [
        {"review_id": review["review_id"], "aspect": aspect["aspect"], "aspect_sentiment": aspect["sentiment"],
         "aspect_polarity": aspect["polarity"], "evidence": aspect["evidence"], "aspect_score": aspect["score"]}
        for review in records for aspect in review["aspects"]
    ]
    aspects = pd.DataFrame(
        aspect_rows,
        columns=["review_id", "aspect", "aspect_sentiment", "aspect_polarity", "evidence", "aspect_score"],
    )
    context = reviews[["review_id", "date", "moment", "source", *DIMENSIONS]]
    aspects = aspects.merge(context, on="review_id", how="left")
    return reviews, aspects


class FeedbackStore:
    """Holds the two tables. Appends build new frames and swap them in, so a reader that took a
    snapshot keeps a consistent view while the stream processor adds rows."""

    def __init__(self, records: list):
        self._lock = threading.Lock()
        self.reviews, self.aspects = to_frames(records)
        self.version = 0

    def append(self, records: list) -> None:
        new_reviews, new_aspects = to_frames(records)
        with self._lock:
            self.reviews = pd.concat([self.reviews, new_reviews], ignore_index=True)
            self.aspects = pd.concat([self.aspects, new_aspects], ignore_index=True)
            self.version += 1

    def snapshot(self) -> tuple:
        with self._lock:
            return self.reviews, self.aspects

    def as_of(self) -> pd.Timestamp:
        return self.reviews.date.max()


# ---------------------------------------------------------------------------------------------
# Filters and windows
# ---------------------------------------------------------------------------------------------

@dataclass
class Filters:
    product: Optional[str] = None
    channel: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    days: Optional[int] = 30  # None = all data


def apply_dimensions(frame: pd.DataFrame, filters: Filters) -> pd.DataFrame:
    for dimension in DIMENSIONS:
        value = getattr(filters, dimension)
        if value:
            frame = frame[frame[dimension] == value]
    return frame


def windows(as_of: pd.Timestamp, days: Optional[int], first_date: pd.Timestamp) -> dict:
    """Current period [start, as_of] and the equal-length period before it."""
    if days is None:
        return {"start": first_date, "end": as_of, "previous": None}
    start = as_of - pd.Timedelta(days=days - 1)
    return {
        "start": start,
        "end": as_of,
        "previous": (start - pd.Timedelta(days=days), start - pd.Timedelta(days=1)),
    }


def between(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    return frame[(frame.date >= start) & (frame.date <= end)]


def iso(day) -> str:
    return pd.Timestamp(day).strftime("%Y-%m-%d")


def rate(part: int, whole: int) -> Optional[float]:
    return round(part / whole, 4) if whole else None


def sentiment_stats(frame: pd.DataFrame) -> dict:
    counts = frame.sentiment_label.value_counts()
    total = int(len(frame))
    return {
        "reviews": total,
        **{label: int(counts.get(label, 0)) for label in SENTIMENT_LABELS},
        "negative_rate": rate(int(counts.get("negative", 0)), total),
        "positive_rate": rate(int(counts.get("positive", 0)), total),
        "avg_polarity": round(float(frame.sentiment_polarity.mean()), 4) if total else None,
    }


def _scoped(store: FeedbackStore, filters: Filters) -> tuple:
    reviews, aspects = store.snapshot()
    as_of = reviews.date.max()
    span = windows(as_of, filters.days, reviews.date.min())
    return apply_dimensions(reviews, filters), apply_dimensions(aspects, filters), as_of, span


def _period_info(span: dict, filters: Filters) -> dict:
    return {"start": iso(span["start"]), "end": iso(span["end"]), "days": filters.days}


# ---------------------------------------------------------------------------------------------
# Metrics (GET /api/v1/metrics/*)
# ---------------------------------------------------------------------------------------------

def metrics_sentiment(store: FeedbackStore, filters: Filters) -> dict:
    reviews, _, as_of, span = _scoped(store, filters)
    current = sentiment_stats(between(reviews, span["start"], span["end"]))
    previous = sentiment_stats(between(reviews, *span["previous"])) if span["previous"] else None
    return {
        "as_of": iso(as_of),
        "period": _period_info(span, filters),
        "current": current,
        "previous": previous,
    }


def _aspect_table(aspects: pd.DataFrame, review_count: int) -> dict:
    table = {}
    for aspect in ASPECT_KEYS:
        rows = aspects[aspects.aspect == aspect]
        counts = rows.aspect_sentiment.value_counts()
        mentions = int(len(rows))
        table[aspect] = {
            "mentions": mentions,
            "negative": int(counts.get("negative", 0)),
            "neutral": int(counts.get("neutral", 0)),
            "positive": int(counts.get("positive", 0)),
            "negative_rate": rate(int(counts.get("negative", 0)), mentions),
            "net_sentiment": round(float(rows.aspect_polarity.mean()), 4) if mentions else None,
            "share_of_reviews": rate(mentions, review_count),
        }
    return table


def metrics_topics(store: FeedbackStore, filters: Filters) -> dict:
    reviews, aspects, as_of, span = _scoped(store, filters)
    current_reviews = between(reviews, span["start"], span["end"])
    current = _aspect_table(between(aspects, span["start"], span["end"]), len(current_reviews))
    previous = None
    if span["previous"]:
        previous = _aspect_table(between(aspects, *span["previous"]), len(between(reviews, *span["previous"])))
    rows = []
    for aspect in ASPECT_KEYS:
        row = {"aspect": aspect, "name": ASPECTS[aspect]["name"], **current[aspect]}
        before = previous[aspect]["negative_rate"] if previous else None
        row["previous_negative_rate"] = before
        row["negative_rate_change"] = (
            round(row["negative_rate"] - before, 4) if before is not None and row["negative_rate"] is not None else None
        )
        rows.append(row)
    rows.sort(key=lambda row: row["negative"], reverse=True)
    return {"as_of": iso(as_of), "period": _period_info(span, filters), "topics": rows}


def metrics_distribution(store: FeedbackStore, filters: Filters, column: str) -> dict:
    """Share of each emotion (or intent) in the period, with the previous period's share."""
    labels = EMOTION_LABELS if column == "emotion" else INTENT_LABELS
    reviews, _, as_of, span = _scoped(store, filters)
    current = between(reviews, span["start"], span["end"])
    previous = between(reviews, *span["previous"]) if span["previous"] else None
    current_counts = current[column].value_counts()
    previous_counts = previous[column].value_counts() if previous is not None else None
    rows = [
        {
            "label": label,
            "count": int(current_counts.get(label, 0)),
            "share": rate(int(current_counts.get(label, 0)), len(current)),
            "previous_share": rate(int(previous_counts.get(label, 0)), len(previous))
            if previous is not None else None,
        }
        for label in labels
    ]
    rows.sort(key=lambda row: row["count"], reverse=True)
    return {"as_of": iso(as_of), "period": _period_info(span, filters), "items": rows}


# ---------------------------------------------------------------------------------------------
# Trends (GET /api/v1/trends)
# ---------------------------------------------------------------------------------------------

def trends(store: FeedbackStore, filters: Filters, granularity: str = "day", aspect: Optional[str] = None) -> dict:
    reviews, aspects, as_of, span = _scoped(store, filters)
    current = between(reviews, span["start"], span["end"])
    frequency = "D" if granularity == "day" else "W-MON"

    def bucket(frame: pd.DataFrame) -> pd.Series:
        if granularity == "day":
            return frame.date
        return frame.date.dt.to_period("W-SUN").dt.start_time

    if granularity == "day":
        index = pd.date_range(span["start"], span["end"], freq="D")
    else:
        index = pd.date_range(
            pd.Timestamp(span["start"]).to_period("W-SUN").start_time, span["end"], freq=frequency
        )
    grouped = current.groupby(bucket(current))
    counts = grouped.sentiment_label.value_counts().unstack(fill_value=0).reindex(index, fill_value=0)
    polarity = grouped.sentiment_polarity.mean().reindex(index)

    aspect_counts = None
    if aspect:
        scoped = between(aspects[aspects.aspect == aspect], span["start"], span["end"])
        aspect_counts = (
            scoped.groupby(bucket(scoped)).aspect_sentiment.value_counts().unstack(fill_value=0).reindex(index, fill_value=0)
        )

    points = []
    for period in index:
        row = counts.loc[period]
        total = int(row.sum())
        point = {
            "period": iso(period),
            "reviews": total,
            **{label: int(row.get(label, 0)) for label in SENTIMENT_LABELS},
            "negative_rate": rate(int(row.get("negative", 0)), total),
            "positive_rate": rate(int(row.get("positive", 0)), total),
            "avg_polarity": None if pd.isna(polarity.loc[period]) else round(float(polarity.loc[period]), 4),
        }
        if aspect_counts is not None:
            aspect_row = aspect_counts.loc[period]
            mentions = int(aspect_row.sum())
            point["aspect_mentions"] = mentions
            point["aspect_negative_rate"] = rate(int(aspect_row.get("negative", 0)), mentions)
        points.append(point)
    return {
        "as_of": iso(as_of),
        "period": _period_info(span, filters),
        "granularity": granularity,
        "aspect": aspect,
        "points": points,
    }


# ---------------------------------------------------------------------------------------------
# Alerts (GET /api/v1/alerts)
# ---------------------------------------------------------------------------------------------

def alert_windows(as_of: pd.Timestamp) -> dict:
    current_start = as_of - pd.Timedelta(days=ALERT_CURRENT_DAYS - 1)
    baseline_end = current_start - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=ALERT_BASELINE_DAYS - 1)
    return {"current": (current_start, as_of), "baseline": (baseline_start, baseline_end)}


def two_proportion_z(hits_a: int, n_a: int, hits_b: int, n_b: int) -> float:
    """z-score for rate A > rate B (pooled two-proportion test)."""
    if not n_a or not n_b:
        return 0.0
    pooled = (hits_a + hits_b) / (n_a + n_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    return 0.0 if spread == 0 else (hits_a / n_a - hits_b / n_b) / spread


def driver_segments(current_negative: pd.DataFrame, baseline_negative: pd.DataFrame, limit: int = 3) -> list:
    """Segments over-represented among current negatives compared with the baseline's negatives."""
    drivers = []
    for dimension in ["product", "channel", "city", "country"]:
        current_share = current_negative[dimension].value_counts(normalize=True)
        baseline_share = baseline_negative[dimension].value_counts(normalize=True)
        current_count = current_negative[dimension].value_counts()
        for value, share in current_share.items():
            if value == "Unknown" or current_count[value] < 5:
                continue
            before = float(baseline_share.get(value, 0.0))
            drivers.append({
                "dimension": dimension, "value": value,
                "share_of_negatives": round(float(share), 4),
                "baseline_share_of_negatives": round(before, 4),
                "lift": round(float(share) - before, 4),
                "negative_mentions": int(current_count[value]),
            })
    drivers.sort(key=lambda driver: driver["lift"], reverse=True)
    return [driver for driver in drivers if driver["lift"] > 0.05][:limit]


def _evaluate_scope(scope: str, name: str, current: pd.DataFrame, baseline: pd.DataFrame,
                    sentiment_column: str, as_of) -> Optional[dict]:
    current_n, baseline_n = len(current), len(baseline)
    if current_n < ALERT_MIN_MENTIONS or baseline_n < ALERT_MIN_MENTIONS:
        return None
    current_negative = current[current[sentiment_column] == "negative"]
    baseline_negative = baseline[baseline[sentiment_column] == "negative"]
    current_rate = len(current_negative) / current_n
    baseline_rate = len(baseline_negative) / baseline_n
    change = current_rate - baseline_rate
    relative = change / baseline_rate if baseline_rate else float("inf")
    z = two_proportion_z(len(current_negative), current_n, len(baseline_negative), baseline_n)

    if change >= ALERT_MIN_POINT_CHANGE and relative >= ALERT_MIN_RELATIVE_CHANGE and z >= ALERT_MIN_Z:
        kind = "deterioration"
        severity = "critical" if change >= 0.25 else ("high" if change >= 0.15 else "medium")
    elif change <= -ALERT_MIN_POINT_CHANGE and z <= -ALERT_MIN_Z:
        kind, severity = "improvement", "info"
    else:
        return None

    drivers = driver_segments(current_negative, baseline_negative) if kind == "deterioration" else []
    direction = "rose" if kind == "deterioration" else "fell"
    headline = (
        f"Negative {name.lower()} sentiment {direction} from {baseline_rate:.0%} to {current_rate:.0%} "
        f"({change * 100:+.0f} pts, {relative:+.0%}) in the last {ALERT_CURRENT_DAYS} days"
    )
    # Only call a segment the concentration point when it holds a real share of the negatives;
    # a jump from 0% to 10% is a lead to check, not "where the problem is".
    concentrated = [driver for driver in drivers if driver["share_of_negatives"] >= 0.25]
    if concentrated:
        top = concentrated[0]
        headline += (f", concentrated in {top['value']} ({top['share_of_negatives']:.0%} of negative "
                     f"mentions vs {top['baseline_share_of_negatives']:.0%} before)")
    elif kind == "deterioration":
        headline += ", spread across segments"
    return {
        "id": f"{scope}-{iso(as_of)}",
        "scope": scope,
        "name": name,
        "kind": kind,
        "severity": severity,
        "headline": headline + ".",
        "current": {"mentions": current_n, "negative": len(current_negative), "negative_rate": round(current_rate, 4)},
        "baseline": {"mentions": baseline_n, "negative": len(baseline_negative), "negative_rate": round(baseline_rate, 4)},
        "point_change": round(change, 4),
        "relative_change": round(relative, 4) if math.isfinite(relative) else None,
        "z_score": round(z, 2),
        "drivers": drivers,
        "action": PLAYBOOK.get(scope),
    }


def compute_alerts(store: FeedbackStore, filters: Filters) -> dict:
    """Current 7-day negative rate vs the previous 28 days, overall and per aspect (guide Phase 7)."""
    reviews, aspects = store.snapshot()
    as_of = reviews.date.max()
    span = alert_windows(as_of)
    reviews, aspects = apply_dimensions(reviews, filters), apply_dimensions(aspects, filters)
    found = []
    overall = _evaluate_scope("overall", "Overall", between(reviews, *span["current"]),
                              between(reviews, *span["baseline"]), "sentiment_label", as_of)
    if overall:
        overall["action"] = "Open the aspects with the largest increase to find the driver."
        found.append(overall)
    for aspect in ASPECT_KEYS:
        rows = aspects[aspects.aspect == aspect]
        alert = _evaluate_scope(aspect, ASPECTS[aspect]["name"], between(rows, *span["current"]),
                                between(rows, *span["baseline"]), "aspect_sentiment", as_of)
        if alert:
            found.append(alert)
    order = {"critical": 0, "high": 1, "medium": 2, "info": 3}
    found.sort(key=lambda alert: (order[alert["severity"]], -abs(alert["point_change"])))
    return {
        "as_of": iso(as_of),
        "current_window": [iso(day) for day in span["current"]],
        "baseline_window": [iso(day) for day in span["baseline"]],
        "rules": {
            "min_mentions": ALERT_MIN_MENTIONS, "min_point_change": ALERT_MIN_POINT_CHANGE,
            "min_relative_change": ALERT_MIN_RELATIVE_CHANGE, "min_z": ALERT_MIN_Z,
        },
        "alerts": found,
    }


# ---------------------------------------------------------------------------------------------
# Issue detail (GET /api/v1/issues/{aspect})
# ---------------------------------------------------------------------------------------------

def segment_breakdown(current: pd.DataFrame, baseline: pd.DataFrame, dimension: str) -> list:
    rows = []
    for value in sorted(set(current[dimension]) | set(baseline[dimension])):
        now = current[current[dimension] == value]
        before = baseline[baseline[dimension] == value]
        now_negative = int((now.aspect_sentiment == "negative").sum())
        rows.append({
            "value": value,
            "mentions": int(len(now)),
            "negative": now_negative,
            "negative_rate": rate(now_negative, len(now)),
            "baseline_negative_rate": rate(int((before.aspect_sentiment == "negative").sum()), len(before)),
        })
    rows.sort(key=lambda row: row["negative"], reverse=True)
    return rows


def issue_detail(store: FeedbackStore, aspect: str, filters: Filters) -> dict:
    """Everything an analyst needs for one aspect: trend, segments, evidence, findings, action."""
    reviews, aspects = store.snapshot()
    as_of = reviews.date.max()
    span = alert_windows(as_of)
    reviews, aspects = apply_dimensions(reviews, filters), apply_dimensions(aspects, filters)
    rows = aspects[aspects.aspect == aspect]
    current = between(rows, *span["current"])
    baseline = between(rows, *span["baseline"])

    # 90-day daily trend with a 7-day rolling negative rate (smooths the daily noise).
    trend_start = as_of - pd.Timedelta(days=89)
    recent = between(rows, trend_start, as_of)
    index = pd.date_range(trend_start, as_of, freq="D")
    daily = recent.groupby("date").aspect_sentiment.value_counts().unstack(fill_value=0).reindex(index, fill_value=0)
    negative = daily.get("negative", pd.Series(0, index=index))
    total = daily.sum(axis=1)
    rolling_rate = negative.rolling(7, min_periods=1).sum() / total.rolling(7, min_periods=1).sum().replace(0, np.nan)
    trend = [
        {"period": iso(day), "mentions": int(total.loc[day]), "negative": int(negative.loc[day]),
         "negative_rate_7d": None if pd.isna(rolling_rate.loc[day]) else round(float(rolling_rate.loc[day]), 4)}
        for day in index
    ]

    current_negative = current[current.aspect_sentiment == "negative"]
    evidence = (
        current_negative.sort_values(["moment", "aspect_score"], ascending=False)
        .drop_duplicates("evidence").head(8)
    )
    review_lookup = reviews.set_index("review_id")
    evidence_rows = [
        {
            "review_id": row.review_id, "date": iso(row.date), "evidence": row.evidence,
            "text": review_lookup.at[row.review_id, "text"], "product": row.product,
            "channel": row.channel, "city": row.city, "confidence": row.aspect_score,
        }
        for row in evidence.itertuples()
    ]

    negative_reviews = reviews[reviews.review_id.isin(current_negative.review_id)]
    alert = next(
        (item for item in compute_alerts(store, filters)["alerts"] if item["scope"] == aspect), None
    )
    current_rate = rate(len(current_negative), len(current))
    baseline_rate = rate(int((baseline.aspect_sentiment == "negative").sum()), len(baseline))

    # Measured findings: every sentence is computed from the data, none is generated.
    findings = []
    if current_rate is not None and baseline_rate is not None:
        findings.append(
            f"{len(current_negative)} of {len(current)} {ASPECTS[aspect]['name'].lower()} mentions in the last "
            f"{ALERT_CURRENT_DAYS} days were negative ({current_rate:.0%}), against {baseline_rate:.0%} in the "
            f"previous {ALERT_BASELINE_DAYS} days."
        )
    drivers = driver_segments(current_negative, baseline[baseline.aspect_sentiment == "negative"])
    for driver in drivers:
        findings.append(
            f"{driver['dimension'].title()} {driver['value']} accounts for {driver['share_of_negatives']:.0%} "
            f"of negative mentions, up from {driver['baseline_share_of_negatives']:.0%}."
        )
    if len(negative_reviews):
        top_emotion = negative_reviews.emotion.value_counts()
        top_intent = negative_reviews.intent.value_counts()
        findings.append(
            f"Most common emotion in these reviews: {top_emotion.index[0]} ({top_emotion.iloc[0] / len(negative_reviews):.0%}); "
            f"most common intent: {top_intent.index[0].replace('_', ' ')} ({top_intent.iloc[0] / len(negative_reviews):.0%})."
        )

    return {
        "aspect": aspect,
        "name": ASPECTS[aspect]["name"],
        "as_of": iso(as_of),
        "current_window": [iso(day) for day in span["current"]],
        "baseline_window": [iso(day) for day in span["baseline"]],
        "current": {"mentions": int(len(current)), "negative": int(len(current_negative)), "negative_rate": current_rate},
        "baseline": {"mentions": int(len(baseline)), "negative_rate": baseline_rate},
        "alert": alert,
        "trend": trend,
        "segments": {dimension: segment_breakdown(current, baseline, dimension) for dimension in DIMENSIONS},
        "emotions": {k: int(v) for k, v in negative_reviews.emotion.value_counts().items()},
        "intents": {k: int(v) for k, v in negative_reviews.intent.value_counts().items()},
        "evidence": evidence_rows,
        "findings": findings,
        "recommended_action": PLAYBOOK[aspect],
    }


# ---------------------------------------------------------------------------------------------
# Feedback explorer (GET /api/v1/feedback)
# ---------------------------------------------------------------------------------------------

def _public(row: dict) -> dict:
    """A review row as JSON-safe output (drops the helper date columns)."""
    return {key: value for key, value in row.items() if key not in {"date", "moment"}}


def search_feedback(store: FeedbackStore, filters: Filters, search: str = "", sentiment: str = "",
                    aspect: str = "", emotion: str = "", intent: str = "", source: str = "",
                    page: int = 1, page_size: int = 20) -> dict:
    reviews, aspects, as_of, span = _scoped(store, filters)
    matches = between(reviews, span["start"], span["end"])
    if sentiment:
        matches = matches[matches.sentiment_label == sentiment]
    if emotion:
        matches = matches[matches.emotion == emotion]
    if intent:
        matches = matches[matches.intent == intent]
    if source:
        matches = matches[matches.source == source]
    if aspect:
        matches = matches[matches.topics.map(lambda topics: aspect in topics)]
    if search.strip():
        term = search.strip().lower()
        matches = matches[
            matches.text.str.lower().str.contains(term, regex=False)
            | matches.review_id.str.lower().str.startswith(term)
        ]
    matches = matches.sort_values(["moment", "review_id"], ascending=False)
    start = (page - 1) * page_size
    return {
        "total": int(len(matches)),
        "page": page,
        "page_size": page_size,
        "items": [_public(row) for row in matches.iloc[start:start + page_size].to_dict("records")],
    }


def review_detail(store: FeedbackStore, review_id: str) -> Optional[dict]:
    reviews, _ = store.snapshot()
    rows = reviews[reviews.review_id == review_id]
    if rows.empty:
        return None
    return _public(rows.iloc[-1].to_dict())


# ---------------------------------------------------------------------------------------------
# Unsupervised theme discovery (GET /api/v1/themes)
# ---------------------------------------------------------------------------------------------

def discover_themes(store: FeedbackStore, filters: Filters, n_themes: int = 5) -> dict:
    """NMF over TF-IDF of negative reviews in the period: surfaces themes outside the taxonomy."""
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer

    reviews, _, as_of, span = _scoped(store, filters)
    negative = between(reviews, span["start"], span["end"])
    negative = negative[negative.sentiment_label == "negative"].drop_duplicates("text")
    if len(negative) < n_themes * 3:
        return {"as_of": iso(as_of), "period": _period_info(span, filters), "reviews": int(len(negative)), "themes": []}
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_df=0.6)
    matrix = vectorizer.fit_transform(negative.text)
    model = NMF(n_components=n_themes, random_state=0, init="nndsvd", max_iter=400)
    weights = model.fit_transform(matrix)
    terms = np.array(vectorizer.get_feature_names_out())
    assignment = weights.argmax(axis=1)
    themes = []
    for index, component in enumerate(model.components_):
        members = negative[assignment == index]
        if members.empty:
            continue
        uncovered = float((members.topics.map(len) == 0).mean())
        themes.append({
            "terms": terms[component.argsort()[::-1][:6]].tolist(),
            "reviews": int(len(members)),
            "outside_taxonomy_share": round(uncovered, 4),
            "examples": members.text.head(3).tolist(),
        })
    themes.sort(key=lambda theme: theme["reviews"], reverse=True)
    return {"as_of": iso(as_of), "period": _period_info(span, filters), "reviews": int(len(negative)), "themes": themes}


def filter_options(store: FeedbackStore) -> dict:
    reviews, _ = store.snapshot()
    return {
        **{dimension: sorted(value for value in reviews[dimension].unique() if value != "Unknown")
           for dimension in DIMENSIONS},
        "aspects": [{"key": key, "name": ASPECTS[key]["name"]} for key in ASPECT_KEYS],
        "sentiments": SENTIMENT_LABELS,
        "emotions": EMOTION_LABELS,
        "intents": INTENT_LABELS,
        "date_range": [iso(reviews.date.min()), iso(reviews.date.max())],
    }
