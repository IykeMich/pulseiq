"""Text cleaning that keeps meaning: negation and ! / ? survive, noise does not (guide Phase 1).

These functions are referenced by the saved scikit-learn pipelines, so changing them changes what
a trained model sees. Retrain (python -m src.train) after editing.
"""
import re

_CONTRACTIONS = [
    (re.compile(r"\bcan'?t\b"), "can not"),
    (re.compile(r"\bwon'?t\b"), "will not"),
    (re.compile(r"\bain'?t\b"), "is not"),
    (re.compile(r"\b(\w+)n't\b"), r"\1 not"),    # don't, isn't, wouldn't ...
    # The same words typed without the apostrophe ("didnt"). An explicit list, because a general
    # rule would also split ordinary words ending in "nt", such as "payment".
    (re.compile(r"\b(do|does|did|is|was|were|are|would|could|should|has|have|had)nt\b"), r"\1 not"),
    (re.compile(r"'re\b"), " are"),
    (re.compile(r"'ve\b"), " have"),
    (re.compile(r"'ll\b"), " will"),
    (re.compile(r"'m\b"), " am"),
]
_URL = re.compile(r"https?://\S+|www\.\S+")
_REPEATED_CHAR = re.compile(r"(\w)\1{2,}")       # soooo -> soo
_REPEATED_PUNCT = re.compile(r"([!?.])\1+")      # !!! -> !
_NON_TEXT = re.compile(r"[^a-z0-9!?.,'/ _-]+")
_SPACES = re.compile(r"\s+")

NEGATORS = {"not", "no", "never", "nothing", "nobody", "none", "neither", "nor", "without", "hardly"}
_NEGATION_SCOPE = 3                              # tokens after a negator that get the neg_ prefix
_SCOPE_END = {".", "!", "?", ",", "but", "however", "although", "though"}
_TOKEN = re.compile(r"[a-z0-9_'/-]+|[!?.,]")


def clean_text(text: str) -> str:
    """Lowercase, expand contractions, squash repeats and drop symbols; keep ! ? . , for tone."""
    text = str(text).lower().replace("’", "'").replace("_", " ")
    text = _URL.sub(" ", text)
    for pattern, replacement in _CONTRACTIONS:
        text = pattern.sub(replacement, text)
    text = _REPEATED_CHAR.sub(r"\1\1", text)
    text = _REPEATED_PUNCT.sub(r"\1", text)
    text = _NON_TEXT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def mark_negation(text: str) -> str:
    """Clean, then prefix up to 3 words after a negator with neg_ ("not good" -> "not neg_good").

    This lets a bag-of-words model tell "good" from "not good" without word order.
    """
    tokens = _TOKEN.findall(clean_text(text))
    marked, remaining = [], 0
    for token in tokens:
        if token in _SCOPE_END:
            remaining = 0
            marked.append(token)
        elif token in NEGATORS:
            remaining = _NEGATION_SCOPE
            marked.append(token)
        elif remaining > 0:
            marked.append("neg_" + token)
            remaining -= 1
        else:
            marked.append(token)
    return " ".join(marked)


# Clause boundaries: sentence ends, and contrast words where opinions usually flip.
_CLAUSE_SPLIT = re.compile(
    r"(?<=[.!?;])\s+|\s*\b(?:but|however|although|though|whereas|while|yet|except that)\b,?\s*"
    r"|\s*,\s*(?:and\s+)?(?=(?:the|my|our|their|its|it|i|they|delivery|payment|support)\b)",
    re.IGNORECASE,
)


def split_clauses(text: str) -> list:
    """Split a review into opinion clauses: "The app looks great, but payment fails" -> 2 clauses."""
    clauses = [clause.strip(" ,.;") for clause in _CLAUSE_SPLIT.split(str(text)) if clause]
    clauses = [clause for clause in clauses if clause and any(char.isalpha() for char in clause)]
    # " and " joins two opinions when both sides are full statements ("the app crashes and support ...").
    result = []
    for clause in clauses:
        parts = re.split(r"\s+and\s+(?=(?:the|my|i|it|they|support|delivery|payment)\b)", clause, flags=re.IGNORECASE)
        if len(parts) > 1 and all(len(part.split()) >= 3 for part in parts):
            result.extend(part.strip() for part in parts)
        else:
            result.append(clause)
    return result or [str(text).strip()]


# Rule-based baseline: a small hand-made opinion lexicon with negation flipping.
POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "love", "loved", "perfect", "perfectly", "easy", "fast",
    "quick", "quickly", "smooth", "smoothly", "helpful", "happy", "brilliant", "fantastic", "best",
    "affordable", "clean", "beautiful", "intuitive", "polite", "fresh", "premium", "seamless", "safe",
    "secure", "generous", "recommend", "thank", "thanks", "wonderful", "kind", "patient", "early",
    "instantly", "straightforward", "pleased", "nice", "reliable", "solid", "impressive", "fair",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "worst", "hate", "slow", "fail", "fails", "failed", "failing", "broken",
    "late", "never", "crash", "crashes", "crashed", "freezes", "useless", "rubbish", "expensive",
    "overpriced", "confusing", "mess", "fake", "defective", "expired", "disappointed", "angry",
    "furious", "unacceptable", "ridiculous", "scam", "hacked", "worried", "scary", "declined",
    "delayed", "ignored", "refused", "frustrating", "annoying", "poor", "problem", "issue", "rip-off",
    "disgusting", "appalling", "horrible", "sad", "lagging", "lags", "unusable", "locked", "stuck",
}


def lexicon_sentiment(text: str) -> str:
    """Count positive minus negative words; a negator within 3 words flips a word's sign."""
    tokens = _TOKEN.findall(clean_text(text))
    score, flip = 0, 0
    for token in tokens:
        if token in _SCOPE_END:
            flip = 0
            continue
        if token in NEGATORS and token != "never":
            flip = _NEGATION_SCOPE
            continue
        sign = 1 if token in POSITIVE_WORDS else (-1 if token in NEGATIVE_WORDS else 0)
        if sign and flip:
            sign = -sign
        score += sign
        flip = max(0, flip - 1)
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"
