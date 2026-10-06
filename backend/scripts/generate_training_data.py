"""Generate the synthetic labeled training set for the NLP models (seeded, so every run is identical).

Run from backend/:  python scripts/generate_training_data.py
Writes data/training/synthetic_labeled_reviews.csv.

Why this exists: the dataset pack's demo files are built from a few sentence templates (900 unique
texts in 20,000 rows) and their emotion labels vary at random for the same text, so they can't
train or fairly evaluate a model. This generator uses the pack's label taxonomy but writes far more
varied reviews: 1-3 aspects per review with their own opinions, contrast words, emotion and intent
cues, sarcasm, very short reviews, typos and Nigerian-English expressions. It was written without
copying the pack's templates, so scoring the trained model on the pack is a real cross-dataset test.

Labels per review: rating (sentiment is derived from it later, as in real review datasets),
emotion, intent, and the aspects mentioned with their sentiment.
"""
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import TRAINING_DATA_PATH  # noqa: E402

SEED = 7
REVIEW_COUNT = 18000

PRODUCT_NAMES = [
    "QuickCash Wallet", "CloudDesk", "FreshMart", "SwiftBank Mobile", "HealthPlus",
    "StreamBox", "LearnHub", "PayWave Mobile App", "RideGo", "ShopNow",
]

