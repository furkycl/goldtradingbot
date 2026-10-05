"""Strategy families. Each exposes:

    prepare(df, p)  -> DataFrame with the columns it needs (no lookahead)
    signal(row, p)  -> Signal (side 0 when nothing to do)
    warmup(p)       -> bars of history required

Exits (ATR stop, R-multiple TP, trailing, time stop) and position sizing are
shared and live in backtest.py / engine.py, so every family is judged on the
quality of its ENTRIES alone, under identical risk rules.
"""
from __future__ import annotations

from . import breakout, meanrev, overnight, spike, squeeze

REGISTRY = {
    "breakout": breakout,
    "squeeze": squeeze,
    "overnight": overnight,
    "spike": spike,
    "meanrev": meanrev,
}

__all__ = ["REGISTRY"]
