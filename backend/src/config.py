"""Central configuration: data-zone paths, the label contract, model version and alert thresholds.

Every other module imports from here, so changing a path, label or threshold here changes the
whole pipeline. The label sets come from the PulseIQ Dataset Pack taxonomies
(data/reference/*_taxonomy.csv), so model output and the demo data speak the same language.
"""
from pathlib import Path

# Backend root (customer_pulse/backend/), resolved from this file so it works from any cwd.
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"

# Local mirror of the guide's S3 layout (s3://pulseiq-data/raw|processed|curated/...).
RAW_DIR = DATA_DIR / "raw"                                     # exact source data, never edited
RAW_FEEDBACK_PATH = RAW_DIR / "customer_feedback" / "customer_feedback_demo.csv"
RAW_STREAM_PATH = RAW_DIR / "streaming" / "streaming_feedback_events.csv"
LIVE_RAW_PATH = RAW_DIR / "live" / "events.jsonl"              # feedback received through the API
PROCESSED_DIR = DATA_DIR / "processed"                         # one enriched record per review
PROCESSED_PATH = PROCESSED_DIR / "reviews_enriched.jsonl"
LIVE_PROCESSED_PATH = PROCESSED_DIR / "live_enriched.jsonl"
CURATED_DIR = DATA_DIR / "curated"                             # business-ready aggregates
QUALITY_REPORT_PATH = CURATED_DIR / "data_quality_report.json"

# Model training data lives apart from the application data (as the dataset pack README asks).
TRAINING_DATA_PATH = DATA_DIR / "training" / "synthetic_labeled_reviews.csv"
CHALLENGE_SET_PATH = DATA_DIR / "samples" / "challenge_set.csv"
ABSA_SAMPLE_PATH = DATA_DIR / "samples" / "aspect_sentiment_demo.csv"

MODEL_VERSION = "pulseiq-nlp-v1"
RANDOM_SEED = 42

# The review contract (guide Phase 0). The raw file must contain at least these columns.
REVIEW_COLUMNS = [
    "review_id", "customer_id", "timestamp", "text", "rating",
    "product", "channel", "country", "city", "language",
]
# Columns of the demo file that hold the pack's own labels (kept for the agreement check).
PACK_LABEL_COLUMNS = ["sentiment_label", "emotion_label", "intent_label", "primary_aspect"]

SENTIMENT_LABELS = ["negative", "neutral", "positive"]
EMOTION_LABELS = ["anger", "disgust", "fear", "sadness", "surprise", "neutral", "joy"]
INTENT_LABELS = [
    "complaint", "praise", "refund_request", "technical_problem", "fraud_report",
    "cancellation", "product_question", "delivery_issue", "payment_issue", "account_issue",
]

# Which cities belong to which country; used by the data-quality checks.
CITY_COUNTRY = {
    "Lagos": "Nigeria", "Abuja": "Nigeria", "Port Harcourt": "Nigeria", "Kano": "Nigeria",
    "Ibadan": "Nigeria", "Enugu": "Nigeria", "Benin City": "Nigeria",
    "Accra": "Ghana", "London": "United Kingdom", "New York": "United States",
}

# Early warning (guide Phase 7): current 7-day window vs the 28 days before it.
ALERT_CURRENT_DAYS = 7
ALERT_BASELINE_DAYS = 28
ALERT_MIN_MENTIONS = 15          # ignore aspects with too little current volume
ALERT_MIN_POINT_CHANGE = 0.08    # +8 percentage points of negative rate ...
ALERT_MIN_RELATIVE_CHANGE = 0.20 # ... and at least +20% relative ...
ALERT_MIN_Z = 2.0                # ... and a two-proportion z-score of at least 2
