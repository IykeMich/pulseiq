"""The controlled aspect taxonomy (guide Phases 2-3), entity gazetteer and the action playbook.

The ten aspects are the dataset pack's aspect_taxonomy.csv. A fixed taxonomy keeps business
reporting stable: "payment" means the same thing every week, whatever model sits underneath.
Keywords are regular expressions matched on lowercased text.

`strong` keywords always count. `weak` keywords are ambiguous on their own ("slow" can describe
an app, a courier or an agent), so they only count when the clause has no strong keyword for a
different aspect: "slow delivery" is delivery, "the app is slow" is performance.
"""
import re

ASPECTS = {
    "payment": {
        "name": "Payment",
        "strong": [
            r"\bpay(s|ing|ment|ments)?\b", r"\bpaid\b", r"\bcheckout\b", r"\bcharged?\b",
            r"\bdebit(ed)?\b", r"\btransactions?\b", r"\bbill(ing|ed)?\b", r"\btransfers?\b",
            r"\bdeclined?\b", r"\bussd\b", r"\btop(ping)?[- ]?up\b", r"\binstal?lments?\b",
            r"\bpayondelivery\b", r"\bmastercard\b", r"\bvisa\b",
        ],
        "weak": [r"\bcards?\b"],
    },
    "delivery": {
        "name": "Delivery",
        "strong": [
            r"\bdeliver(y|ies|ed)?\b", r"\bshipping\b", r"\bshipped\b", r"\bcourier\b",
            r"\briders?\b", r"\bdispatch(ed)?\b", r"\barriv(e|ed|es|ing|al)\b", r"\bparcels?\b",
            r"\bpackages?\b", r"\btracking\b", r"\bwaybill\b",
        ],
        "weak": [r"\blate\b", r"\bon time\b", r"\bdelay(ed|s)?\b", r"\border (is|was|never)\b"],
    },
    "pricing": {
        "name": "Pricing",
        "strong": [
            r"\bprices?\b", r"\bpricing\b", r"\bpriced\b", r"\bexpensive\b", r"\bcheap(er|est)?\b",
            r"\bcosts?\b", r"\bfees?\b", r"\bdiscounts?\b", r"\bpromo( codes?)?\b",
            r"\bdeals?\b", r"\bvalue for money\b", r"\boverpriced\b", r"\baffordable\b",
            r"\bservice charge\b", r"\bdeliveryfee\b", r"\brip[- ]?off\b", r"\bcoupons?\b",
            r"\bloyalty points\b",
        ],
        "weak": [r"\bsale\b", r"\bpoints\b"],
    },
    "customer_support": {
        "name": "Customer support",
        "strong": [
            r"\bcustomer[_ ]support\b", r"\bsupport\b", r"\bcustomer (service|care)\b", r"\bagents?\b",
            r"\bhelpline\b", r"\bcall (center|centre)\b", r"\blive chat\b", r"\btickets?\b",
            r"\bhelpdesk\b", r"\brepl(y|ied|ies)\b", r"\brespon(d|ds|ded|se|sive)\b",
        ],
        "weak": [r"\bstaff\b", r"\bchat\b"],
    },
    "product_quality": {
        "name": "Product quality",
        "strong": [
            r"\bproduct[_ ]quality\b", r"\bquality\b", r"\bbroken\b", r"\bdamaged\b", r"\bfake\b",
            r"\boriginal\b", r"\bauthentic\b", r"\bdefective\b", r"\bexpired\b", r"\bwell made\b",
            r"\bmaterial\b", r"\bfits?\b", r"\bstopped working\b", r"\bcolou?r\b",
            r"\bscratch(es|ed)?\b", r"\bcounterfeit\b", r"\bfresh\b", r"\bas described\b",
            r"\bclearly used\b", r"\bsecond[- ]?hand\b", r"\bmouldy\b", r"\bspoilt\b",
        ],
        "weak": [r"\bproducts?\b", r"\bitems?\b"],
    },
    "performance": {
        "name": "Performance",
        "strong": [
            r"\bperformance\b", r"\bspeed\b", r"\bcrash(es|ed|ing)?\b", r"\blag(s|gy|ging)?\b",
            r"\bfreez(e|es|ing)\b", r"\bfroze\b", r"\bload(s|ing|ed)?\b", r"\bspinning\b",
            r"\bglitch(es|y)?\b", r"\bbugs?\b", r"\bbuggy\b", r"\bunusable\b", r"\btime[- ]?outs?\b",
            r"\boutage\b", r"\bis down\b", r"\bruns smoothly\b", r"\bhangs?\b",
        ],
        "weak": [r"\bslow\b", r"\bfast\b", r"\bquick(ly)?\b", r"\bupdate\b", r"\bsmooth(ly)?\b"],
    },
    "security": {
        "name": "Security",
        "strong": [
            r"\bsecur(e|ity)\b", r"\bhack(ed|er|ers)?\b", r"\bfraud\w*\b", r"\bscam(s|mer|mers)?\b",
            r"\bpasswords?\b", r"\botp\b", r"\bunauthori[sz]ed\b", r"\bstolen\b", r"\bsuspicious\b",
            r"\bprivacy\b", r"\btwo[- ]factor\b", r"\b2fa\b", r"\bverification\b", r"\bleak(ed)?\b",
            r"\bphishing\b", r"\bnot mine\b", r"\bwithout my permission\b", r"\bsafe\b",
            r"\blocked( out)?\b", r"\bunlock\b", r"\blog ?in(to)?\b",
        ],
        "weak": [r"\bpin\b"],
    },
    "usability": {
        "name": "Usability",
        "strong": [
            r"\busability\b", r"\bdesign\b", r"\bredesign\b", r"\binterface\b", r"\blayout\b",
            r"\bnavigat(e|ion)\b", r"\bmenus?\b", r"\bbuttons?\b", r"\bfonts?\b",
            r"\buser[- ]friendly\b", r"\bintuitive\b", r"\beasy to use\b", r"\bdark mode\b",
            r"\bhome screen\b", r"\blooks (great|good|nice|bad|ugly)\b", r"\bgetting lost\b",
            r"\bfind(ing)? (products|anything)\b",
        ],
        "weak": [r"\bscreen\b", r"\blooks?\b", r"\bconfusing\b"],
    },
    "refund": {
        "name": "Refund",
        "strong": [
            r"\brefund(s|ed|ing)?\b", r"\bmoney back\b", r"\breimburs\w*\b", r"\bchargeback\b",
            r"\breturn (process|policy|request)\b", r"\breturn(ed|ing)? (the|my|an|it)\b",
        ],
        "weak": [],
    },
    "availability": {
        "name": "Availability",
        "strong": [
            r"\bavailability\b", r"\bout of stock\b", r"\bsold out\b", r"\bunavailable\b",
            r"\bin stock\b", r"\brestock(ed|s)?\b", r"\bnot available\b", r"\bavailable in\b",
            r"\bbackorder(ed)?\b",
        ],
        "weak": [r"\bstock\b", r"\bavailable\b"],
    },
}

