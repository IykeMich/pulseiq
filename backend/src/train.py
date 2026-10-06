"""Train and evaluate the PulseIQ NLP models, then write artifacts/ (guide Phases 1-3, section 18).

Run from backend/:  python -m src.train

1. Load the synthetic labeled set, drop duplicate texts (so no text sits in two splits) and derive
   sentiment from the star rating (1-2 negative, 3 neutral, 4-5 positive).
2. Split 70/15/15 into train / validation / test, stratified by sentiment.
3. Sentiment: compare majority class, a rule-based lexicon, the TF-IDF unigram baseline and the
   word+char model. C is picked on validation by macro-F1; test is touched once at the end.
4. Emotion and intent: baseline vs word+char, same protocol.
5. For each task, deploy whichever candidate scored higher on validation (the richer model is not
   assumed to win), refit it on train+validation and save it.
6. Evaluate aspects on the test split, the hand-written challenge set and the dataset pack.
"""
import json
from collections import Counter
from datetime import datetime, timezone

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

from src.analyzer import PulseAnalyzer
from src.config import (
    ABSA_SAMPLE_PATH, ARTIFACT_DIR, CHALLENGE_SET_PATH, EMOTION_LABELS, INTENT_LABELS,
    MODEL_VERSION, RANDOM_SEED, RAW_FEEDBACK_PATH, SENTIMENT_LABELS, TRAINING_DATA_PATH,
)
from src.evaluate import aspect_scores, classification_summary, evaluate_challenge_set, evaluate_on_pack
from src.models import build_baseline, build_final
from src.preprocess import lexicon_sentiment

C_GRID = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]


def rating_to_sentiment(rating: int) -> str:
    return "negative" if rating <= 2 else ("positive" if rating >= 4 else "neutral")


def load_training_frame() -> pd.DataFrame:
    frame = pd.read_csv(TRAINING_DATA_PATH, keep_default_na=False)
    frame = frame.drop_duplicates("text").reset_index(drop=True)
    frame["sentiment"] = frame.rating.map(rating_to_sentiment)
    frame["aspects"] = frame.aspects.map(json.loads)
    return frame


def split(frame: pd.DataFrame) -> tuple:
    train, holdout = train_test_split(frame, test_size=0.3, stratify=frame.sentiment, random_state=RANDOM_SEED)
    validation, test = train_test_split(holdout, test_size=0.5, stratify=holdout.sentiment, random_state=RANDOM_SEED)
    return train, validation, test


def tune(target: str, labels: list, train: pd.DataFrame, validation: pd.DataFrame) -> tuple:
    """Fit the final model for each C; return (best C, validation macro-F1 per C)."""
    scores = {}
    for C in C_GRID:
        model = build_final(C).fit(train.text, train[target])
        scores[C] = classification_summary(validation[target], model.predict(validation.text), labels)["macro_f1"]
        print(f"  {target:9s} C={C:<5} validation macro-F1={scores[C]:.4f}")
    return max(scores, key=scores.get), scores


BASELINE = "baseline_tfidf_unigram_lr"
WORD_CHAR = "final_tfidf_word_char_lr"
MODEL_TYPES = {
    BASELINE: "TF-IDF (word unigrams) + LogisticRegression",
    WORD_CHAR: "TF-IDF (word 1-2gram + negation, char 2-5gram) + LogisticRegression (balanced)",
}


def build_candidate(name: str, C: float):
    return build_final(C) if name == WORD_CHAR else build_baseline()


