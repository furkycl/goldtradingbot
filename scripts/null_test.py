"""Calibration: how often does the optimizer accept a fake 'improvement' on
pure random walks (where no strategy can have an edge)? Target <= 5%.
2026-10-05 result: old procedure 45% (independent audit), new procedure 5% (3/60),
before the sealed-holdout gate which filters further."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np, pandas as pd
from multiprocessing import Pool
from goldbot.config import Settings, StrategyParams
from goldbot.optimize import search

def rw(seed, n=8000):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.0018, n)              # pure random walk, ~gold hourly vol
    c = 2500 * np.exp(np.cumsum(r)); o = np.r_[2500, c[:-1]]
    w = np.abs(rng.normal(0, 0.001, n)) * c
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + w, "low": np.minimum(o, c) - w, "close": c}, index=idx)

def run(seed):
    s = Settings(starting_equity=10_000)
    base = StrategyParams(ema_fast=20, ema_slow=100, breakout_lookback=24, atr_stop_mult=2.0,
                          take_profit_r=2.0, trail_atr_mult=2.5, adx_min=18.0)
    r = search(rw(seed), s, base, trials=40, seed=seed)
    return {"seed": seed, "accepted": r["accepted"], "reason": r["reason"],
            "base_ret": r["baseline"]["total_return_pct"], "base_score": r["baseline"]["median_score"]}

if __name__ == "__main__":
    with Pool(2) as p:
        res = p.map(run, range(1000, 1060))
    acc = sum(r["accepted"] for r in res)
    pos = sum(r["base_ret"] > 0 for r in res)
    print(json.dumps({"runs": len(res), "false_accepts": acc, "rate": acc/len(res),
                      "baseline_positive_oos_return": pos}, indent=1))
    from collections import Counter
    print(Counter(r["reason"].split(":")[0] if not r["accepted"] else "ACCEPTED" for r in res))
