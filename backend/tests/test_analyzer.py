"""The trained analyzer returns the stable output schema and handles the guide's examples."""
EXPECTED_FIELDS = {
    "sentiment_label", "sentiment_score", "sentiment_polarity", "sentiment_probabilities",
    "emotion", "emotion_score", "intent", "intent_score", "topics", "aspects", "entities",
    "model_version", "processed_at",
}


def test_output_schema_is_stable(analyzer):
    output = analyzer.analyze("Delivery was quick and the rider was polite.")
    assert set(output) == EXPECTED_FIELDS
    assert output["model_version"] == "pulseiq-nlp-v1"
    assert abs(sum(output["sentiment_probabilities"].values()) - 1) < 1e-3
    assert -1 <= output["sentiment_polarity"] <= 1


def test_guide_aspect_example(analyzer):
    """Guide Phase 3: one review, different opinions per aspect."""
    output = analyzer.analyze("The app looks great, but payment fails every time and support is slow.")
    assert output["sentiment_label"] == "negative"
    by_aspect = {aspect["aspect"]: aspect["sentiment"] for aspect in output["aspects"]}
    assert by_aspect == {"usability": "positive", "payment": "negative", "customer_support": "negative"}


def test_clear_cases(analyzer):
    assert analyzer.analyze("Love it, everything arrived early and the quality is excellent!")["sentiment_label"] == "positive"
    fraud = analyzer.analyze("Someone hacked my account and made purchases that were not mine. I'm scared.")
    assert fraud["sentiment_label"] == "negative"
    assert fraud["emotion"] == "fear"
    assert fraud["intent"] in {"fraud_report", "account_issue"}


def test_batch_matches_single(analyzer):
    texts = ["refund pls", "Prices are fair and the quality is solid."]
    batch = analyzer.analyze_texts(texts)
    assert [b["sentiment_label"] for b in batch] == [analyzer.analyze(t)["sentiment_label"] for t in texts]
