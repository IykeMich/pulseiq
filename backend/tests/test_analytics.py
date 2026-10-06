"""Metrics and the alert rule on a small hand-built dataset with a known spike."""
import pandas as pd

from src.analytics import FeedbackStore, Filters, compute_alerts, metrics_sentiment, metrics_topics, trends


def record(review_id, day, sentiment, aspect_sentiment, product="RideGo"):
    polarity = {"negative": -0.8, "neutral": 0.0, "positive": 0.8}
    return {
        "review_id": review_id, "customer_id": "c1", "timestamp": f"{day}T10:00:00Z", "text": "text",
        "rating": 3, "product": product, "channel": "web", "country": "Nigeria", "city": "Lagos",
        "language": "en", "sentiment_label": sentiment, "sentiment_score": 0.9,
        "sentiment_polarity": polarity[sentiment], "sentiment_probabilities": {}, "emotion": "neutral",
        "emotion_score": 0.5, "intent": "complaint", "intent_score": 0.5, "topics": ["payment"],
        "aspects": [{"aspect": "payment", "name": "Payment", "sentiment": aspect_sentiment, "score": 0.9,
                     "polarity": polarity[aspect_sentiment], "evidence": f"clause {review_id}"}],
        "entities": [], "model_version": "test", "processed_at": "", "source": "batch", "source_labels": None,
    }


def spike_store():
    """35 days at 20% negative payment mentions, then 7 days at 70%, mostly on one product."""
    records, number = [], 0
    for day in pd.date_range("2026-08-01", "2026-09-04"):
        for index in range(10):
            number += 1
            label = "negative" if index < 2 else "positive"
            records.append(record(f"r{number}", day.strftime("%Y-%m-%d"), label, label))
    for day in pd.date_range("2026-09-05", "2026-09-11"):
        for index in range(10):
            number += 1
            label = "negative" if index < 7 else "positive"
            product = "PayWave Mobile App" if label == "negative" else "RideGo"
            records.append(record(f"r{number}", day.strftime("%Y-%m-%d"), label, label, product))
    return FeedbackStore(records)


def test_sentiment_metrics_compare_with_previous_period():
    metrics = metrics_sentiment(spike_store(), Filters(days=7))
    assert metrics["as_of"] == "2026-09-11"
    assert metrics["current"]["negative_rate"] == 0.7
    assert metrics["previous"]["negative_rate"] == 0.2


def test_alert_fires_with_driver():
    alerts = compute_alerts(spike_store(), Filters())["alerts"]
    payment = next(alert for alert in alerts if alert["scope"] == "payment")
    assert payment["kind"] == "deterioration"
    assert payment["severity"] == "critical"
    assert payment["drivers"][0]["value"] == "PayWave Mobile App"
    assert "concentrated in PayWave Mobile App" in payment["headline"]


def test_no_alert_on_flat_data():
    records = [record(f"r{i}", day.strftime("%Y-%m-%d"), "negative" if i % 5 == 0 else "positive",
                      "negative" if i % 5 == 0 else "positive")
               for i, day in enumerate(d for d in pd.date_range("2026-08-01", "2026-09-11") for _ in range(10))]
    assert compute_alerts(FeedbackStore(records), Filters())["alerts"] == []


def test_filters_scope_metrics_and_trends():
    store = spike_store()
    only_paywave = Filters(product="PayWave Mobile App", days=7)
    assert metrics_sentiment(store, only_paywave)["current"]["negative_rate"] == 1.0
    topics = {row["aspect"]: row for row in metrics_topics(store, Filters(days=7))["topics"]}
    assert topics["payment"]["mentions"] == 70
    points = trends(store, Filters(days=7), "day", "payment")["points"]
    assert len(points) == 7 and points[-1]["aspect_negative_rate"] == 0.7
