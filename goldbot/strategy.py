"""Strategy façade: runs the enabled families (goldbot/strategies) and applies
the shared filters (daily trend, session, news veto, long-only).

Signals are evaluated on bar close and executed on the next bar open. Exits
(ATR stop, R-multiple take profit, trailing after 1R, time stop, per-family
hard exit) and sizing live in backtest.py / engine.py and are identical in both.
"""
from __future__ import annotations

import pandas as pd

from .config import StrategyParams
from .ensemble import Selector
from .indicators import atr
from .strategies import REGISTRY
from .strategies.base import Signal, none

__all__ = ["Signal", "Selector", "prepare", "signal_at", "candidates_at", "warmup_bars",
           "daily_trend", "in_session", "families"]


def families(p: StrategyParams) -> list[str]:
    names = [n for n in (p.strategies or ["breakout"]) if n in REGISTRY]
    return names or ["breakout"]


def prepare(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = atr(out, p.atr_period)
    for name in families(p):
        out = REGISTRY[name].prepare(out, p)
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
    base = max(REGISTRY[n].warmup(p) for n in families(p))
    return max(base, p.atr_period + 5, p.daily_trend_days * 23) + 5


def _filtered(sig: Signal, row: pd.Series, p: StrategyParams, news_sentiment: float) -> Signal:
    if sig.side == 0:
        return sig
    if p.daily_trend_days and float(row.get("daily_trend", 0.0)) * sig.side <= 0:
        return none(row, "against daily trend")
    if not in_session(row.name, p):
        return none(row, "outside session")
    weighted = news_sentiment * p.news_weight
    if abs(news_sentiment) >= p.news_veto_threshold and (weighted * sig.side) < 0:
        return none(row, f"vetoed by news sentiment {news_sentiment:+.2f}")
    return sig


def candidates_at(row: pd.Series, p: StrategyParams, news_sentiment: float = 0.0) -> list[Signal]:
    """One (possibly empty) signal per enabled family, after the shared filters."""
    out = []
    for name in families(p):
        sig = REGISTRY[name].signal(row, p)
        sig.strategy = sig.strategy or name
        out.append(_filtered(sig, row, p, news_sentiment))
    return out


def signal_at(row: pd.Series, p: StrategyParams, news_sentiment: float = 0.0,
              selector: Selector | None = None) -> Signal:
    """Single-family: that family's signal. Ensemble: the selector's pick."""
    cands = candidates_at(row, p, news_sentiment)
    if len(cands) == 1:
        return cands[0]
    chosen = (selector or Selector(families(p), p.ensemble_lookback, p.ensemble_min_score)).pick(cands)
    if chosen is not None:
        return chosen
    reasons = [c.reason for c in cands if c.reason]
    return none(row, "; ".join(reasons[:2]))
