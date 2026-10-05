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
    "max_hold_bars": [0, 12, 24, 48],
    "daily_trend_days": [0, 20, 60, 120],
}
# Variant dimensions are added to SEARCH_SPACE only after scripts/compare_variants.py
# shows they help out-of-sample under 1x AND 2x costs (see reports/variants-*.md).

GUARDRAILS = {"max_drawdown_pct": 25.0, "min_trades": 40, "min_profit_factor": 1.1}
# A candidate must beat the baseline in at least this many of the OOS folds on
# return, AND improve the median score by a relative margin. Calibrated so the
# false-acceptance rate on pure random walks is low (tests/test_null.py).
MIN_FOLD_WINS = 3
REL_MARGIN = 0.25
ABS_MARGIN = 0.15


def score(stats: dict) -> float:
    """Return / drawdown style score (Calmar-like), penalising few trades."""
    if stats["trades"] == 0:
        return -1.0
    dd = max(stats["max_drawdown_pct"], 1.0)
    return stats["return_pct"] / dd * min(1.0, stats["trades"] / 20)


def folds(df: pd.DataFrame, n: int = 4, train_frac: float = 0.6,
          warm: int = 300) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]]:
    """Anchored walk-forward. Returns (train, test_with_warmup, oos_start)."""
    size = len(df)
    first_test = int(size * train_frac)
    step = (size - first_test) // n
    out = []
    for k in range(n):
        a, b = first_test + k * step, first_test + (k + 1) * step
        out.append((df.iloc[:a], df.iloc[max(0, a - warm):b], df.index[a]))
    return out


def evaluate(df: pd.DataFrame, settings: Settings, params: StrategyParams, n_folds: int = 4) -> dict:
    res = []
    for _, test, oos_start in folds(df, n_folds, warm=max(300, warmup_bars(params) + 50)):
        res.append(run_backtest(test, settings, params, trade_from=oos_start).stats)
    scores = [score(r) for r in res]
    return {
        "median_score": round(median(scores), 4),
        "worst_dd": max(r["max_drawdown_pct"] for r in res),
        "total_trades": sum(r["trades"] for r in res),
        "median_pf": round(median(min(r["profit_factor"], 10.0) for r in res), 2),
        "total_return_pct": round(sum(r["return_pct"] for r in res), 2),
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


def clearly_better(cand: dict, base: dict) -> tuple[bool, str]:
    """Paired, per-fold comparison on identical OOS windows."""
    wins = sum(c["return_pct"] > b["return_pct"] for c, b in zip(cand["folds"], base["folds"]))
    need = base["median_score"] + max(ABS_MARGIN, REL_MARGIN * abs(base["median_score"]))
    if wins < MIN_FOLD_WINS:
        return False, f"beats baseline in only {wins}/{len(base['folds'])} folds"
    if cand["median_score"] < need:
        return False, f"median score {cand['median_score']} < required {round(need, 4)}"
    if cand["total_return_pct"] <= base["total_return_pct"]:
        return False, "total OOS return not higher"
    return True, f"wins {wins}/{len(base['folds'])} folds, score {base['median_score']} -> {cand['median_score']}"


def random_candidate(base: StrategyParams, rng: random.Random) -> StrategyParams:
    changes = {k: rng.choice(v) for k, v in SEARCH_SPACE.items() if rng.random() < 0.5}
    cand = replace(base, **changes)
    if cand.ema_fast >= cand.ema_slow:
        cand = replace(cand, ema_fast=max(5, cand.ema_slow // 5))
    return cand


def search(df: pd.DataFrame, settings: Settings, base: StrategyParams,
           trials: int = 40, seed: int = 0) -> dict:
    """Pick ONE candidate using in-sample data only, then give it a single
    out-of-sample test (no selection on OOS results)."""
    rng = random.Random(seed)
    train = df.iloc[: int(len(df) * 0.6)]
    base_is = score(run_backtest(train, settings, base).stats)
    best_is, best = base_is, None
    for _ in range(trials):
        cand = random_candidate(base, rng)
        s = score(run_backtest(train, settings, cand).stats)
        if s > best_is:
            best_is, best = s, cand

    base_oos = evaluate(df, settings, base)
    out = {"accepted": False, "baseline": base_oos, "baseline_is": base_is}
    if best is None:
        out["reason"] = "no candidate beat baseline in-sample"
        return out
    ev = evaluate(df, settings, best)
    out["candidate"] = ev
    ok, why = passes_guardrails(ev)
    if not ok:
        out["reason"] = f"candidate rejected: {why}"
        return out
    better, why = clearly_better(ev, base_oos)
    out["reason"] = why if better else f"candidate rejected: {why}"
    if better:
        out.update(accepted=True, params=best)
    return out
