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
    out["daily_trend"] = daily_trend(out["close"], p.daily_trend_days) if p.daily_trend_days else 0.0
    return out


def daily_trend(close: pd.Series, days: int) -> pd.Series:
    """Sign of the N-day return using ONLY completed prior days (no lookahead)."""
    daily = close.resample("1D").last().dropna()
    trend = (daily / daily.shift(days) - 1).shift(1)          # known at the start of each day
    trend.index = trend.index.normalize()
    keys = close.index.normalize()
    return pd.Series(trend.reindex(keys).to_numpy(), index=close.index).fillna(0.0)


def in_session(ts: pd.Timestamp, p: StrategyParams) -> bool:
    if p.session_start_utc < 0 or p.session_end_utc < 0:
        return True
    h = ts.tz_convert("UTC").hour if ts.tzinfo else ts.hour
    if p.session_start_utc <= p.session_end_utc:
        return p.session_start_utc <= h < p.session_end_utc
    return h >= p.session_start_utc or h < p.session_end_utc


def warmup_bars(p: StrategyParams) -> int:
    return max(p.ema_slow, p.breakout_lookback, p.atr_period, p.adx_period,
               p.daily_trend_days * 23) + 5


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
    if p.daily_trend_days and float(row.get("daily_trend", 0.0)) * side <= 0:
        return Signal(0, close, 0, 0, a, "against daily trend")
    if not in_session(row.name, p):
        return Signal(0, close, 0, 0, a, "outside session")

    weighted = news_sentiment * p.news_weight
    if abs(news_sentiment) >= p.news_veto_threshold and (weighted * side) < 0:
        return Signal(0, close, 0, 0, a, f"vetoed by news sentiment {news_sentiment:+.2f}")

    stop = close - side * p.atr_stop_mult * a
    tp = close + side * p.atr_stop_mult * a * p.take_profit_r
    return Signal(side, close, stop, tp, a, "breakout long" if side > 0 else "breakout short")
