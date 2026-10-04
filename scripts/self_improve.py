"""One iteration of the self-improvement loop (run by .github/workflows/self-improve.yml).

1. Download fresh gold data (falls back to synthetic if offline).
2. Walk-forward search around current params (config/params.yaml).
3. If a candidate beats the baseline out-of-sample AND passes guardrails,
   write it to config/params.yaml and a report to reports/; the workflow then
   opens a PR on a new branch, and auto-merges it only after CI passes.

It never touches config/settings.yaml (broker, live mode, risk limits).
Exit code: 0 = improvement written, 78 = nothing to change.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldbot import data  # noqa: E402
from goldbot.config import ROOT, load_params, load_settings, save_params  # noqa: E402
from goldbot.optimize import search  # noqa: E402


def _summary(ev: dict) -> dict:
    out = {k: v for k, v in ev.items() if k != "folds"}
    out["fold_return_pct"] = [f["return_pct"] for f in ev["folds"]]
    out["fold_max_dd_pct"] = [f["max_drawdown_pct"] for f in ev["folds"]]
    out["fold_win_rate_pct"] = [f["win_rate_pct"] for f in ev["folds"]]
    return out


def main() -> int:
    settings, params = load_settings(), load_params()
    settings.starting_equity = 10_000  # optimise on a size where min-lot rounding doesn't dominate
    try:
        df = data.load_yfinance("GC=F", period="730d", interval=params.timeframe)
        source = "yfinance GC=F"
    except Exception as exc:
        print(f"data download failed ({exc}); using synthetic data — no params will be changed")
        return 78
    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
    result = search(df, settings, params, trials=60, seed=seed)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    report = {
        "date": stamp, "data": source, "bars": len(df), "accepted": result["accepted"],
        "reason": result["reason"],
        "baseline_oos": _summary(result["baseline"]),
    }
    if result["accepted"]:
        report["candidate_oos"] = _summary(result["candidate"])
        report["old_params"] = params.to_dict()
        report["new_params"] = result["params"].to_dict()
        save_params(result["params"], header=f"auto-tuned {stamp}: {result['reason']}")
    (reports / f"self-improve-{stamp}.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    return 0 if result["accepted"] else 78


if __name__ == "__main__":
    sys.exit(main())
