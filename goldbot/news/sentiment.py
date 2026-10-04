"""Gold-specific headline sentiment.

Score in [-1, 1]: positive = bullish for gold (XAU/USD up).
Lexicon is built around the main macro drivers of gold:
  real rates / Fed path, USD strength, risk-off / geopolitics,
  inflation, central-bank buying, ETF flows.
Deterministic and dependency-free so it can be backtested and unit-tested.
An LLM scorer can be plugged in via NewsAggregator(scorer=...).
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone

# (pattern, weight). Positive -> bullish gold.
LEXICON: list[tuple[str, float]] = [
    # Fed / rates
    (r"\brate cuts?\b|\bcuts? rates?\b|\bdovish\b|\beasing\b", 0.8),
    (r"\brate hikes?\b|\bhikes? rates?\b|\bhawkish\b|\btightening\b", -0.8),
    (r"\b(treasury|bond) yields? (fall|drop|slide|tumble|decline)", 0.6),
    (r"\b(treasury|bond) yields? (rise|jump|climb|surge|spike)", -0.6),
    (r"\breal yields? (fall|drop|decline)", 0.7),
    (r"\breal yields? (rise|climb|jump)", -0.7),
    # USD
    (r"\b(dollar|usd|dxy) (weakens|falls|slides|drops|slumps|tumbles)", 0.6),
    (r"\b(dollar|usd|dxy) (strengthens|rises|rallies|jumps|surges|firms)", -0.6),
    # risk-off / geopolitics
    (r"\bsafe[- ]haven\b", 0.5),
    (r"\b(war|invasion|missile|airstrike|attack|escalat\w+|conflict)\b", 0.5),
    (r"\b(ceasefire|peace (deal|talks)|de-?escalat\w+)\b", -0.4),
    (r"\b(recession|crisis|turmoil|sell-?off|crash)\b", 0.4),
    (r"\bbank (failure|collapse|run)\b", 0.6),
    # inflation
    (r"\b(inflation|cpi|pce) (hotter|higher|rises|accelerat\w+|beats)", 0.2),
    (r"\b(inflation|cpi|pce) (cooler|lower|falls|eases|slows)", 0.3),
    # jobs (strong jobs -> hawkish -> bearish gold)
    (r"\b(payrolls?|nfp|jobs) (beat|surge|jump|strong)", -0.5),
    (r"\b(payrolls?|nfp|jobs) (miss|weak|slump|disappoint)", 0.5),
    # flows
    (r"\bcentral banks? (buy|buying|add\w*|purchas\w+)\b", 0.6),
    (r"\b(etf|spdr|gld) (inflows?|holdings rise)", 0.5),
    (r"\b(etf|spdr|gld) (outflows?|holdings fall)", -0.5),
    # direct price talk
    (r"\bgold (rises|rallies|jumps|surges|climbs|gains|hits record|record high)", 0.5),
    (r"\bgold (falls|drops|slides|tumbles|slumps|declines|retreats)", -0.5),
    (r"\b(altın|ons) (yükseldi|rekor|yükseliş)", 0.5),
    (r"\b(altın|ons) (düştü|geriledi|düşüş)", -0.5),
    (r"\bfaiz indirimi\b", 0.7),
    (r"\bfaiz artırımı\b", -0.7),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), w) for p, w in LEXICON]
_GOLD_TOPIC = re.compile(r"\b(gold|xau|bullion|precious metals?|fed|fomc|powell|"
                         r"dollar|treasur|yield|inflation|cpi|payroll|nfp|"
                         r"altın|ons|fed|faiz)\w*", re.IGNORECASE)


def is_relevant(text: str) -> bool:
    return bool(_GOLD_TOPIC.search(text))


def score_headline(text: str) -> float:
    total = sum(w for rx, w in _COMPILED if rx.search(text))
    return max(-1.0, min(1.0, math.tanh(total)))


def aggregate(items: list[tuple[datetime, float]], now: datetime | None = None,
              half_life_min: float = 90.0) -> float:
    """Exponentially time-decayed mean of headline scores, in [-1, 1]."""
    now = now or datetime.now(timezone.utc)
    num = den = 0.0
    for ts, s in items:
        age = max(0.0, (now - ts).total_seconds() / 60)
        w = 0.5 ** (age / half_life_min)
        num += w * s
        den += w
    return max(-1.0, min(1.0, num / den)) if den > 1e-6 else 0.0
