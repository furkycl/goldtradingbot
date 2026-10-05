"""Judge every strategy family and the ensemble on real data, holdout-safe.

For each configuration: walk-forward OOS folds (same machinery as the weekly
loop), random-entry benchmark (same exits/sizing/costs, random entries),
cost tiers 1x/2x, long/short attribution. Writes reports/strategies-DATE.{md,json}.
Run monthly by research.yml; never looks at the sealed holdout.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldbot import data  # noqa: E402
from goldbot.backtest import run_backtest  # noqa: E402
from goldbot.config import ROOT, load_params, load_settings  # noqa: E402
from goldbot.optimize import evaluate, passes_guardrails  # noqa: E402
from goldbot.strategies import REGISTRY  # noqa: E402
from goldbot.strategy import warmup_bars  # noqa: E402

N_RANDOM = 150
ALL = list(REGISTRY)


def configs(base):
    out = {}
    for name in ALL:
        out[f"{name}"] = replace(base, strategies=[name])
    out["spike follow"] = replace(base, strategies=["spike"], spike_mode="follow")
    out["ensemble: all"] = replace(base, strategies=ALL)
    out["ensemble: breakout+squeeze"] = replace(base, strategies=["breakout", "squeeze"])
    out["ensemble: breakout+meanrev"] = replace(base, strategies=["breakout", "meanrev"])
    out["ensemble: all + vol-scaled risk"] = replace(base, strategies=ALL, risk_vol_scaling=True)
    out["breakout + vol-scaled risk"] = replace(base, strategies=["breakout"], risk_vol_scaling=True)
    return out


def _cost(s, m):
    s = replace(s); s.spread *= m; s.commission_per_lot *= m; s.financing_pct_per_year *= m
    return s


def random_benchmark(df, s, p, start, rng):
    real = run_backtest(df, s, p, trade_from=start)
    tr = real.trades
    n_bars = len(df) - df.index.searchsorted(start)
    held = sum(df.index.searchsorted(t.exit_time) - df.index.searchsorted(t.entry_time) + 1 for t in tr)
    q = len(tr) / max(1, n_bars - held)
    long_frac = sum(t.side > 0 for t in tr) / max(1, len(tr))
    rets = []
    for _ in range(N_RANDOM):
        r = np.random.default_rng(rng.integers(1 << 31))

        def fn(i, ts, r=r):
            return (1 if r.random() < long_frac else -1) if r.random() < q else 0
        rets.append(run_backtest(df, s, p, trade_from=start, entry_fn=fn).stats["return_pct"])
    rets = np.array(rets)
    return real, {"median": round(float(np.median(rets)), 2), "p95": round(float(np.percentile(rets, 95)), 2),
                  "p_value": round(float((rets >= real.stats["return_pct"]).mean()), 3)}


def main() -> int:
    settings, base = load_settings(), load_params()
    settings.starting_equity = 10_000
    hold = pd.Timestamp(yaml.safe_load((ROOT / "config" / "validation.yaml").read_text())["holdout_start"], tz="UTC")
    try:
        df = data.load_yfinance("GC=F", "730d", base.timeframe).loc[: hold - pd.Timedelta(seconds=1)]
    except Exception as exc:
        print("data download failed:", exc)
        return 1
    rng = np.random.default_rng(20261005)
    rows = []
    for label, p in configs(base).items():
        start = df.index[warmup_bars(p) + 50]
        real, rb = random_benchmark(df, settings, p, start, rng)
        st = real.stats
        st2 = run_backtest(df, _cost(settings, 2), p, trade_from=start).stats
        wf = evaluate(df, settings, p)
        ok, why = passes_guardrails(wf)
        by = {}
        for t in real.trades:
            d = by.setdefault(t.strategy, {"n": 0, "pnl": 0.0, "wins": 0})
            d["n"] += 1; d["pnl"] += t.pnl; d["wins"] += t.pnl > 0
        rows.append({"config": label, "strategies": p.strategies, "period": f"{start:%Y-%m-%d}→{df.index[-1]:%Y-%m-%d}",
                     "return_pct": st["return_pct"], "max_dd_pct": st["max_drawdown_pct"], "trades": st["trades"],
                     "pf": st["profit_factor"], "win_rate": st["win_rate_pct"], "sharpe": st["sharpe"],
                     "return_2x_cost": st2["return_pct"], "pf_2x_cost": st2["profit_factor"],
                     "random": rb, "wf_median_score": wf["median_score"], "wf_folds_return": [f["return_pct"] for f in wf["folds"]],
                     "wf_worst_dd": wf["worst_dd"], "guardrails": why,
                     "long_pnl": round(sum(t.pnl for t in real.trades if t.side > 0), 2),
                     "short_pnl": round(sum(t.pnl for t in real.trades if t.side < 0), 2),
                     "by_family": {k: {"n": v["n"], "pnl": round(v["pnl"], 2), "win_rate": round(100 * v["wins"] / v["n"], 1)} for k, v in by.items()},
                     "robust": ok and rb["p_value"] <= 0.05 and st2["profit_factor"] > 1.1 and
                     sum(f["return_pct"] > 0 for f in wf["folds"]) >= 3})
        print(f"{label:34} ret {st['return_pct']:7.2f}  pf {st['profit_factor']:5.2f}  p {rb['p_value']:.3f}  "
              f"2x {st2['return_pct']:7.2f}  wf {wf['median_score']:7.3f}  {'ROBUST' if rows[-1]['robust'] else ''}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = ROOT / "reports"; out.mkdir(exist_ok=True)
    (out / f"strategies-{stamp}.json").write_text(json.dumps({"date": stamp, "bars": len(df), "rows": rows}, indent=1, default=str))
    L = [f"# Strategy families — {stamp}", "",
         f"GC=F 1h, {len(df)} bars up to the sealed holdout ({hold.date()}), $10k, real costs. "
         f"Random = same exits/sizing/costs with random entries ({N_RANDOM} runs); p = share of random runs ≥ real. "
         "WF = 4 walk-forward OOS folds. Robust = guardrails + p ≤ 0.05 + PF > 1.1 at 2× costs + ≥3/4 folds positive.", "",
         "| Config | Return % | Max DD % | Trades | PF | Win % | Random median % | p | Return 2× cost % | PF 2× | WF score | WF fold returns % | Longs $ | Shorts $ | Robust |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['config']} | {r['return_pct']} | {r['max_dd_pct']} | {r['trades']} | {r['pf']} | {r['win_rate']} | "
                 f"{r['random']['median']} | {r['random']['p_value']} | {r['return_2x_cost']} | {r['pf_2x_cost']} | {r['wf_median_score']} | "
                 f"{r['wf_folds_return']} | {r['long_pnl']} | {r['short_pnl']} | {'✅' if r['robust'] else '—'} |")
    L += ["", "## Per-family attribution inside ensembles", ""]
    for r in rows:
        if len(r["strategies"]) > 1:
            L.append(f"- **{r['config']}**: " + ", ".join(f"{k}: {v['n']} trades, ${v['pnl']}, win {v['win_rate']}%" for k, v in r["by_family"].items()))
    (out / f"strategies-{stamp}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