def compare(target: str, labels: list, train, validation, test) -> tuple:
    """Baseline vs tuned word+char model. The one with the higher validation macro-F1 is selected.

    Returns (report, selected name, C for word+char, selected test predictions, fitted candidates).
    """
    baseline = build_baseline().fit(train.text, train[target])
    baseline_validation = classification_summary(validation[target], baseline.predict(validation.text), labels)["macro_f1"]
    best_C, validation_scores = tune(target, labels, train, validation)
    word_char = build_final(best_C).fit(train.text, train[target])
    selected = WORD_CHAR if validation_scores[best_C] >= baseline_validation else BASELINE
    fitted = {BASELINE: baseline, WORD_CHAR: word_char}
    report = {
        "labels": labels,
        "selected_model": selected,
        "selected_C": best_C,
        "validation_macro_f1": {BASELINE: baseline_validation, WORD_CHAR: validation_scores[best_C]},
        "validation_macro_f1_by_C": {str(C): score for C, score in validation_scores.items()},
        "test": {
            name: classification_summary(test[target], model.predict(test.text), labels)
            for name, model in fitted.items()
        },
    }
    print(f"  {target:9s} selected {selected} (validation macro-F1 baseline {baseline_validation:.4f} "
          f"vs word+char {validation_scores[best_C]:.4f})")
    return report, selected, best_C, fitted[selected].predict(test.text), fitted


def challenge_sentiment(fitted: dict, challenge: pd.DataFrame) -> dict:
    """Challenge-set sentiment accuracy for each candidate (both refit on train+validation like the
    deployed model, so the numbers match the deployed model's own challenge results)."""
    result = {}
    for name, model in fitted.items():
        correct = pd.Series(model.predict(challenge.text) == challenge.sentiment.values, index=challenge.index)
        result[name] = {
            "accuracy": round(float(correct.mean()), 4),
            "by_category": {category: round(float(correct[challenge.category == category].mean()), 4)
                            for category in sorted(challenge.category.unique())},
        }
    return result


def error_analysis(test: pd.DataFrame, predictions) -> dict:
    """Sentiment error rate per difficulty tag, plus a sample of wrong predictions to read."""
    frame = test.assign(predicted=predictions)
    frame["wrong"] = frame.predicted != frame.sentiment
    tag_lists = frame.tags.map(lambda tags: tags.split("|") if tags else ["plain"])
    by_tag = {}
    for tag in sorted({tag for tags in tag_lists for tag in tags}):
        mask = tag_lists.map(lambda tags: tag in tags)
        by_tag[tag] = {"reviews": int(mask.sum()), "error_rate": round(float(frame.wrong[mask].mean()), 4)}
    errors = frame[frame.wrong].sample(n=min(30, int(frame.wrong.sum())), random_state=RANDOM_SEED)
    return {
        "by_tag": by_tag,
        "sample_errors": [
            {"text": row.text, "rating": int(row.rating), "expected": row.sentiment,
             "predicted": row.predicted, "tags": row.tags.split("|") if row.tags else []}
            for row in errors.itertuples()
        ],
    }


