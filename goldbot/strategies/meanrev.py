"""Mean reversion in non-trending regimes.

Close beyond a `meanrev_bb`-sigma Bollinger band while ADX < meanrev_adx_max.
Target = the middle band (so the R multiple is whatever the band gap gives,
capped by take_profit_r), stop = ATR. Opposite regime to the breakouts, which
is what makes it useful in an ensemble.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import adx, atr
from .base import Signal, none, ready


def prepare(df: pd.DataFrame, p) -> pd.DataFrame:
    out = df
    if "atr" not in out:
        out["atr"] = atr(out, p.atr_period)
    if "adx" not in out:
        out["adx"] = adx(out, p.adx_period)
    mid = out["close"].rolling(20).mean()
    sd = out["close"].rolling(20).std()
    out["mr_mid"] = mid
    out["mr_up"], out["mr_low"] = mid + p.meanrev_bb * sd, mid - p.meanrev_bb * sd
    return out


def warmup(p) -> int:
    return max(25, p.adx_period + 5)


def signal(row: pd.Series, p) -> Signal:
    if not ready(row, "mr_mid", "mr_up", "mr_low", "adx"):
        return none(row)
    if row["adx"] >= p.meanrev_adx_max:
        return none(row)
    close, a = float(row["close"]), float(row["atr"])
    if close < row["mr_low"]:
        side = 1
    elif close > row["mr_up"]:
        side = -1
    else:
        return none(row)
    stop = close - side * p.atr_stop_mult * a
    tp_dist = min(abs(float(row["mr_mid"]) - close), p.atr_stop_mult * a * p.take_profit_r)
    if tp_dist < 0.5 * a:
        return none(row, "meanrev target too close")
    return Signal(side, close, stop, close + side * tp_dist, a,
                  f"meanrev {'long' if side > 0 else 'short'}", "meanrev", hard_exit_bars=max(p.max_hold_bars, 12))