# aspect -> polarity -> phrases. "neg" entries are (text, strong?) pairs.
PHRASES = {
    "payment": {
        "pos": [
            "payment went through instantly", "checkout was quick and smooth",
            "paying with my card was easy", "the bank transfer option works perfectly",
            "I like that I can pay on delivery", "card payments never fail for me",
            "topping up my wallet takes seconds", "the payment process is seamless",
            "billing is clear and accurate", "I paid with USSD without any wahala",
        ],
        "neg": [
            ("checkout is a bit clunky", False), ("payment sometimes takes a few tries", False),
            ("the card option is confusing at checkout", False),
            ("it takes long to confirm my transfer", False),
            ("billing statements are hard to understand", False),
            ("payment fails every time I try", True), ("my card was charged twice for one order", True),
            ("I was debited but the order never went through", True),
            ("the transaction keeps getting declined for no reason", True),
            ("money left my account and it still says payment failed", True),
            ("I have been debited three times and still no order", True),
            ("the payment page keeps saying transaction failed", True),
        ],
        "sarcastic": [
            "great, another failed payment", "love being charged twice for the same order",
            "wonderful, debited again and nothing to show for it",
        ],
        "neutral": ["I paid with my debit card", "payment was by bank transfer",
                    "I used the pay on delivery option"],
    },
    "delivery": {
        "pos": [
            "my order arrived a day early", "delivery was fast", "the rider was polite and on time",
            "my package came well packed and on schedule", "tracking was accurate the whole way",
            "same-day delivery actually worked", "the courier called before arriving",
            "everything arrived on time",
        ],
        "neg": [
            ("delivery took a bit longer than promised", False), ("the tracking updates are vague", False),
            ("the rider couldn't find my address at first", False), ("my parcel arrived a day late", False),
            ("my order is two weeks late", True), ("the package never arrived", True),
            ("the rider marked it delivered but I got nothing", True),
            ("delivery has been delayed five times", True), ("nobody knows where my order is", True),
            ("they keep rescheduling my delivery", True),
        ],
        "sarcastic": ["fantastic, my order is late again",
                      "nice to know next-day delivery means next month"],
        "neutral": ["the order was delivered to my office", "I chose standard delivery"],
    },
    "pricing": {
        "pos": [
            "prices are very affordable", "great value for money", "the discounts are generous",
            "cheaper than other stores", "the promo codes actually work", "no hidden fees",
            "loyalty points saved me a lot",
        ],
        "neg": [
            ("prices are a bit high", False), ("the delivery fee is steep", False),
            ("discounts are not as good as before", False),
            ("prices doubled overnight", True), ("everything is overpriced now", True),
            ("there are hidden fees everywhere", True), ("the service charge is a rip-off", True),
            ("they increased prices without any notice", True), ("the promo code never works", True),
        ],
        "sarcastic": ["love how everything costs double now"],
        "neutral": ["I compared prices with other stores", "I bought it during the sale"],
    },
    "customer_support": {
        "pos": [
            "customer support solved my issue in minutes", "the agent was very helpful",
            "live chat responded quickly",
            "support followed up to make sure everything was fine",
            "the customer care team was patient and kind", "my ticket was resolved the same day",
        ],
        "neg": [
            ("support takes a while to reply", False),
            ("the agent didn't fully understand my problem", False),
            ("I had to explain my issue twice to customer care", False),
            ("customer support never responds", True),
            ("I have been waiting a week for a reply from support", True),
            ("the agent hung up on me", True), ("support keeps sending copy-paste replies", True),
            ("nobody at customer care can help me", True),
            ("my complaint ticket was closed without a solution", True),
        ],
        "sarcastic": ["thanks support, a week to send me a template reply"],
        "neutral": ["I contacted customer care by email", "I spoke to an agent on live chat"],
    },
    "product_quality": {
        "pos": [
            "the product quality is excellent", "items are original and well made",
            "the shoes fit perfectly", "everything was fresh", "it works exactly as described",
            "the material feels premium",
        ],
        "neg": [
            ("the quality is not what I expected", False), ("the size runs a little small", False),
            ("the colour looks different from the pictures", False),
            ("the item is broken", True), ("they sold me a fake product", True),
            ("the blender stopped working after two days", True), ("the product is defective", True),
            ("I received an expired item", True), ("the phone I bought is clearly used", True),
            ("the bread was mouldy", True),
        ],
        "sarcastic": ["lovely, a brand new phone with scratches all over it"],
        "neutral": ["I ordered a pair of sneakers", "I bought a blender"],
    },
    "performance": {
        "pos": [
            "the app loads quickly", "no crashes since the last update", "pages load instantly",
            "it runs smoothly on my old phone", "the site is fast even on weak network",
        ],
        "neg": [
            ("the app is a bit slow sometimes", False), ("pages take a while to load", False),
            ("it lags when I scroll", False),
            ("the app crashes every time I open it", True), ("it freezes constantly", True),
            ("the site is down again", True), ("nothing loads, just a spinning wheel", True),
            ("the latest update made it unusable", True),
        ],
        "sarcastic": ["great update, now the app crashes twice as often"],
        "neutral": ["I updated the app yesterday", "the loading screen looks different now"],
    },
    "security": {
        "pos": [
            "I feel my account is safe here", "two-factor login gives me peace of mind",
            "they flagged a suspicious login quickly", "the OTP verification makes me feel secure",
        ],
        "neg": [
            ("verification takes too many steps", False), ("the OTP sometimes comes late", False),
            ("I can't log into my account", False), ("the password reset link never comes", False),
            ("someone hacked my account", True),
            ("someone made purchases on my account that were not mine", True),
            ("I got a scam message pretending to be you", True),
            ("my password was changed without my permission", True),
            ("my fraud report has been ignored", True),
            ("I am worried my details have been leaked", True),
            ("my account got locked for no reason", True),
            ("I keep getting logged out and locked out of my account", False),
            ("my account was locked without explanation", True),
        ],
        "sarcastic": [],
        "neutral": ["I reset my password", "I turned on two-factor login"],
    },
    "usability": {
        "pos": [
            "the app looks great", "the design is clean and modern", "it is easy to navigate",
            "the new layout is beautiful", "finding products is easy",
            "the interface is very intuitive",
        ],
        "neg": [
            ("the menu is a bit confusing", False), ("the fonts are too small", False),
            ("some buttons are hard to find", False),
            ("the new design is a mess", True), ("the interface is so confusing I gave up", True),
            ("I can't find anything in this layout", True), ("the redesign ruined the app", True),
        ],
        "sarcastic": ["love the new design, if you enjoy getting lost"],
        "neutral": ["the app has a new layout", "I mostly browse on the home screen"],
    },
    "refund": {
        "pos": [
            "my refund landed within a day", "the refund was processed quickly",
            "returning the item and getting my money back was easy",
            "they reimbursed me without any questions", "the return process was painless",
        ],
        "neg": [
            ("the refund took longer than expected", False),
            ("the return process has too many steps", False), ("I only got a partial refund", False),
            ("I have been waiting a month for my refund", True), ("they refused to refund me", True),
            ("my refund was approved but never paid", True), ("nobody will process my refund", True),
        ],
        "sarcastic": ["brilliant, sixty days and still no refund"],
        "neutral": ["I requested a refund last week", "I returned the item on Monday"],
    },
    "availability": {
        "pos": [
            "everything I wanted was in stock", "they restock popular items quickly",
            "the item was available in my size", "my favourite brand is always in stock",
        ],
        "neg": [
            ("my size is often out of stock", False), ("some items are not available in my city", False),
            ("everything I want is always out of stock", True),
            ("the item sold out right after I added it to cart", True),
            ("they cancelled my order because it was unavailable", True),
            ("the page says available but it is never in stock", True),
        ],
        "sarcastic": ["great, out of stock for the third month running"],
        "neutral": ["I checked if the item was in stock", "I asked when it would be restocked"],
    },
}

