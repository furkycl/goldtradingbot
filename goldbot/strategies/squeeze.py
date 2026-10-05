"""Volatility-compression breakout.

Bollinger band width at a `squeeze_pct` percentile low of the last
`squeeze_lookback` bars = energy stored. Enter on the first close outside the
bands in the direction of the fast EMA slope. Different trigger from the
Donchian breakout: it fires after quiet periods, not after a run-up.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr, ema
from .base import Signal, make, none, ready


def prepare(df: pd.DataFrame, p) -> pd.DataFrame:
    out = df
    if "atr" not in out:
        out["atr"] = atr(out, p.atr_period)
    mid = out["close"].rolling(20).mean()
    sd = out["close"].rolling(20).std()
    out["bb_up"], out["bb_low"] = mid + 2 * sd, mid - 2 * sd
    width = (out["bb_up"] - out["bb_low"]) / mid
    # percentile rank of the PREVIOUS bar's width within the lookback (no lookahead)
    out["bb_width_pct"] = width.shift(1).rolling(p.squeeze_lookback).rank(pct=True)
    out["ema_slope"] = ema(out["close"], p.ema_fast).diff(3)
    return out


def warmup(p) -> int:
    return p.squeeze_lookback + 25


def signal(row: pd.Series, p) -> Signal:
    if not ready(row, "bb_up", "bb_low", "bb_width_pct", "ema_slope"):
        return none(row)
    if row["bb_width_pct"] > p.squeeze_pct:
        return none(row)
    close = float(row["close"])
    if close > row["bb_up"] and row["ema_slope"] > 0:
        return make(row, p, 1, "squeeze", "squeeze breakout long")
    if close < row["bb_low"] and row["ema_slope"] < 0:
        return make(row, p, -1, "squeeze", "squeeze breakout short")
    return none(row)