ASPECT_KEYS = list(ASPECTS)

_STRONG = {key: [re.compile(pattern) for pattern in spec["strong"]] for key, spec in ASPECTS.items()}
_WEAK = {key: [re.compile(pattern) for pattern in spec["weak"]] for key, spec in ASPECTS.items()}

# Fixed phrases that would otherwise trigger the wrong aspect ("pay on delivery" is a payment
# method, "delivery fee" is a price). They are rewritten to one token before matching.
_PHRASE_REWRITES = [
    (re.compile(r"\bpay(ing)? on delivery\b"), "payondelivery"),
    (re.compile(r"\bdelivery (fee|fees|charge|charges)\b"), "deliveryfee"),
]


def detect_aspects(clause: str) -> list:
    """Aspects mentioned in one clause, in taxonomy order (see the module docstring)."""
    lowered = clause.lower()
    for pattern, replacement in _PHRASE_REWRITES:
        lowered = pattern.sub(replacement, lowered)
    strong = {key for key, patterns in _STRONG.items() if any(p.search(lowered) for p in patterns)}
    weak = {key for key, patterns in _WEAK.items() if any(p.search(lowered) for p in patterns)}
    found = set(strong)
    for key in weak - strong:
        if not strong - {key}:
            found.add(key)
    return [key for key in ASPECT_KEYS if key in found]


# Entities: which product or place a review names (gazetteer lookup over the pack's catalogue).
PRODUCT_ENTITIES = [
    "QuickCash Wallet", "CloudDesk", "FreshMart", "SwiftBank Mobile", "HealthPlus",
    "StreamBox", "LearnHub", "PayWave Mobile App", "RideGo", "ShopNow",
]
LOCATION_ENTITIES = [
    "Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan", "Enugu", "Benin City",
    "Accra", "London", "New York",
]
_ENTITY_PATTERNS = [
    (entity_type, value, re.compile(r"\b" + re.escape(value.lower()) + r"\b"))
    for entity_type, values in (("product", PRODUCT_ENTITIES), ("location", LOCATION_ENTITIES))
    for value in values
]


def detect_entities(text: str) -> list:
    """Products and places named in the text, e.g. [{"type": "product", "value": "RideGo"}]."""
    lowered = text.lower()
    return [
        {"type": entity_type, "value": value}
        for entity_type, value, pattern in _ENTITY_PATTERNS
        if pattern.search(lowered)
    ]


# What an analyst should do when an aspect turns negative. Deterministic on purpose: the action
# is a business rule, not something a model should invent.
PLAYBOOK = {
    "payment": "Check payment-gateway error rates and recent releases for the affected segment; "
               "reconcile debited-but-failed transactions and proactively reverse duplicates.",
    "delivery": "Review courier SLAs and hub capacity in the affected cities; send proactive delay "
                "notices and prioritise orders already past their promised date.",
    "pricing": "Compare the price change against competitors and churn signals; consider a targeted "
               "offer for affected segments and show fees before checkout.",
    "customer_support": "Check queue times and staffing on the affected channel; audit tickets closed "
                        "without resolution and replace template replies for the top issues.",
    "product_quality": "Pull the suppliers and SKUs behind the complaints; quarantine suspected "
                       "counterfeit or expired stock and tighten quality checks.",
    "performance": "Correlate with crash reports and the latest release; roll back or hotfix if "
                   "crash-free sessions dropped.",
    "security": "Escalate to the fraud team: review account-takeover signals, force resets for "
                "affected accounts and warn customers about the scam pattern.",
    "usability": "Run a usability review of the affected screens; add in-app guidance and track task "
                 "completion for the confusing flows.",
    "refund": "Audit the refund queue for ageing cases; set a refund SLA and notify customers of "
              "status automatically.",
    "availability": "Check stock-outs and forecast accuracy for the affected products and cities; "
                    "add back-in-stock alerts.",
}