# Opinions about the whole product rather than one aspect (no aspect label), and plain factual
# statements with no opinion at all. Real feedback is full of both.
GENERAL_OPINIONS = {
    "pos": ["works really well", "it does exactly what I need", "honestly a pleasure to use",
            "simple and hassle-free", "top-notch service overall", "I'm very satisfied with it",
            "a great experience from start to finish", "everything was clear and easy",
            "no issues at all so far", "really impressed overall", "it has made my life easier"],
    "neg": [("it's really frustrating to use", True), ("a terrible experience overall", True),
            ("it needs a lot of work", False), ("honestly awful", True), ("very poor overall", True),
            ("it just doesn't work for me", True), ("it keeps letting me down", False),
            ("nothing works the way it should", True), ("I regret signing up", True),
            ("not great, could be much better", False)],
}
FACTUAL_STATEMENTS = [
    "I placed an order this morning", "this is my first time using {product}",
    "I'm writing about my recent order", "I checked my account on {product} today",
    "I just made my first purchase on {product}", "I signed up for {product} last week",
    "I have been a {product} customer for two years", "I opened {product} again this afternoon",
    "I'm leaving a note about {product}", "I logged a request with {product} yesterday",
    "I switched to the {product} business plan", "I tried {product} on my new phone",
]

# Plain nouns for each aspect, used in neutral "this is about X" statements so the model learns
# that naming a topic is not an opinion about it.
ASPECT_NOUNS = {
    "payment": ["payments", "checkout", "billing"], "delivery": ["delivery", "shipping"],
    "pricing": ["pricing", "the price list"], "customer_support": ["customer support", "the support team"],
    "product_quality": ["product quality", "the product range"], "performance": ["performance", "app speed"],
    "security": ["security settings", "account security"], "usability": ["usability", "the app layout"],
    "refund": ["refunds", "the refund policy"], "availability": ["availability", "stock levels"],
}
TOPIC_STATEMENTS = [
    "my question is about {noun}", "I'm getting in touch about {noun}",
    "I looked at the {noun} options today", "I have a few notes on {noun}",
    "I'm reviewing {noun} for my team", "this message concerns {noun}",
]

EMOTION_CUES = {
    "anger": ["This is unacceptable!", "I am furious.", "Absolutely ridiculous!!",
              "I'm so angry right now.", "Fix this now!", "Abeg fix this nonsense."],
    "sadness": ["Really sad about this.", "I'm so disappointed.", "Feeling let down.",
                "Sad, because I used to love this store.", "This breaks my heart."],
    "fear": ["I'm really worried.", "This is scary.", "I don't feel safe anymore.",
             "Please help, I'm anxious about my money."],
    "disgust": ["Disgusting.", "This is appalling.", "Absolutely gross.", "Shameful behaviour.",
                "It made me sick."],
    "surprise_negative": ["I'm shocked.", "I can't believe this happened.",
                          "Wow, I did not see this coming."],
    "surprise_positive": ["Wow, pleasantly surprised!", "Did not expect it to be this good.",
                          "What a surprise!"],
    "joy": ["Love it!", "So happy with this.", "Amazing experience.", "Absolutely brilliant.",
            "Thank you so much!", "Best shopping app I've used."],
    "neutral": ["Just sharing my experience.", "Mixed experience overall.", "Some good, some bad."],
}

