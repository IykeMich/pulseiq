"""Text cleaning, negation marking, clause splitting and the aspect taxonomy."""
from src.preprocess import clean_text, lexicon_sentiment, mark_negation, split_clauses
from src.taxonomy import detect_aspects, detect_entities


def test_clean_text_keeps_negation_and_tone():
    assert clean_text("I DON'T like it!!!") == "i do not like it!"
    assert clean_text("didnt work") == "did not work"


def test_words_ending_in_nt_are_not_split():
    """Regression: a loose n't rule once turned "payment" into "payme not"."""
    assert clean_text("payment went through") == "payment went through"


def test_mark_negation_scope_stops_at_punctuation():
    assert mark_negation("not good, but fast") == "not neg_good , but fast"


def test_split_clauses_on_contrast_words():
    clauses = split_clauses("The app looks great, but payment fails every time and support is slow.")
    assert clauses == ["The app looks great", "payment fails every time", "support is slow"]


def test_aspects_use_strong_and_weak_keywords():
    assert detect_aspects("payment fails every time") == ["payment"]
    assert detect_aspects("the app is slow") == ["performance"]          # weak keyword alone counts
    assert detect_aspects("slow delivery") == ["delivery"]              # strong keyword wins
    assert detect_aspects("I used the pay on delivery option") == ["payment"]
    assert detect_aspects("the delivery fee is steep") == ["pricing"]
    assert detect_aspects("The customer_support experience was smooth") == ["customer_support"]


def test_entities_from_the_catalogue():
    entities = detect_entities("RideGo in Lagos keeps crashing")
    assert {"type": "product", "value": "RideGo"} in entities
    assert {"type": "location", "value": "Lagos"} in entities


def test_lexicon_baseline_flips_negated_words():
    assert lexicon_sentiment("not good") == "negative"
    assert lexicon_sentiment("great service") == "positive"
