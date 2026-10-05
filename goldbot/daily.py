"""Daily-bar strategies (vectorised) for the long-horizon comparison.

All positions are decided on the close of day t and earn the return of day t+1
(close-to-close), so there is no lookahead. Costs: `cost_bps` per unit of
position change (spread + commission), and `financing_pct` per year on the
absolute position (CFD swap; set 0 for physical/ETF/token).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def returns_from_positions(close: pd.Series, pos: pd.Series, cost_bps: float = 3.0,
                           financing_pct: float = 0.0) -> pd.Series:
    r = close.pct_change().fillna(0.0)
    held = pos.shift(1).fillna(0.0)                       # decided yesterday, earns today
    turnover = pos.diff().abs().fillna(pos.abs())
    cost = turnover.shift(1).fillna(0.0) * cost_bps / 1e4
    fin = held.abs() * financing_pct / 100 / TRADING_DAYS
    return held * r - cost - fin


def stats(rets: pd.Series) -> dict:
    rets = rets.dropna()
    if rets.empty:
        return {}
    eq = (1 + rets).cumprod()
    years = len(rets) / TRADING_DAYS
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else -1.0
    dd = (1 - eq / eq.cummax()).max()
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    sharpe = rets.mean() / rets.std() * np.sqrt(TRADING_DAYS) if rets.std() > 0 else 0.0
    return {"cagr_pct": round(100 * cagr, 2), "total_pct": round(100 * (eq.iloc[-1] - 1), 1),
            "max_dd_pct": round(100 * dd, 1), "vol_pct": round(100 * vol, 1),
            "sharpe": round(float(sharpe), 2),
            "calmar": round(float(cagr / dd), 2) if dd > 0 else 0.0,
            "years": round(years, 1)}


# ------------------------------------------------------------------ strategies
def buy_hold(close: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=close.index)


def tsmom(close: pd.Series, lookback: int = 252, long_only: bool = True) -> pd.Series:
    """Time-series momentum: long if the past `lookback`-day return > 0."""
    sig = np.sign(close / close.shift(lookback) - 1).fillna(0.0)
    return sig.clip(lower=0) if long_only else sig


def sma_filter(close: pd.Series, n: int = 200) -> pd.Series:
    return (close > close.rolling(n).mean()).astype(float)


def donchian_daily(close: pd.Series, high: pd.Series, low: pd.Series, entry: int = 55,
                   exit_: int = 20, long_only: bool = True) -> pd.Series:
    """Turtle-style: enter on `entry`-day high break, exit on `exit_`-day low."""
    up = high.rolling(entry).max().shift(1)
    lo_exit = low.rolling(exit_).min().shift(1)
    dn = low.rolling(entry).min().shift(1)
    hi_exit = high.rolling(exit_).max().shift(1)
    pos = np.zeros(len(close))
    c = close.to_numpy()
    for i in range(1, len(c)):
        p = pos[i - 1]
        if p > 0 and c[i] < lo_exit.iloc[i]:
            p = 0
        elif p < 0 and c[i] > hi_exit.iloc[i]:
            p = 0
        if p == 0:
            if c[i] > up.iloc[i]:
                p = 1
            elif not long_only and c[i] < dn.iloc[i]:
                p = -1
        pos[i] = p
    return pd.Series(pos, index=close.index)


def vol_target(close: pd.Series, pos: pd.Series, target_pct: float = 15.0,
               max_lev: float = 2.0, window: int = 60) -> pd.Series:
    """Scale a {0,1,-1} position so realised vol ~ target (uses past data only)."""
    vol = close.pct_change().rolling(window).std() * np.sqrt(TRADING_DAYS)
    scale = (target_pct / 100 / vol).clip(upper=max_lev).fillna(0.0)
    return pos * scale


def random_exposure(n: int, frac_in: float, mean_hold: int, rng: np.random.Generator) -> np.ndarray:
    """Random long/flat timing with the same time-in-market and average holding period."""
    pos = np.zeros(n)
    i, state = 0, rng.random() < frac_in
    mean_out = max(1, int(mean_hold * (1 - frac_in) / max(frac_in, 1e-6)))
    while i < n:
        length = max(1, int(rng.exponential(mean_hold if state else mean_out)))
        pos[i:i + length] = 1.0 if state else 0.0
        i += length
        state = not state
    return pos