# (cue text, aspect the cue itself mentions or None)
INTENT_CUES = {
    "refund_request": [("I want a refund.", "refund"), ("Please refund my money.", "refund"),
                       ("Give me my money back.", "refund"), ("Refund me abeg.", "refund")],
    "cancellation": [("I'm uninstalling the app.", None), ("Closing my account today.", None),
                     ("I'm switching to another store.", None), ("Never ordering again.", None),
                     ("Cancel my membership.", None)],
    "product_question": [("How do I change my delivery address?", "delivery"),
                         ("Can I pay in instalments?", "payment"),
                         ("Is this item available in blue?", "availability"),
                         ("How long does a refund usually take?", "refund"),
                         ("Does it come with a warranty?", None),
                         ("Can someone explain how this works?", None)],
    "fraud_report": [("Please investigate this fraud.", "security"),
                     ("I want to report unauthorized activity.", "security")],
    "account_issue": [("Please unlock my account.", "security"),
                      ("I need help getting back into my account.", None)],
    "praise": [("Keep it up!", None), ("Highly recommend.", None), ("Will order again.", None)],
}

# (text, rating, emotion, intent) for very short reviews.
SHORT_REVIEWS = [
    ("Terrible.", 1, "anger", "complaint"), ("worst app ever", 1, "anger", "complaint"),
    ("Useless.", 1, "anger", "complaint"), ("Never again!", 1, "anger", "cancellation"),
    ("rubbish service", 1, "disgust", "complaint"), ("So bad", 2, "sadness", "complaint"),
    ("not good", 2, "sadness", "complaint"), ("not happy", 2, "sadness", "complaint"),
    ("Disappointed.", 2, "sadness", "complaint"), ("Shocking service", 1, "surprise", "complaint"),
    ("Love it", 5, "joy", "praise"), ("Excellent!", 5, "joy", "praise"),
    ("great service", 5, "joy", "praise"), ("Perfect", 5, "joy", "praise"),
    ("Very good app", 4, "joy", "praise"), ("not bad at all", 4, "joy", "praise"),
    ("no complaints", 4, "joy", "praise"), ("10/10", 5, "joy", "praise"),
]

# Which issue intent a negative opinion on each aspect usually becomes.
ISSUE_INTENT = {
    "payment": "payment_issue", "delivery": "delivery_issue", "refund": "refund_request",
    "performance": "technical_problem", "usability": "technical_problem",
}
ACCOUNT_PHRASES = {"I can't log into my account", "the password reset link never comes",
                   "my account got locked for no reason",
                   "I keep getting logged out and locked out of my account",
                   "my account was locked without explanation"}


def add_typos(rng: random.Random, text: str) -> str:
    """Swap or drop a letter in one or two longer words, like fast phone typing."""
    words = text.split(" ")
    candidates = [index for index, word in enumerate(words) if len(word) > 4 and word.isalpha()]
    for index in rng.sample(candidates, k=min(len(candidates), rng.choice([1, 2]))):
        word = words[index]
        position = rng.randrange(1, len(word) - 2)
        if rng.random() < 0.5:
            word = word[:position] + word[position + 1] + word[position] + word[position + 2:]
        else:
            word = word[:position] + word[position + 1:]
        words[index] = word
    return " ".join(words)


def join_opinions(rng: random.Random, opinions: list) -> str:
    """Join opinion phrases, using contrast words when the polarity flips, as people do."""
    parts = [opinions[0]["phrase"]]
    for previous, current in zip(opinions, opinions[1:]):
        flips = {previous["polarity"], current["polarity"]} == {"positive", "negative"}
        if flips:
            connector = rng.choice([", but ", " but ", ". However, ", ", although ", ". On the other hand, "])
        else:
            connector = rng.choice([" and ", ", and ", ". ", ". Also, "])
        parts.append(connector + current["phrase"])
    pieces = "".join(parts).split(". ")
    return ". ".join(piece[0].upper() + piece[1:] for piece in pieces) + "."


def pick_opinion(rng: random.Random, aspect: str, negative_rate: float) -> dict:
    bank = PHRASES[aspect]
    roll = rng.random()
    if roll < 0.08:
        return {"aspect": aspect, "polarity": "neutral", "strong": False,
                "phrase": rng.choice(bank["neutral"]), "sarcastic": False}
    if roll < 0.08 + negative_rate:
        if bank["sarcastic"] and rng.random() < 0.06:
            return {"aspect": aspect, "polarity": "negative", "strong": True,
                    "phrase": rng.choice(bank["sarcastic"]), "sarcastic": True}
        phrase, strong = rng.choice(bank["neg"])
        return {"aspect": aspect, "polarity": "negative", "strong": strong, "phrase": phrase,
                "sarcastic": False}
    return {"aspect": aspect, "polarity": "positive", "strong": False,
            "phrase": rng.choice(bank["pos"]), "sarcastic": False}


