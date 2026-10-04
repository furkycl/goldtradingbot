"""Trend-following breakout strategy with news-sentiment filter.

Signal (evaluated on bar close, executed on next bar open):
  LONG  when close > Donchian upper, EMA fast > EMA slow, ADX >= adx_min
  SHORT when close < Donchian lower, EMA fast < EMA slow, ADX >= adx_min
News sentiment in [-1, 1] (positive = bullish gold) can veto trades that go
against a strong news bias. Exits: ATR stop, R-multiple take profit, ATR
trailing stop after price moves 1R in favour.

Why this design: gold trends persistently around macro shocks (rates, USD,
geopolitics); breakout + trend filter is the most robust family in public
research for XAU, and the news filter avoids fading strong headline flows.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import StrategyParams
from .indicators import adx, atr, donchian, ema


@dataclass
class Signal:
    side: int          # +1 long, -1 short, 0 none
    entry_ref: float   # reference price (bar close)
    stop: float
    take_profit: float
    atr: float
    reason: str


def prepare(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], p.ema_fast)
    out["ema_slow"] = ema(out["close"], p.ema_slow)
    out["atr"] = atr(out, p.atr_period)
    out["adx"] = adx(out, p.adx_period)
    out["dc_up"], out["dc_low"] = donchian(out, p.breakout_lookback)
    return out


def warmup_bars(p: StrategyParams) -> int:
    return max(p.ema_slow, p.breakout_lookback, p.atr_period, p.adx_period) + 5


def signal_at(row: pd.Series, p: StrategyParams, news_sentiment: float = 0.0) -> Signal:
    none = Signal(0, float(row["close"]), 0.0, 0.0, float(row.get("atr", 0) or 0), "")
    if pd.isna(row.get("dc_up")) or pd.isna(row.get("atr")) or row["atr"] <= 0:
        return none
    close, a = float(row["close"]), float(row["atr"])
    trending = row["adx"] >= p.adx_min
    side = 0
    if trending and close > row["dc_up"] and row["ema_fast"] > row["ema_slow"]:
        side = 1
    elif trending and close < row["dc_low"] and row["ema_fast"] < row["ema_slow"]:
        side = -1
    if side == 0:
        return none

    weighted = news_sentiment * p.news_weight
    if abs(news_sentiment) >= p.news_veto_threshold and (weighted * side) < 0:
        return Signal(0, close, 0, 0, a, f"vetoed by news sentiment {news_sentiment:+.2f}")

    stop = close - side * p.atr_stop_mult * a
    tp = close + side * p.atr_stop_mult * a * p.take_profit_r
    return Signal(side, close, stop, tp, a, "breakout long" if side > 0 else "breakout short")