def train() -> dict:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_training_frame()
    train_set, validation, test = split(frame)
    print(f"Training data: {len(frame):,} unique reviews -> "
          f"train {len(train_set):,} / validation {len(validation):,} / test {len(test):,}")

    # Sentiment, with the two non-learned reference points first.
    majority = Counter(train_set.sentiment).most_common(1)[0][0]
    challenge_frame = pd.read_csv(CHALLENGE_SET_PATH, keep_default_na=False)
    sentiment_report, sentiment_choice, sentiment_C, sentiment_predictions, sentiment_fitted = compare(
        "sentiment", SENTIMENT_LABELS, train_set, validation, test)
    sentiment_report["test"] = {
        "majority_class": classification_summary(test.sentiment, [majority] * len(test), SENTIMENT_LABELS),
        "rule_based_lexicon": classification_summary(
            test.sentiment, test.text.map(lexicon_sentiment), SENTIMENT_LABELS),
        **sentiment_report["test"],
    }
    emotion_report, emotion_choice, emotion_C, _, _ = compare("emotion", EMOTION_LABELS, train_set, validation, test)
    intent_report, intent_choice, intent_C, _, _ = compare("intent", INTENT_LABELS, train_set, validation, test)
    choices = {"sentiment": (sentiment_choice, sentiment_C), "emotion": (emotion_choice, emotion_C),
               "intent": (intent_choice, intent_C)}

    # Refit on train + validation with the chosen settings; test stays unseen.
    fit_frame = pd.concat([train_set, validation])
    models = {
        task: build_candidate(name, C).fit(fit_frame.text, fit_frame[task])
        for task, (name, C) in choices.items()
    }
    sentiment_candidates = {
        name: (models["sentiment"] if name == sentiment_choice else build_candidate(name, sentiment_C).fit(
            fit_frame.text, fit_frame.sentiment))
        for name in (BASELINE, WORD_CHAR)
    }
    sentiment_report["challenge_set"] = challenge_sentiment(sentiment_candidates, challenge_frame)
    for name, model in models.items():
        joblib.dump(model, ARTIFACT_DIR / f"{name}.joblib", compress=3)
    analyzer = PulseAnalyzer(models["sentiment"], models["emotion"], models["intent"])

    test_outputs = analyzer.analyze_texts(test.text.tolist())
    aspect_report = aspect_scores(
        test.aspects.tolist(),
        [[{"aspect": a["aspect"], "sentiment": a["sentiment"]} for a in output["aspects"]] for output in test_outputs],
    )
    challenge = evaluate_challenge_set(analyzer, challenge_frame)
    pack = evaluate_on_pack(
        analyzer, pd.read_csv(RAW_FEEDBACK_PATH), pd.read_csv(ABSA_SAMPLE_PATH), SENTIMENT_LABELS)

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "data": {
            "source": "synthetic_labeled_reviews.csv (seeded generator, pack taxonomy)",
            "unique_reviews": int(len(frame)),
            "train": int(len(train_set)), "validation": int(len(validation)), "test": int(len(test)),
            "sentiment_distribution": frame.sentiment.value_counts().to_dict(),
        },
        "sentiment": {**sentiment_report, "error_analysis": error_analysis(test, sentiment_predictions)},
        "emotion": emotion_report,
        "intent": intent_report,
        "aspects": {"test": aspect_report},
        "challenge_set": challenge,
        "dataset_pack": pack,
    }
    metadata = {
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "models": {
            task: {"selected": name, "type": MODEL_TYPES[name], "C": C if name == WORD_CHAR else 1.0,
                   "classes": list(models[task].classes_)}
            for task, (name, C) in choices.items()
        },
        "aspect_method": "taxonomy keywords per clause + clause-level sentiment model",
        "training_reviews": int(len(fit_frame)),
    }
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (ARTIFACT_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2))

    final_sentiment = sentiment_report["test"][WORD_CHAR]
    print(f"\nSentiment test macro-F1: word+char {final_sentiment['macro_f1']:.4f} vs "
          f"baseline {sentiment_report['test']['baseline_tfidf_unigram_lr']['macro_f1']:.4f} vs "
          f"lexicon {sentiment_report['test']['rule_based_lexicon']['macro_f1']:.4f}")
    print(f"Emotion test macro-F1 ({emotion_choice}): {emotion_report['test'][emotion_choice]['macro_f1']:.4f}   "
          f"Intent test macro-F1 ({intent_choice}): {intent_report['test'][intent_choice]['macro_f1']:.4f}")
    print(f"Aspect detection F1 (test): {aspect_report['detection']['f1']:.4f}, "
          f"aspect sentiment accuracy: {aspect_report['sentiment_accuracy']}")
    print(f"Challenge set sentiment accuracy: {challenge['sentiment_accuracy']:.4f} "
          f"({challenge['size']} hand-written cases)")
    print(f"Dataset pack sentiment macro-F1 (unique texts): "
          f"{pack['sentiment_unique_texts']['macro_f1']:.4f}; primary aspect found: {pack['primary_aspect_detected']:.4f}")
    print(f"Artifacts written to {ARTIFACT_DIR}")
    return metrics


if __name__ == "__main__":
    train()
