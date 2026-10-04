"""Market data sources.

- load_csv: OHLC CSV with a datetime column (e.g. exported from MT5 / Dukascopy).
- load_yfinance: free gold futures data (GC=F) for research; NOT tick-accurate.
- synthetic_ohlc: deterministic random-walk data for tests.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.lower() for c in df.columns})
    if not isinstance(df.index, pd.DatetimeIndex):
        for cand in ("datetime", "date", "time", "timestamp"):
            if cand in df.columns:
                df = df.set_index(pd.to_datetime(df[cand], utc=True)).drop(columns=[cand])
                break
    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        raise ValueError(f"missing OHLC columns: {missing}")
    df = df[OHLC + [c for c in ("volume",) if c in df.columns]].astype(float)
    return df.sort_index().dropna()


def load_csv(path: str | Path) -> pd.DataFrame:
    return normalize(pd.read_csv(path))


def load_yfinance(symbol: str = "GC=F", period: str = "730d", interval: str = "1h") -> pd.DataFrame:
    import yfinance as yf  # optional dependency

    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = normalize(df)
    if len(df) < 500:
        raise RuntimeError(f"yfinance returned only {len(df)} bars for {symbol}")
    return df


def synthetic_ohlc(n: int = 3000, seed: int = 7, start_price: float = 2000.0,
                   drift: float = 0.00002, vol: float = 0.003, freq: str = "1h") -> pd.DataFrame:
    """Regime-switching random walk: alternates trending and choppy segments."""
    rng = np.random.default_rng(seed)
    regime = np.repeat(rng.choice([-1, 0, 1], size=n // 200 + 1), 200)[:n]
    rets = rng.normal(drift + regime * vol * 0.15, vol, n)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]])
    wiggle = np.abs(rng.normal(0, vol * 0.6, n)) * close
    high = np.maximum(open_, close) + wiggle
    low = np.minimum(open_, close) - wiggle
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)
