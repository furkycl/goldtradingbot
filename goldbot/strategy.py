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
from .indicators import atr, ema
from .strategies import REGISTRY
from .strategies.base import Signal, none

__all__ = ["Signal", "Selector", "prepare", "signal_at", "candidates_at", "warmup_bars",
           "daily_trend", "in_session", "families", "confluence", "tier_multiplier"]


def families(p: StrategyParams) -> list[str]:
    names = [n for n in (p.strategies or ["breakout"]) if n in REGISTRY]
    return names or ["breakout"]


def prepare(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = atr(out, p.atr_period)
    for name in families(p):
        out = REGISTRY[name].prepare(out, p)
    out["daily_trend"] = daily_trend(out["close"], p.daily_trend_days) if p.daily_trend_days else 0.0
    # shared confluence inputs (always computed; cheap)
    if "ema_fast" not in out:
        out["ema_fast"] = ema(out["close"], p.ema_fast)
    if "ema_slow" not in out:
        out["ema_slow"] = ema(out["close"], p.ema_slow)
    out["conf_daily"] = daily_trend(out["close"], 20)
    out["atr_pct"] = out["atr"].shift(1).rolling(200, min_periods=50).rank(pct=True)
    return out


def confluence(row: pd.Series, side: int, news_sentiment: float, agree: int) -> tuple[float, str]:
    """Quality score in [0, 1]. Each component is evidence-based (docs/RESEARCH.md):
    trend (EMA), 20-day trend, news direction, London/NY liquidity, non-extreme
    volatility, not chasing (stretch from fast EMA), agreement between families."""
    a = float(row["atr"]) or 1e-9
    close = float(row["close"])
    parts = {}
    parts["trend"] = 1.0 if (float(row["ema_fast"]) - float(row["ema_slow"])) * side > 0 else 0.0
    d = float(row.get("conf_daily", 0.0))
    parts["daily"] = 1.0 if d * side > 0 else (0.5 if d == 0 else 0.0)
    ns = news_sentiment * side
    parts["news"] = 1.0 if ns > 0.2 else (0.5 if abs(news_sentiment) <= 0.2 else 0.0)
    ts = row.name
    hour = ts.tz_convert("UTC").hour if getattr(ts, "tzinfo", None) else ts.hour
    parts["session"] = 1.0 if 7 <= hour < 17 else 0.5
    vp = row.get("atr_pct", float("nan"))
    parts["vol"] = 1.0 if (vp == vp and 0.2 <= float(vp) <= 0.8) else 0.5
    stretch = abs(close - float(row["ema_fast"])) / a
    parts["stretch"] = 1.0 if stretch <= 2.0 else (0.5 if stretch <= 3.0 else 0.0)
    parts["agree"] = 1.0 if agree >= 1 else 0.5
    weights = {"trend": 2, "daily": 1.5, "news": 1.5, "session": 1, "vol": 1, "stretch": 1.5, "agree": 1}
    score = sum(parts[k] * w for k, w in weights.items()) / sum(weights.values())
    return round(score, 3), " ".join(k for k, v in parts.items() if v >= 1.0)


def tier_multiplier(score: float, tiers: list) -> float:
    for lo, mult in sorted(tiers, key=lambda t: -float(t[0])):
        if score >= float(lo):
            return float(mult)
    return float(sorted(tiers, key=lambda t: float(t[0]))[0][1]) if tiers else 1.0


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
    return max(base, p.atr_period + 5, p.daily_trend_days * 23, 21 * 23 if p.confluence_tiers else 0) + 5


def _filtered(sig: Signal, row: pd.Series, p: StrategyParams, news_sentiment: float) -> Signal:
    if sig.side == 0:
        return sig
    if p.daily_trend_days and float(row.get("daily_trend", 0.0)) * sig.side <= 0:
        return none(row, "against daily trend")
    if not in_session(row.name, p):
        return none(row, "outside session")
    if p.max_entry_stretch_atr and "ema_fast" in row.index and float(row["atr"]) > 0:
        if abs(float(row["close"]) - float(row["ema_fast"])) / float(row["atr"]) > p.max_entry_stretch_atr:
            return none(row, "overextended: not chasing")
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
    if p.confluence_tiers:
        for sig in out:
            if sig.side:
                agree = sum(1 for o in out if o is not sig and o.side == sig.side)
                score, why = confluence(row, sig.side, news_sentiment, agree)
                sig.risk_mult = tier_multiplier(score, p.confluence_tiers)
                sig.reason += f" [conf {score:.2f}: {why}]"
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
