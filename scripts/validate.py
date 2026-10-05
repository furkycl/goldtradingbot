"""Strategy validation on real data — answers three questions honestly:

1. Does the hourly breakout strategy have an edge beyond chance?
   (random-entry benchmark with identical exits/sizing/costs, cost stress,
   parameter neighbourhood, second instrument without futures roll gaps)
2. Which profit method is most sensible for gold?
   (hourly breakout vs buy & hold vs daily trend following, 2000-2026 incl.
   the 2011-2015 bear market, plus random-timing benchmark)
3. What does "$100 -> $1,000,000" require?
   (block-bootstrap Monte Carlo at several leverage levels)

Writes reports/validation-YYYY-MM-DD.{md,json}. Needs internet (GitHub Actions).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldbot import daily as D  # noqa: E402
from goldbot import data  # noqa: E402
from goldbot.backtest import run_backtest  # noqa: E402
from goldbot.config import ROOT, StrategyParams, load_params, load_settings  # noqa: E402
from goldbot.optimize import SEARCH_SPACE  # noqa: E402
from goldbot.strategy import warmup_bars  # noqa: E402

N_RANDOM = 300
ORIGINAL_DEFAULTS = StrategyParams()   # hand-set before any data was seen
rng_master = np.random.default_rng(20261005)


# ---------------------------------------------------------------- helpers
def _cost(settings, mult):
    s = replace(settings)
    s.spread *= mult
    s.commission_per_lot *= mult
    s.financing_pct_per_year *= mult
    return s


def hourly_block(df: pd.DataFrame, settings, p: StrategyParams, label: str) -> dict:
    start = df.index[warmup_bars(p) + 50]
    real = run_backtest(df, settings, p, trade_from=start)
    st = real.stats
    trades = real.trades
    longs = [t.pnl for t in trades if t.side > 0]
    shorts = [t.pnl for t in trades if t.side < 0]
    n_bars = len(df) - df.index.searchsorted(start)
    held = sum(df.index.searchsorted(t.exit_time) - df.index.searchsorted(t.entry_time) + 1 for t in trades)
    q = len(trades) / max(1, n_bars - held)
    long_frac = len(longs) / max(1, len(trades))

    rand_ret, rand_pf = [], []
    for _ in range(N_RANDOM):
        rng = np.random.default_rng(rng_master.integers(1 << 31))

        def entry_fn(i, ts, rng=rng):
            if rng.random() < q:
                return 1 if rng.random() < long_frac else -1
            return 0
        rs = run_backtest(df, settings, p, trade_from=start, entry_fn=entry_fn).stats
        rand_ret.append(rs["return_pct"])
        rand_pf.append(min(rs["profit_factor"], 10))
    rand_ret = np.array(rand_ret)
    pct = float((rand_ret < st["return_pct"]).mean() * 100)

    costs = {f"{m}x": run_backtest(df, _cost(settings, m), p, trade_from=start).stats["return_pct"]
             for m in (0, 1, 2, 3)}

    neigh = []
    for k, vals in SEARCH_SPACE.items():
        for v in vals:
            if getattr(p, k) == v:
                continue
            q2 = replace(p, **{k: v})
            if q2.ema_fast >= q2.ema_slow:
                continue
            r2 = run_backtest(df, settings, q2, trade_from=df.index[warmup_bars(q2) + 50]).stats
            neigh.append({"param": k, "value": v, "return_pct": r2["return_pct"], "pf": r2["profit_factor"]})
    neigh_pos = sum(n["return_pct"] > 0 for n in neigh) / max(1, len(neigh))

    c = df["close"]
    bh = 100 * (c.iloc[-1] / c.loc[start:].iloc[0] - 1)
    return {
        "label": label, "params": p.to_dict(), "period": f"{start:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}",
        "stats": st, "long_pnl": round(sum(longs), 2), "short_pnl": round(sum(shorts), 2),
        "n_long": len(longs), "n_short": len(shorts),
        "random": {"median_return_pct": round(float(np.median(rand_ret)), 2),
                   "p95_return_pct": round(float(np.percentile(rand_ret, 95)), 2),
                   "median_pf": round(float(np.median(rand_pf)), 2),
                   "real_percentile": round(pct, 1), "p_value": round(1 - pct / 100, 3)},
        "cost_stress_return_pct": costs,
        "neighbourhood_positive_frac": round(neigh_pos, 2), "neighbourhood": neigh,
        "buy_hold_return_pct": round(float(bh), 2),
    }


VENUES = {
    # name: (spread $/oz, round-trip commission as % of notional, financing %/yr, long_only)
    "Global raw CFD (benchmark, not legal in TR)": (0.15, 0.0015, 5.0, False),
    "SPK-licensed TR CFD via MT5": (0.50, 0.0, 5.0, False),
    "VIOP F_XAUUSD (0.05%/side + fees)": (0.20, 0.12, 0.0, False),
    "Token spot, 0.10%/side (PAXG/XAUT)": (1.50, 0.20, 0.0, True),
    "Token spot, 0.20%/side": (2.00, 0.40, 0.0, True),
}


def venue_block(df: pd.DataFrame, settings, p: StrategyParams) -> list[dict]:
    start = df.index[warmup_bars(p) + 50]
    mid = float(df["close"].loc[start:].mean())
    rows = []
    for name, (spread, rt_pct, fin, long_only) in VENUES.items():
        s = replace(settings)
        s.spread, s.financing_pct_per_year, s.long_only = spread, fin, long_only
        s.commission_per_lot = rt_pct / 100 * mid * s.contract_size
        if long_only:   # spot token: no leverage
            s.risk = replace(s.risk, max_leverage=1.0)
        r = run_backtest(df, s, p, trade_from=start)
        st = r.stats
        risk = [t.initial_risk for t in r.trades]
        cost_oz = spread + rt_pct / 100 * mid
        rows.append({"venue": name, "return_pct": st["return_pct"], "max_dd_pct": st["max_drawdown_pct"],
                     "trades": st["trades"], "pf": st["profit_factor"],
                     "cost_per_trade_in_R": round(cost_oz / float(np.mean(risk)), 3) if risk else None})
    return rows


def daily_block(df: pd.DataFrame, name: str, cost_bps: float, fin: float) -> dict:
    c, h, lo = df["close"], df["high"], df["low"]
    strategies = {
        "Buy & hold": D.buy_hold(c),
        "TSMOM 12m long-only": D.tsmom(c, 252),
        "TSMOM 6m long-only": D.tsmom(c, 126),
        "TSMOM 3m long-only": D.tsmom(c, 63),
        "TSMOM 12m long/short": D.tsmom(c, 252, long_only=False),
        "SMA200 filter": D.sma_filter(c, 200),
        "Donchian 55/20 long-only": D.donchian_daily(c, h, lo, 55, 20),
        "Donchian 55/20 long/short": D.donchian_daily(c, h, lo, 55, 20, long_only=False),
    }
    strategies["TSMOM 12m + vol target 15%"] = D.vol_target(c, strategies["TSMOM 12m long-only"], 15, 2.0)
    strategies["Buy & hold + vol target 15%"] = D.vol_target(c, strategies["Buy & hold"], 15, 2.0)

    start = c.index[260]
    periods = {"full": (start, c.index[-1]),
               "2000-2011 bull": ("2000-01-01", "2011-08-31"),
               "2011-2015 bear": ("2011-09-01", "2015-12-31"),
               "2016-2026 bull": ("2016-01-01", c.index[-1])}
    rows = []
    for nm, pos in strategies.items():
        r = D.returns_from_positions(c, pos, cost_bps, fin).loc[start:]
        row = {"strategy": nm, "time_in_market_pct": round(100 * float((pos.loc[start:] != 0).mean()), 1)}
        for pn, (a, b) in periods.items():
            seg = r.loc[pd.Timestamp(a, tz="UTC") if isinstance(a, str) else a:
                        pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1) if isinstance(b, str) else b]
            if len(seg) > 200:
                row[pn] = D.stats(seg)
        rows.append(row)

    # random-timing benchmark for TSMOM 12m long-only
    pos = strategies["TSMOM 12m long-only"].loc[start:]
    frac = float((pos > 0).mean())
    switches = max(1, int((pos.diff().abs() > 0).sum()))
    mean_hold = max(1, int(frac * len(pos) / (switches / 2 + 1)))
    real_sharpe = D.stats(D.returns_from_positions(c, strategies["TSMOM 12m long-only"], cost_bps, fin).loc[start:])["sharpe"]
    rs = []
    for _ in range(N_RANDOM):
        rp = pd.Series(D.random_exposure(len(pos), frac, mean_hold, rng_master), index=pos.index)
        rs.append(D.stats(D.returns_from_positions(c.loc[start:], rp, cost_bps, fin))["sharpe"])
    pct = float((np.array(rs) < real_sharpe).mean() * 100)
    return {"instrument": name, "cost_bps": cost_bps, "financing_pct": fin,
            "start": str(start.date()), "end": str(c.index[-1].date()), "rows": rows,
            "tsmom_random_timing": {"real_sharpe": real_sharpe, "random_median_sharpe": round(float(np.median(rs)), 2),
                                    "real_percentile": round(pct, 1), "time_in_market": round(frac, 2)}}


def monte_carlo(daily_rets: pd.Series, label: str, years: int = 10, paths: int = 4000,
                block: int = 20, leverages=(1, 2, 3, 5, 10)) -> dict:
    r = daily_rets.dropna().to_numpy()
    n = years * D.TRADING_DAYS
    rng = np.random.default_rng(7)
    out = []
    for L in leverages:
        finals, dds, ruined = [], [], 0
        for _ in range(paths):
            starts = rng.integers(0, len(r) - block, n // block + 1)
            path = np.concatenate([r[s:s + block] for s in starts])[:n] * L
            if (path <= -1).any():
                ruined += 1; finals.append(0.0); dds.append(1.0); continue
            eq = np.cumprod(1 + path)
            dd = float((1 - eq / np.maximum.accumulate(eq)).max())
            if eq.min() < 0.1:
                ruined += 1
            finals.append(float(eq[-1])); dds.append(dd)
        finals = np.array(finals); dds = np.array(dds)
        med = float(np.median(finals))
        cagr = med ** (1 / years) - 1 if med > 0 else -1
        yrs_10k = math.log(10_000) / math.log(1 + cagr) if cagr > 0 else None
        out.append({"leverage": L, "median_multiple_10y": round(med, 2),
                    "p_10000x_in_10y_pct": round(100 * float((finals >= 10_000).mean()), 2),
                    "p_lose_half_pct": round(100 * float((dds >= 0.5).mean()), 1),
                    "p_ruin_pct": round(100 * ruined / paths, 1),
                    "median_cagr_pct": round(100 * cagr, 1),
                    "years_to_10000x_at_median": round(yrs_10k, 0) if yrs_10k else None})
    return {"label": label, "rows": out}


# ------------------------------------------------------------------- main
def md_report(res: dict) -> str:
    L = [f"# Strategy validation — {res['date']}", "",
         "Automatically generated by `scripts/validate.py`. All figures are backtests on public data; "
         "past performance does not guarantee future results.", ""]
    L += ["## 1. Hourly breakout strategy: is there an edge?", "",
          "Random benchmark = same exits, sizing and costs, but random entry times/sides "
          f"({N_RANDOM} simulations). p-value = share of random runs that did at least as well.", "",
          "| Instrument / params | Period | Return % | Max DD % | Trades | PF | Random median % | Random 95th % | p-value | Cost 0x/1x/2x/3x % | Neighbours profitable | Buy & hold % |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in res["hourly"]:
        st, rd, cs = h["stats"], h["random"], h["cost_stress_return_pct"]
        L.append(f"| {h['label']} | {h['period']} | {st['return_pct']} | {st['max_drawdown_pct']} | {st['trades']} | "
                 f"{st['profit_factor']} | {rd['median_return_pct']} | {rd['p95_return_pct']} | {rd['p_value']} | "
                 f"{cs['0x']}/{cs['1x']}/{cs['2x']}/{cs['3x']} | {int(100*h['neighbourhood_positive_frac'])}% | {h['buy_hold_return_pct']} |")
    L += ["", "Long vs short P&L ($10k account):", ""]
    for h in res["hourly"]:
        L.append(f"- {h['label']}: longs {h['n_long']} trades ${h['long_pnl']}, shorts {h['n_short']} trades ${h['short_pnl']}")
    if res.get("venues"):
        L += ["", "### Same strategy with the costs of venues reachable from Turkey (GC=F 1h, current params)", "",
              "| Venue | Return % | Max DD % | Trades | PF | Cost per trade (in R) |", "|---|---|---|---|---|---|"]
        for v in res["venues"]:
            L.append(f"| {v['venue']} | {v['return_pct']} | {v['max_dd_pct']} | {v['trades']} | {v['pf']} | {v['cost_per_trade_in_R']} |")
    for d in res["daily"]:
        L += ["", f"## 2. Daily strategies — {d['instrument']} ({d['start']} → {d['end']}, cost {d['cost_bps']} bps/switch, financing {d['financing_pct']}%/yr)", "",
              "| Strategy | In market % | CAGR % | Max DD % | Sharpe | Calmar | 2000-11 CAGR | 2011-15 bear CAGR / DD | 2016-26 CAGR |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in d["rows"]:
            f = r.get("full", {}); a = r.get("2000-2011 bull", {}); b = r.get("2011-2015 bear", {}); c = r.get("2016-2026 bull", {})
            L.append(f"| {r['strategy']} | {r['time_in_market_pct']} | {f.get('cagr_pct')} | {f.get('max_dd_pct')} | {f.get('sharpe')} | "
                     f"{f.get('calmar')} | {a.get('cagr_pct', '–')} | {b.get('cagr_pct', '–')} / {b.get('max_dd_pct', '–')} | {c.get('cagr_pct', '–')} |")
        t = d["tsmom_random_timing"]
        L += ["", f"TSMOM 12m vs random timing with the same time in market ({t['time_in_market']}): "
              f"Sharpe {t['real_sharpe']} vs random median {t['random_median_sharpe']} → better than {t['real_percentile']}% of random runs."]
    L += ["", "## 3. What would $100 → $1,000,000 (10,000×) take?", "",
          "Block-bootstrap Monte Carlo (20-day blocks, 4,000 paths, 10 years) of daily strategy returns, scaled by leverage. "
          "Ruin = equity falls below 10% of start or a single day wipes the account.", ""]
    for m in res["monte_carlo"]:
        L += [f"**{m['label']}**", "", "| Leverage | Median 10y multiple | Median CAGR % | P(10,000× in 10y) % | P(≥50% drawdown) % | P(ruin) % | Years to 10,000× at median |",
              "|---|---|---|---|---|---|---|"]
        for r in m["rows"]:
            L.append(f"| {r['leverage']}× | {r['median_multiple_10y']} | {r['median_cagr_pct']} | {r['p_10000x_in_10y_pct']} | "
                     f"{r['p_lose_half_pct']} | {r['p_ruin_pct']} | {r['years_to_10000x_at_median'] or '∞'} |")
        L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    settings = load_settings()
    settings.starting_equity = 10_000
    current = load_params()
    res = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "hourly": [], "daily": [], "monte_carlo": []}

    import yaml
    hold = pd.Timestamp(yaml.safe_load((ROOT / "config" / "validation.yaml").read_text())["holdout_start"], tz="UTC")
    # hourly strategy research never looks at the sealed holdout (see self_improve.py)
    gc_h = data.load_yfinance("GC=F", "730d", "1h").loc[: hold - pd.Timedelta(seconds=1)]
    res["hourly"].append(hourly_block(gc_h, settings, current, "GC=F 1h, current params"))
    res["hourly"].append(hourly_block(gc_h, settings, ORIGINAL_DEFAULTS, "GC=F 1h, original defaults"))
    res["venues"] = venue_block(gc_h, settings, current)
    try:
        px_h = data.load_yfinance("PAXG-USD", "730d", "1h").loc[: hold - pd.Timedelta(seconds=1)]
        px_set = replace(settings); px_set.financing_pct_per_year = 0.0
        res["hourly"].append(hourly_block(px_h, px_set, current, "PAXG-USD 1h (no roll gaps), current params"))
    except Exception as exc:
        print("PAXG-USD hourly unavailable:", exc)

    gc_d = data.load_yfinance("GC=F", "max", "1d")
    res["daily"].append(daily_block(gc_d, "GC=F daily as CFD (5%/yr financing)", cost_bps=3.0, fin=5.0))
    res["daily"].append(daily_block(gc_d, "GC=F daily unlevered (ETF/token/physical, 0.4%/yr fee)", cost_bps=10.0, fin=0.4))

    c = gc_d["close"]
    start = c.index[260]
    res["monte_carlo"].append(monte_carlo(D.returns_from_positions(c, D.buy_hold(c), 3.0, 5.0).loc[start:],
                                          "Buy & hold gold via CFD (2000-2026 returns)"))
    res["monte_carlo"].append(monte_carlo(D.returns_from_positions(c, D.tsmom(c, 252), 3.0, 5.0).loc[start:],
                                          "TSMOM 12m long-only via CFD (2000-2026 returns)"))
    eq = run_backtest(gc_h, settings, current, trade_from=gc_h.index[warmup_bars(current) + 50]).equity
    hr = eq.resample("1D").last().dropna().pct_change().dropna()
    res["monte_carlo"].append(monte_carlo(hr, "Hourly breakout (2024-2026 returns). Leverage column = risk per "
                                          "trade as a multiple of 1%. ONLY ~2 YEARS OF DATA: treat as optimistic",
                                          leverages=(1, 2, 3, 5)))

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"validation-{res['date']}.json").write_text(json.dumps(res, indent=1, default=str))
    md = md_report(res)
    (out / f"validation-{res['date']}.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
