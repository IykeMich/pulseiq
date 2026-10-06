"""PulseAnalyzer: one review in, the stable PulseIQ output schema out (guide Phases 1-3).

    text -> sentiment (+ probability)   TF-IDF + logistic regression
         -> emotion, intent             separate classifiers, same recipe
         -> topics / aspects            taxonomy keywords per clause, sentiment per clause
         -> entities                    gazetteer lookup

Output fields (flat, so models can change without redesigning storage or the API):
    sentiment_label, sentiment_score, sentiment_polarity, sentiment_probabilities,
    emotion, emotion_score, intent, intent_score, topics[], aspects[], entities[],
    model_version, processed_at
`aspects` merges the guide's aspects[] and aspect_sentiments[] into one list of objects
({aspect, sentiment, score, evidence}), so an aspect and its sentiment can't drift apart.
"""
from datetime import datetime, timezone

import joblib
import numpy as np

from src.config import ARTIFACT_DIR, MODEL_VERSION
from src.preprocess import split_clauses
from src.taxonomy import ASPECTS, detect_aspects, detect_entities


def _probabilities(model, texts: list) -> tuple:
    """(class labels, probability matrix) for a fitted pipeline."""
    return list(model.classes_), model.predict_proba(texts)


class PulseAnalyzer:
    def __init__(self, sentiment_model, emotion_model, intent_model, model_version: str = MODEL_VERSION):
        self.sentiment_model = sentiment_model
        self.emotion_model = emotion_model
        self.intent_model = intent_model
        self.model_version = model_version

    @classmethod
    def load(cls, artifact_dir=None) -> "PulseAnalyzer":
        artifact_dir = artifact_dir or ARTIFACT_DIR
        return cls(
            joblib.load(artifact_dir / "sentiment.joblib"),
            joblib.load(artifact_dir / "emotion.joblib"),
            joblib.load(artifact_dir / "intent.joblib"),
        )

    def _sentiment(self, texts: list) -> list:
        labels, probs = _probabilities(self.sentiment_model, texts)
        positive, negative = labels.index("positive"), labels.index("negative")
        results = []
        for row in probs:
            best = int(np.argmax(row))
            results.append({
                "label": labels[best],
                "score": round(float(row[best]), 4),
                # Signed score in [-1, 1]: P(positive) - P(negative). Averages well over time.
                "polarity": round(float(row[positive] - row[negative]), 4),
                "probabilities": {label: round(float(p), 4) for label, p in zip(labels, row)},
            })
        return results

    @staticmethod
    def _top_label(model, texts: list) -> list:
        labels, probs = _probabilities(model, texts)
        return [(labels[int(np.argmax(row))], round(float(row.max()), 4)) for row in probs]

    def _aspects(self, texts: list) -> list:
        """Per review: aspects found clause by clause, each scored by the sentiment model."""
        clause_rows = []  # (review index, aspect, clause text)
        for review_index, text in enumerate(texts):
            for clause in split_clauses(text):
                for aspect in detect_aspects(clause):
                    clause_rows.append((review_index, aspect, clause))

        per_review = [dict() for _ in texts]
        if clause_rows:
            clause_sentiments = self._sentiment([clause for _, _, clause in clause_rows])
            for (review_index, aspect, clause), sentiment in zip(clause_rows, clause_sentiments):
                per_review[review_index].setdefault(aspect, []).append((clause, sentiment))

        results = []
        for found in per_review:
            aspects = []
            for aspect, mentions in found.items():
                # An aspect mentioned in several clauses: average the probabilities.
                labels = list(mentions[0][1]["probabilities"])
                mean = {label: float(np.mean([m[1]["probabilities"][label] for m in mentions])) for label in labels}
                label = max(mean, key=mean.get)
                strongest = max(mentions, key=lambda m: abs(m[1]["polarity"]))
                aspects.append({
                    "aspect": aspect,
                    "name": ASPECTS[aspect]["name"],
                    "sentiment": label,
                    "score": round(mean[label], 4),
                    "polarity": round(mean.get("positive", 0) - mean.get("negative", 0), 4),
                    "evidence": strongest[0],
                })
            results.append(aspects)
        return results

    def analyze_texts(self, texts: list) -> list:
        """Analyze many texts at once (vectorised); returns one output-schema dict per text."""
        texts = [str(text) for text in texts]
        if not texts:
            return []
        sentiments = self._sentiment(texts)
        emotions = self._top_label(self.emotion_model, texts)
        intents = self._top_label(self.intent_model, texts)
        aspects = self._aspects(texts)
        processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return [
            {
                "sentiment_label": sentiment["label"],
                "sentiment_score": sentiment["score"],
                "sentiment_polarity": sentiment["polarity"],
                "sentiment_probabilities": sentiment["probabilities"],
                "emotion": emotion[0],
                "emotion_score": emotion[1],
                "intent": intent[0],
                "intent_score": intent[1],
                "topics": [aspect["aspect"] for aspect in review_aspects],
                "aspects": review_aspects,
                "entities": detect_entities(text),
                "model_version": self.model_version,
                "processed_at": processed_at,
            }
            for text, sentiment, emotion, intent, review_aspects
            in zip(texts, sentiments, emotions, intents, aspects)
        ]

    def analyze(self, text: str) -> dict:
        return self.analyze_texts([text])[0]
