"""Core holding signal (unlevered gold), per docs/STRATEGY.md §3/§5.

Validation 2001-2026: buy & hold was the best long-run method; a 6-month trend
filter cut max drawdown 45% -> 32% at ~3 pts/yr lower return (insurance, not
alpha). This command just reports the facts; it never trades.
"""
from __future__ import annotations

import pandas as pd

from . import daily as D


def core_signal(close: pd.Series) -> dict:
    c = close.dropna()
    last = float(c.iloc[-1])
    out = {"date": str(c.index[-1].date()), "price": round(last, 2),
           "from_high_pct": round(100 * (last / float(c.max()) - 1), 1)}
    for name, n in (("3m", 63), ("6m", 126), ("12m", 252)):
        out[f"ret_{name}_pct"] = round(100 * (last / float(c.iloc[-n - 1]) - 1), 1) if len(c) > n else None
    out["trend_6m_up"] = bool(D.tsmom(c, 126).iloc[-1] > 0)
    vol = c.pct_change().tail(60).std() * (252 ** 0.5)
    out["vol_60d_pct"] = round(100 * float(vol), 1)
    out["advice"] = ("HOLD core position (6m trend up)" if out["trend_6m_up"] else
                     "6m trend DOWN: plain holders keep holding; drawdown-averse holders may reduce "
                     "(historically cut max drawdown, cost ~3 pts/yr)")
    return out
