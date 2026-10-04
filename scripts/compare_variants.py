"""Compare research-backed strategy variants on real gold data (walk-forward OOS).

Each variant is evaluated against the current params under 1x and 2x costs.
A variant is marked ROBUST only if it beats the baseline OOS in both cost
scenarios and passes guardrails. Output: reports/variants-YYYY-MM-DD.{md,json}

Run by .github/workflows/research.yml (data download needs internet).
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldbot import data  # noqa: E402
from goldbot.config import ROOT, load_params, load_settings  # noqa: E402
from goldbot.optimize import evaluate, passes_guardrails  # noqa: E402

# name -> (param changes, evidence note)
VARIANTS = {
    "A1 daily trend 60d": ({"daily_trend_days": 60}, "Bartsch et al.; AQR century of trend"),
    "A2 daily trend 120d": ({"daily_trend_days": 120}, "Bartsch et al.; AQR century of trend"),
    "A3 daily trend 20d": ({"daily_trend_days": 20}, "shorter variant, robustness check"),
    "B1 session 07-17 UTC": ({"session_start_utc": 7, "session_end_utc": 17}, "Batten et al. 2017 liquidity"),
    "B2 session 06-20 UTC": ({"session_start_utc": 6, "session_end_utc": 20}, "wider window"),
    "E1 time stop 12 bars": ({"max_hold_bars": 12}, "practitioner, weak"),
    "E2 time stop 24 bars": ({"max_hold_bars": 24}, "practitioner, weak"),
    "A1+B1": ({"daily_trend_days": 60, "session_start_utc": 7, "session_end_utc": 17}, "top-2 combined"),
    "A2+B2": ({"daily_trend_days": 120, "session_start_utc": 6, "session_end_utc": 20}, "combined, wider"),
}


def _cost(settings, mult):
    s = replace(settings)
    s.spread = settings.spread * mult
    s.commission_per_lot = settings.commission_per_lot * mult
    return s


def main() -> int:
    settings, base = load_settings(), load_params()
    settings.starting_equity = 10_000
    try:
        df = data.load_yfinance("GC=F", period="730d", interval=base.timeframe)
    except Exception as exc:
        print(f"data download failed: {exc}")
        return 1

    rows = []
    baseline = {m: evaluate(df, _cost(settings, m), base) for m in (1, 2)}
    for name, (chg, note) in [("baseline (current params)", ({}, "params.yaml"))] + list(VARIANTS.items()):
        p = replace(base, **chg)
        evs = {m: (baseline[m] if not chg else evaluate(df, _cost(settings, m), p)) for m in (1, 2)}
        ok, why = passes_guardrails(evs[1])
        beats = all(evs[m]["median_score"] > baseline[m]["median_score"] for m in (1, 2))
        rows.append({
            "variant": name, "changes": chg, "evidence": note,
            "score_1x": evs[1]["median_score"], "score_2x": evs[2]["median_score"],
            "pf_1x": evs[1]["median_pf"], "pf_2x": evs[2]["median_pf"],
            "worst_dd_1x": evs[1]["worst_dd"], "trades_1x": evs[1]["total_trades"],
            "fold_returns_1x": [f["return_pct"] for f in evs[1]["folds"]],
            "fold_returns_2x": [f["return_pct"] for f in evs[2]["folds"]],
            "guardrails": why, "robust": bool(chg) and ok and beats,
        })

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"variants-{stamp}.json").write_text(json.dumps(
        {"date": stamp, "bars": len(df), "start": str(df.index[0]), "end": str(df.index[-1]), "rows": rows},
        indent=2, default=str))

    lines = [f"# Strategy variants — {stamp}", "",
             f"Data: GC=F hourly, {len(df)} bars, {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}. "
             "Walk-forward, 4 out-of-sample folds, $10k equity. 2x = doubled spread and commission.", "",
             "| Variant | Score 1x | Score 2x | PF 1x | PF 2x | Worst DD % | OOS trades | Fold returns % (1x) | Robust |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['variant']} | {r['score_1x']} | {r['score_2x']} | {r['pf_1x']} | {r['pf_2x']} | "
                     f"{r['worst_dd_1x']} | {r['trades_1x']} | {r['fold_returns_1x']} | "
                     f"{'✅' if r['robust'] else '—'} |")
    lines += ["", "Robust = beats baseline OOS score under BOTH 1x and 2x costs and passes guardrails "
              "(DD ≤ 25%, ≥ 8 trades, PF ≥ 1.1)."]
    (out / f"variants-{stamp}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
