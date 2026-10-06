"""The scikit-learn pipelines behind every text classifier.

* baseline: TF-IDF over single words + logistic regression (the guide's Phase 1 reference point).
* final: two TF-IDF views joined together, then logistic regression:
    - words and word pairs over negation-marked text, so "not good" and "good" differ;
    - character 2-5-grams, which survive typos ("paymnet", "crashng") and slang.
  class_weight="balanced" stops large classes (praise, joy) from drowning out small ones (fear).

Sentiment, emotion and intent each get their own model ("don't force one model to do everything").
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from src.preprocess import clean_text, mark_negation

# Keeps neg_ tokens, slashes ("10/10") and ! / ? as their own tokens.
WORD_TOKEN_PATTERN = r"[a-z0-9_'/-]+|[!?]"


def build_baseline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=clean_text, ngram_range=(1, 1), min_df=2)),
        ("clf", LogisticRegression(max_iter=2000)),
    ])


def build_final(C: float = 4.0) -> Pipeline:
    features = FeatureUnion([
        ("words", TfidfVectorizer(
            preprocessor=mark_negation, token_pattern=WORD_TOKEN_PATTERN,
            ngram_range=(1, 2), min_df=2, sublinear_tf=True,
        )),
        ("chars", TfidfVectorizer(
            preprocessor=clean_text, analyzer="char_wb", ngram_range=(2, 5),
            min_df=3, sublinear_tf=True, max_features=60000,
        )),
    ])
    return Pipeline([
        ("features", features),
        ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=3000)),
    ])
