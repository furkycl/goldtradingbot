"""Donchian breakout + EMA trend filter (+ optional ADX, daily trend, session)."""
from __future__ import annotations

import pandas as pd

from ..indicators import adx, atr, donchian, ema
from .base import Signal, make, none, ready


def prepare(df: pd.DataFrame, p) -> pd.DataFrame:
    out = df
    out["ema_fast"] = ema(out["close"], p.ema_fast)
    out["ema_slow"] = ema(out["close"], p.ema_slow)
    if "atr" not in out:
        out["atr"] = atr(out, p.atr_period)
    out["adx"] = adx(out, p.adx_period)
    out["dc_up"], out["dc_low"] = donchian(out, p.breakout_lookback)
    return out


def warmup(p) -> int:
    return max(p.ema_slow, p.breakout_lookback, p.atr_period, p.adx_period) + 5


def signal(row: pd.Series, p) -> Signal:
    if not ready(row, "dc_up", "dc_low", "ema_fast", "ema_slow", "adx"):
        return none(row)
    close = float(row["close"])
    trending = row["adx"] >= p.adx_min
    if trending and close > row["dc_up"] and row["ema_fast"] > row["ema_slow"]:
        return make(row, p, 1, "breakout", "breakout long")
    if trending and close < row["dc_low"] and row["ema_fast"] < row["ema_slow"]:
        return make(row, p, -1, "breakout", "breakout short")
    return none(row)
