"""Evaluation helpers (guide Phase 1 and section 18): metrics, aspect scoring, challenge and pack checks.

Everything returns plain dicts/lists so train.py can write them straight into artifacts/metrics.json,
which the API serves to the dashboard's Model page.
"""
import json
from collections import Counter

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from src.taxonomy import ASPECT_KEYS


def classification_summary(y_true, y_pred, labels: list) -> dict:
    """Accuracy, macro and weighted P/R/F1, per-class scores and the confusion matrix."""
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    macro = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    weighted = precision_recall_fscore_support(y_true, y_pred, labels=labels, average="weighted", zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(float(macro[0]), 4),
        "macro_recall": round(float(macro[1]), 4),
        "macro_f1": round(float(macro[2]), 4),
        "weighted_f1": round(float(weighted[2]), 4),
        "support": int(len(y_true)),
        "per_class": {
            label: {"precision": round(float(p), 4), "recall": round(float(r), 4),
                    "f1": round(float(f), 4), "support": int(s)}
            for label, p, r, f, s in zip(labels, precision, recall, f1, support)
        },
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        },
    }


def aspect_scores(true_aspects: list, predicted_aspects: list) -> dict:
    """Aspect detection precision/recall/F1 (micro and per aspect) and aspect-sentiment accuracy.

    Both arguments are lists (one per review) of [{"aspect": ..., "sentiment": ...}, ...].
    Sentiment accuracy is measured on aspects that were detected correctly.
    """
    counts = {aspect: Counter() for aspect in ASPECT_KEYS}
    sentiment_hits, sentiment_total = 0, 0
    for truth, predicted in zip(true_aspects, predicted_aspects):
        true_map = {item["aspect"]: item["sentiment"] for item in truth}
        predicted_map = {item["aspect"]: item["sentiment"] for item in predicted}
        for aspect in ASPECT_KEYS:
            in_truth, in_prediction = aspect in true_map, aspect in predicted_map
            if in_truth and in_prediction:
                counts[aspect]["tp"] += 1
                sentiment_total += 1
                sentiment_hits += true_map[aspect] == predicted_map[aspect]
            elif in_prediction:
                counts[aspect]["fp"] += 1
            elif in_truth:
                counts[aspect]["fn"] += 1

    def prf(counter: Counter) -> dict:
        tp, fp, fn = counter["tp"], counter["fp"], counter["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
                "support": tp + fn}

    total = sum(counts.values(), Counter())
    return {
        "detection": prf(total),
        "per_aspect": {aspect: prf(counter) for aspect, counter in counts.items()},
        "sentiment_accuracy": round(sentiment_hits / sentiment_total, 4) if sentiment_total else None,
        "sentiment_evaluated": sentiment_total,
    }


def parse_aspect_string(value) -> list:
    """"payment:negative;refund:neutral" -> [{"aspect": "payment", "sentiment": "negative"}, ...]."""
    if not isinstance(value, str) or not value.strip():
        return []
    return [
        {"aspect": part.split(":")[0].strip(), "sentiment": part.split(":")[1].strip()}
        for part in value.split(";") if ":" in part
    ]


def evaluate_challenge_set(analyzer, challenge: pd.DataFrame) -> dict:
    """Score the hand-written hard cases, overall and per category, and keep every prediction."""
    outputs = analyzer.analyze_texts(challenge.text.tolist())
    rows = []
    for record, output in zip(challenge.to_dict("records"), outputs):
        rows.append({
            "text": record["text"],
            "category": record["category"],
            "sentiment": {"expected": record["sentiment"], "predicted": output["sentiment_label"]},
            "emotion": {"expected": record["emotion"], "predicted": output["emotion"]},
            "intent": {"expected": record["intent"], "predicted": output["intent"]},
            "aspects": {
                "expected": parse_aspect_string(record["aspects"]),
                "predicted": [{"aspect": a["aspect"], "sentiment": a["sentiment"]} for a in output["aspects"]],
            },
        })

    def accuracy(task: str, subset: list) -> float:
        return round(sum(row[task]["expected"] == row[task]["predicted"] for row in subset) / len(subset), 4)

    categories = sorted({row["category"] for row in rows})
    return {
        "size": len(rows),
        "sentiment_accuracy": accuracy("sentiment", rows),
        "emotion_accuracy": accuracy("emotion", rows),
        "intent_accuracy": accuracy("intent", rows),
        "aspects": aspect_scores([row["aspects"]["expected"] for row in rows],
                                 [row["aspects"]["predicted"] for row in rows]),
        "by_category": {
            category: {
                "size": len(subset),
                "sentiment_accuracy": accuracy("sentiment", subset),
            }
            for category in categories
            for subset in [[row for row in rows if row["category"] == category]]
        },
        "rows": rows,
    }


def label_ceiling(texts: pd.Series, labels: pd.Series) -> float:
    """Best accuracy any text -> label function could reach (identical texts carry different labels)."""
    frame = pd.DataFrame({"text": texts.values, "label": labels.values})
    best = frame.groupby("text")["label"].agg(lambda values: values.value_counts().iloc[0]).sum()
    return round(float(best / len(frame)), 4)


def evaluate_on_pack(analyzer, pack: pd.DataFrame, absa: pd.DataFrame, sentiment_labels: list) -> dict:
    """Cross-dataset check: the trained models scored against the dataset pack's own labels.

    The pack repeats 900 texts, so sentiment is scored on unique texts. Emotion and intent labels
    vary for the same text, so each agreement figure comes with the label ceiling: the best
    accuracy any model could reach on those labels.
    """
    unique = pack.drop_duplicates("text")
    outputs = {text: output for text, output in zip(unique.text, analyzer.analyze_texts(unique.text.tolist()))}
    predicted = pack.text.map(lambda text: outputs[text])

    unique_sentiment = unique.text.map(lambda text: outputs[text]["sentiment_label"])
    primary_found = unique.apply(lambda row: row.primary_aspect in outputs[row.text]["topics"], axis=1)

    absa_unique = absa.drop_duplicates("text")
    absa_outputs = analyzer.analyze_texts(absa_unique.text.tolist())
    absa_truth = [
        [{"aspect": row.aspect_1, "sentiment": row.aspect_1_sentiment},
         {"aspect": row.aspect_2, "sentiment": row.aspect_2_sentiment}]
        for row in absa_unique.itertuples()
    ]
    absa_predicted = [[{"aspect": a["aspect"], "sentiment": a["sentiment"]} for a in output["aspects"]]
                      for output in absa_outputs]

    return {
        "rows": int(len(pack)),
        "unique_texts": int(len(unique)),
        "sentiment_unique_texts": classification_summary(unique.sentiment_label, unique_sentiment, sentiment_labels),
        "emotion_agreement": round(float((predicted.map(lambda o: o["emotion"]) == pack.emotion_label).mean()), 4),
        "emotion_label_ceiling": label_ceiling(pack.text, pack.emotion_label),
        "intent_agreement": round(float((predicted.map(lambda o: o["intent"]) == pack.intent_label).mean()), 4),
        "intent_label_ceiling": label_ceiling(pack.text, pack.intent_label),
        "primary_aspect_detected": round(float(primary_found.mean()), 4),
        "absa_sample": {"unique_texts": int(len(absa_unique)), **aspect_scores(absa_truth, absa_predicted)},
    }


def to_json(value) -> str:
    return json.dumps(value, indent=2)