def rating_for(rng: random.Random, opinions: list) -> int:
    """Star rating from the opinions (strong complaints weigh more), plus real-world noise."""
    values = [
        (-1.6 if opinion["strong"] else -1.0) if opinion["polarity"] == "negative"
        else (1.0 if opinion["polarity"] == "positive" else 0.0)
        for opinion in opinions
    ]
    score = sum(values) / len(values)
    if score <= -1.2:
        rating = 1
    elif score <= -0.6:
        rating = rng.choice([1, 2])
    elif score < -0.15:
        rating = rng.choice([2, 3])
    elif score <= 0.15:
        rating = 3
    elif score < 0.6:
        rating = rng.choice([3, 4])
    else:
        rating = rng.choice([4, 5, 5])
    if rng.random() < 0.06:
        rating = min(5, max(1, rating + rng.choice([-1, 1])))
    return rating


def pick_general_opinion(rng: random.Random, negative_rate: float) -> dict:
    if rng.random() < negative_rate:
        phrase, strong = rng.choice(GENERAL_OPINIONS["neg"])
        return {"aspect": None, "polarity": "negative", "strong": strong, "phrase": phrase, "sarcastic": False}
    return {"aspect": None, "polarity": "positive", "strong": False,
            "phrase": rng.choice(GENERAL_OPINIONS["pos"]), "sarcastic": False}


def factual_review(rng: random.Random) -> dict:
    """No opinion at all: one or two plain statements, sometimes with a question."""
    statements = rng.sample(FACTUAL_STATEMENTS, k=rng.choice([1, 2]))
    text = ". ".join(statement.format(product=rng.choice(PRODUCT_NAMES)) for statement in statements)
    text = text[0].upper() + text[1:] + "."
    aspects = []
    if rng.random() < 0.6:
        aspect = rng.choice(list(ASPECT_NOUNS))
        topic = rng.choice(TOPIC_STATEMENTS).format(noun=rng.choice(ASPECT_NOUNS[aspect]))
        text = f"{text} {topic[0].upper() + topic[1:]}."
        aspects.append({"aspect": aspect, "sentiment": "neutral"})
    if rng.random() < 0.4:
        cue, cue_aspect = rng.choice(INTENT_CUES["product_question"])
        text = f"{text} {cue}"
        if cue_aspect and cue_aspect not in {a["aspect"] for a in aspects}:
            aspects.append({"aspect": cue_aspect, "sentiment": "neutral"})
    return {"text": text, "rating": 3, "emotion": "neutral", "intent": "product_question",
            "aspects": aspects, "tags": ["factual"]}


