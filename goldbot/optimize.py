"""Walk-forward parameter search used by the self-improvement loop.

Overfitting is the #1 way trading bots die, so a candidate is only accepted if:
  * it is evaluated on OUT-OF-SAMPLE folds it was not tuned on,
  * it beats the current params on the median OOS score across folds,
  * it passes hard guardrails (max drawdown, min trades, profit factor),
  * the improvement exceeds a margin (noise filter).
"""
from __future__ import annotations

import random
from dataclasses import replace
from statistics import median

import pandas as pd

from .backtest import run_backtest
from .config import Settings, StrategyParams
from .strategy import warmup_bars

SEARCH_SPACE = {
    "ema_fast": [10, 20, 30, 50],
    "ema_slow": [100, 150, 200],
    "breakout_lookback": [12, 24, 36, 48, 72],
    "atr_stop_mult": [1.5, 2.0, 2.5, 3.0],
    "take_profit_r": [1.5, 2.0, 2.5, 3.0, 4.0],
    "trail_atr_mult": [2.0, 2.5, 3.0, 3.5],
    "adx_min": [0.0, 15.0, 18.0, 22.0, 25.0],
}
# Variant dimensions are added to SEARCH_SPACE only after scripts/compare_variants.py
# shows they help out-of-sample under 1x AND 2x costs (see reports/variants-*.md).

GUARDRAILS = {"max_drawdown_pct": 25.0, "min_trades": 8, "min_profit_factor": 1.1}
MIN_IMPROVEMENT = 0.10   # median OOS score must improve by this much


def score(stats: dict) -> float:
    """Return / drawdown style score (Calmar-like), penalising few trades."""
    if stats["trades"] == 0:
        return -1.0
    dd = max(stats["max_drawdown_pct"], 1.0)
    return stats["return_pct"] / dd * min(1.0, stats["trades"] / 20)


def folds(df: pd.DataFrame, n: int = 4, train_frac: float = 0.6,
          warm: int = 300) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Anchored walk-forward: train on [0, k), test on [k, k+step)."""
    size = len(df)
    first_test = int(size * train_frac)
    step = (size - first_test) // n
    out = []
    for k in range(n):
        a, b = first_test + k * step, first_test + (k + 1) * step
        out.append((df.iloc[:a], df.iloc[max(0, a - warm):b]))
    return out


def evaluate(df: pd.DataFrame, settings: Settings, params: StrategyParams, n_folds: int = 4) -> dict:
    res = []
    for _, test in folds(df, n_folds, warm=max(300, warmup_bars(params) + 50)):
        st = run_backtest(test, settings, params).stats
        res.append(st)
    scores = [score(r) for r in res]
    return {
        "median_score": round(median(scores), 4),
        "worst_dd": max(r["max_drawdown_pct"] for r in res),
        "total_trades": sum(r["trades"] for r in res),
        "median_pf": round(median(r["profit_factor"] for r in res), 2),
        "folds": res,
    }


def passes_guardrails(ev: dict) -> tuple[bool, str]:
    if ev["worst_dd"] > GUARDRAILS["max_drawdown_pct"]:
        return False, f"drawdown {ev['worst_dd']}% > {GUARDRAILS['max_drawdown_pct']}%"
    if ev["total_trades"] < GUARDRAILS["min_trades"]:
        return False, f"only {ev['total_trades']} OOS trades"
    if ev["median_pf"] < GUARDRAILS["min_profit_factor"]:
        return False, f"profit factor {ev['median_pf']} < {GUARDRAILS['min_profit_factor']}"
    return True, "ok"


def random_candidate(base: StrategyParams, rng: random.Random) -> StrategyParams:
    changes = {k: rng.choice(v) for k, v in SEARCH_SPACE.items() if rng.random() < 0.5}
    cand = replace(base, **changes)
    if cand.ema_fast >= cand.ema_slow:
        cand = replace(cand, ema_fast=max(5, cand.ema_slow // 5))
    return cand


def search(df: pd.DataFrame, settings: Settings, base: StrategyParams,
           trials: int = 40, seed: int = 0) -> dict:
    """Tune on the in-sample part only, then judge winners on OOS folds."""
    rng = random.Random(seed)
    train = df.iloc[: int(len(df) * 0.6)]
    base_is = score(run_backtest(train, settings, base).stats)
    ranked = []
    for _ in range(trials):
        cand = random_candidate(base, rng)
        ranked.append((score(run_backtest(train, settings, cand).stats), cand))
    ranked.sort(key=lambda t: t[0], reverse=True)

    base_oos = evaluate(df, settings, base)
    best = {"accepted": False, "reason": "no candidate beat baseline in-sample",
            "baseline": base_oos, "baseline_is": base_is}
    for is_score, cand in ranked[:5]:
        if is_score <= base_is:
            break
        ev = evaluate(df, settings, cand)
        ok, why = passes_guardrails(ev)
        better = ev["median_score"] >= base_oos["median_score"] + MIN_IMPROVEMENT
        if ok and better:
            return {"accepted": True, "params": cand, "candidate": ev, "baseline": base_oos,
                    "reason": f"OOS median score {base_oos['median_score']} -> {ev['median_score']}"}
        best["reason"] = f"top candidate rejected: {why if not ok else 'OOS improvement below margin'}"
    return best
