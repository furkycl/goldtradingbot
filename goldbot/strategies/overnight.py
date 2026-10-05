"""Asian-session long (intraday seasonality).

Blose & Gondhalekar (2014): COMEX gold overnight returns are significantly
positive and day returns negative (1985-2012, effect shrinking). Long at
`overnight_start_utc` when the slow trend is up, hard exit after
`overnight_bars` bars (before London/NY), ATR stop as usual. Long only.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr, ema
from .base import Signal, make, none, ready


def prepare(df: pd.DataFrame, p) -> pd.DataFrame:
    out = df
    if "atr" not in out:
        out["atr"] = atr(out, p.atr_period)
    if "ema_slow" not in out:
        out["ema_slow"] = ema(out["close"], p.ema_slow)
    return out


def warmup(p) -> int:
    return p.ema_slow + 5


def signal(row: pd.Series, p) -> Signal:
    if not ready(row, "ema_slow"):
        return none(row)
    ts = row.name
    hour = ts.tz_convert("UTC").hour if getattr(ts, "tzinfo", None) else ts.hour
    if hour != p.overnight_start_utc:
        return none(row)
    if float(row["close"]) <= row["ema_slow"]:
        return none(row, "overnight: trend down")
    return make(row, p, 1, "overnight", "overnight long", hard_exit_bars=p.overnight_bars)
