"""News-spike reaction (calendar-free proxy for data releases).

A bar whose range >= spike_mult * ATR is treated as a shock. Smales (2015):
gold futures traders over-react to newswire messages and prices partly
reverse, so the default mode FADES the spike on the next bar's close when
the close is still beyond the spike's midpoint. `spike_mode: follow` trades
continuation instead. Tight stop (beyond the spike extreme) and 1R target.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr
from .base import Signal, none, ready


def prepare(df: pd.DataFrame, p) -> pd.DataFrame:
    out = df
    if "atr" not in out:
        out["atr"] = atr(out, p.atr_period)
    rng = out["high"] - out["low"]
    out["spike_prev"] = (rng.shift(1) >= p.spike_mult * out["atr"].shift(2)).astype(float)
    out["spike_dir"] = ((out["close"].shift(1) > out["open"].shift(1)).astype(float) * 2 - 1)
    out["spike_mid"] = (out["high"].shift(1) + out["low"].shift(1)) / 2
    out["spike_hi"], out["spike_lo"] = out["high"].shift(1), out["low"].shift(1)
    return out


def warmup(p) -> int:
    return p.atr_period + 5


def signal(row: pd.Series, p) -> Signal:
    if not ready(row, "spike_prev", "spike_mid", "spike_hi", "spike_lo") or row["spike_prev"] < 1:
        return none(row)
    close, a = float(row["close"]), float(row["atr"])
    d = int(row["spike_dir"])
    beyond_mid = (close - row["spike_mid"]) * d > 0
    if not beyond_mid:
        return none(row, "spike already retraced")
    if p.spike_mode == "follow":
        side, stop = d, float(row["spike_mid"])
    else:
        side = -d
        stop = float(row["spike_hi"]) + 0.25 * a if d > 0 else float(row["spike_lo"]) - 0.25 * a
    dist = abs(close - stop)
    if dist < 0.3 * a or dist > p.atr_stop_mult * a:
        return none(row, "spike stop out of range")
    tp = close + side * dist * p.take_profit_r
    return Signal(side, close, stop, tp, a, f"spike {p.spike_mode} {'long' if side > 0 else 'short'}",
                  "spike", hard_exit_bars=max(p.max_hold_bars, 6))
