from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    side: int              # +1 long, -1 short, 0 none
    entry_ref: float       # reference price (bar close)
    stop: float
    take_profit: float
    atr: float
    reason: str
    strategy: str = ""
    hard_exit_bars: int = 0    # close unconditionally after N bars (0 = off)


def none(row: pd.Series, reason: str = "") -> Signal:
    a = row.get("atr", 0.0)
    return Signal(0, float(row["close"]), 0.0, 0.0, float(a) if a == a else 0.0, reason)


def make(row: pd.Series, p, side: int, name: str, reason: str, stop_mult: float | None = None,
         tp_r: float | None = None, hard_exit_bars: int = 0) -> Signal:
    close, a = float(row["close"]), float(row["atr"])
    sm = p.atr_stop_mult if stop_mult is None else stop_mult
    tr = p.take_profit_r if tp_r is None else tp_r
    stop = close - side * sm * a
    tp = close + side * sm * a * tr
    return Signal(side, close, stop, tp, a, reason, name, hard_exit_bars)


def ready(row: pd.Series, *cols: str) -> bool:
    if pd.isna(row.get("atr")) or float(row["atr"]) <= 0:
        return False
    return all(not pd.isna(row.get(c)) for c in cols)