def generate_review(rng: random.Random) -> dict:
    tags = []
    roll = rng.random()
    if roll < 0.05:
        text, rating, emotion, intent = rng.choice(SHORT_REVIEWS)
        return {"text": text, "rating": rating, "emotion": emotion, "intent": intent,
                "aspects": [], "tags": ["short"]}
    if roll < 0.15:
        return factual_review(rng)

    negative_rate = rng.choice([0.2, 0.35, 0.5, 0.65])  # vary the mood across reviews
    if roll < 0.2:
        opinions = [pick_general_opinion(rng, negative_rate)]
        tags.append("general")
    else:
        aspects = rng.sample(list(PHRASES), k=rng.choices([1, 2, 3], weights=[0.45, 0.4, 0.15])[0])
        opinions = [pick_opinion(rng, aspect, negative_rate) for aspect in aspects]
        if rng.random() < 0.25:
            general = pick_general_opinion(rng, negative_rate)
            opinions.insert(rng.choice([0, len(opinions)]), general)
    if any(opinion["sarcastic"] for opinion in opinions):
        tags.append("sarcasm")
    polarities = {opinion["polarity"] for opinion in opinions}
    if {"positive", "negative"} <= polarities:
        tags.append("mixed")

    rating = rating_for(rng, opinions)
    if rng.random() < 0.012:
        rating = 6 - rating
        tags.append("rating_mismatch")
    overall = "negative" if rating <= 2 else ("positive" if rating >= 4 else "neutral")
    negatives = [opinion for opinion in opinions if opinion["polarity"] == "negative"]
    negative_aspects = {opinion["aspect"] for opinion in negatives}
    any_strong = any(opinion["strong"] for opinion in negatives)

    # Intent: what the customer wants.
    if overall == "negative" and negatives:
        main = max(negatives, key=lambda opinion: opinion["strong"])
        if main["aspect"] == "security":
            intent = "account_issue" if main["phrase"] in ACCOUNT_PHRASES else "fraud_report"
        else:
            intent = ISSUE_INTENT.get(main["aspect"], "complaint")
        roll = rng.random()
        if roll < 0.1:
            intent = "cancellation"
        elif roll < 0.25 and negative_aspects & {"payment", "delivery", "product_quality"}:
            intent = "refund_request"
        elif roll < 0.32:
            intent = "product_question"
    elif overall == "positive":
        intent = "praise" if rng.random() < 0.9 else "product_question"
    elif negatives:
        intent = rng.choices(["complaint", ISSUE_INTENT.get(negatives[0]["aspect"], "complaint"),
                              "product_question"], weights=[0.4, 0.4, 0.2])[0]
    else:
        intent = "praise" if "positive" in polarities else "product_question"

    # Emotion: how they feel about it.
    if overall == "negative":
        if "security" in negative_aspects and rng.random() < 0.8:
            emotion = "fear"
        elif any(opinion["aspect"] == "product_quality" and opinion["strong"] for opinion in negatives) \
                and rng.random() < 0.45:
            emotion = "disgust"
        elif any_strong and (intent in {"refund_request", "cancellation"} or rng.random() < 0.4):
            emotion = "anger"
        else:
            emotion = rng.choices(["sadness", "anger", "surprise", "disgust"],
                                  weights=[0.5, 0.25, 0.15, 0.1])[0]
    elif overall == "positive":
        emotion = "surprise" if rng.random() < 0.12 else "joy"
    elif "mixed" in tags:
        emotion = rng.choices(["neutral", "sadness", "surprise"], weights=[0.65, 0.25, 0.1])[0]
    else:
        emotion = "neutral"

    text = join_opinions(rng, opinions)
    if rng.random() < 0.3:
        product = rng.choice(PRODUCT_NAMES)
        text = rng.choice([f"{product} review: {text}", f"I use {product} a lot. {text}",
                           f"{text} (via {product})"])
    if rng.random() < 0.6:
        cue_key = f"surprise_{'positive' if overall == 'positive' else 'negative'}" \
            if emotion == "surprise" else emotion
        cue = rng.choice(EMOTION_CUES[cue_key])
        text = f"{cue} {text}" if rng.random() < 0.5 else f"{text} {cue}"
    aspect_labels = {opinion["aspect"]: opinion["polarity"] for opinion in opinions if opinion["aspect"]}
    if intent in INTENT_CUES and (intent != "praise" or rng.random() < 0.5) and \
            (intent not in {"fraud_report", "account_issue", "refund_request"} or rng.random() < 0.6):
        cue, cue_aspect = rng.choice(INTENT_CUES[intent])
        text = f"{text} {cue}"
        if cue_aspect and cue_aspect not in aspect_labels:
            # The cue mentions an aspect too: a request is negative, a question is neutral.
            aspect_labels[cue_aspect] = "neutral" if intent == "product_question" else "negative"

    if rng.random() < 0.06:
        text = add_typos(rng, text)
        tags.append("typo")
    if rng.random() < 0.1:
        text = text.lower()
    elif emotion == "anger" and rng.random() < 0.08:
        text = text.upper()

    return {
        "text": text,
        "rating": rating,
        "emotion": emotion,
        "intent": intent,
        "aspects": [{"aspect": aspect, "sentiment": polarity} for aspect, polarity in aspect_labels.items()],
        "tags": tags,
    }


def main() -> None:
    rng = random.Random(SEED)
    rows = []
    for number in range(1, REVIEW_COUNT + 1):
        review = generate_review(rng)
        rows.append({
            "train_id": f"tr_{number:05d}",
            "text": review["text"],
            "rating": review["rating"],
            "emotion": review["emotion"],
            "intent": review["intent"],
            "aspects": json.dumps(review["aspects"]),
            "tags": "|".join(review["tags"]),
        })
    TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_DATA_PATH, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    unique_texts = len({row["text"] for row in rows})
    print(f"Wrote {len(rows):,} labeled reviews ({unique_texts:,} unique texts) to {TRAINING_DATA_PATH}")


if __name__ == "__main__":
    main()
