"""Forward-test evaluation from the journal + go-live checklist."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .config import ROOT
from .journal import Journal


def go_live_criteria() -> dict:
    return yaml.safe_load((ROOT / "config" / "validation.yaml").read_text()).get("go_live", {})


def evaluate_journal(folder: Path) -> dict:
    j = Journal(folder)
    t = j.load_trades()
    closes = t[t["event"] == "close"] if len(t) else t
    pnl = pd.to_numeric(closes.get("pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    eq = j.load_equity()
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    pf = float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else (float("inf") if len(wins) else 0.0)
    dd = float(((eq.cummax() - eq) / eq.cummax()).max() * 100) if len(eq) else 0.0
    days = (eq.index[-1] - eq.index[0]).days if len(eq) > 1 else 0
    ret = float((eq.iloc[-1] / eq.iloc[0] - 1) * 100) if len(eq) > 1 else 0.0
    return {"folder": str(folder), "trades": int(len(pnl)), "win_rate_pct": round(100 * len(wins) / len(pnl), 1) if len(pnl) else 0.0,
            "profit_factor": round(pf, 2) if np.isfinite(pf) else 999.0, "net_pnl": round(float(pnl.sum()), 2),
            "return_pct": round(ret, 2), "max_drawdown_pct": round(dd, 2), "days": int(days),
            "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
            "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0}


def checklist(m: dict, c: dict | None = None) -> list[tuple[str, bool, str]]:
    c = c or go_live_criteria()
    return [
        ("trades", m["trades"] >= c.get("min_trades", 100), f"{m['trades']} / {c.get('min_trades', 100)}"),
        ("profit factor", m["profit_factor"] >= c.get("min_profit_factor", 1.2),
         f"{m['profit_factor']} (need ≥ {c.get('min_profit_factor', 1.2)})"),
        ("max drawdown", m["max_drawdown_pct"] <= c.get("max_drawdown_pct", 15.0),
         f"{m['max_drawdown_pct']}% (need ≤ {c.get('max_drawdown_pct', 15.0)}%)"),
        ("days tested", m["days"] >= c.get("min_days", 60), f"{m['days']} / {c.get('min_days', 60)}"),
    ]


def render_status(m: dict, checks: list) -> str:
    lines = [f"Forward test [{Path(m['folder']).name}]: {m['trades']} closed trades over {m['days']} days",
             f"  net P&L {m['net_pnl']} | return {m['return_pct']}% | PF {m['profit_factor']} | "
             f"win rate {m['win_rate_pct']}% | max DD {m['max_drawdown_pct']}%",
             f"  avg win {m['avg_win']} | avg loss {m['avg_loss']}", "  Go-live checklist:"]
    for name, ok, detail in checks:
        lines.append(f"    [{'x' if ok else ' '}] {name}: {detail}")
    verdict = all(ok for _, ok, _ in checks)
    lines.append("  VERDICT: " + ("criteria met — review docs/STRATEGY.md stage 2 before going live"
                                   if verdict else "keep testing — do NOT go live yet"))
    return "\n".join(lines)


def html_report(folder: Path) -> Path:
    """Self-contained HTML (inline SVG, no external assets) with equity curve + trades."""
    j = Journal(folder)
    m = evaluate_journal(folder)
    eq = j.load_equity()
    t = j.load_trades()
    w, h, pad = 900, 260, 36
    path = ""
    if len(eq) > 1:
        x = np.linspace(pad, w - pad, len(eq))
        lo, hi = float(eq.min()), float(eq.max())
        y = h - pad - (eq.to_numpy() - lo) / ((hi - lo) or 1) * (h - 2 * pad)
        path = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in zip(x, y))
        axis = (f'<text x="{pad}" y="{pad - 10}" class="ax">{hi:,.2f}</text>'
                f'<text x="{pad}" y="{h - 8}" class="ax">{lo:,.2f}</text>'
                f'<text x="{w - pad}" y="{h - 8}" class="ax" text-anchor="end">{eq.index[-1]:%Y-%m-%d}</text>'
                f'<text x="{pad + 90}" y="{h - 8}" class="ax">{eq.index[0]:%Y-%m-%d}</text>')
    else:
        axis = f'<text x="{w / 2}" y="{h / 2}" class="ax" text-anchor="middle">no equity data yet</text>'
    rows = "".join(
        f"<tr><td>{r.time[:16].replace('T', ' ')}</td><td>{r.event}</td><td>{'BUY' if str(r.side) in ('1', '1.0') else 'SELL' if str(r.side) in ('-1', '-1.0') else ''}</td>"
        f"<td>{r.lots}</td><td>{r.price}</td><td>{'' if pd.isna(r.pnl) else r.pnl}</td><td>{'' if pd.isna(r.reason) else r.reason}</td></tr>"
        for r in t.tail(200).iloc[::-1].itertuples()) if len(t) else ""
    checks = "".join(f"<li class='{'ok' if ok else 'no'}'>{name}: {d}</li>" for name, ok, d in checklist(m))
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>goldbot report</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1b16;--muted:#6b665a;--line:#b8860b;--ok:#2e7d32;--no:#b3261e;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141310;--fg:#ece8df;--muted:#9c968a;--line:#e0b84f;--ok:#7cc47f;--no:#f08a80;--card:#1d1b17}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:960px;margin:auto;padding:24px 16px}} h1{{font-size:22px;margin:0 0 4px}}
.k{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:16px 0}}
.k div{{background:var(--card);padding:12px;border-radius:8px}} .k b{{display:block;font-size:20px}}
.k span,.ax,small{{color:var(--muted);font-size:12px}} svg{{width:100%;height:auto;background:var(--card);border-radius:8px}}
.ax{{fill:var(--muted)}} li.ok{{color:var(--ok)}} li.no{{color:var(--no)}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td{{padding:4px 6px;border-bottom:1px solid #8883}}
.wrap{{overflow-x:auto}}
</style></head><body><main>
<h1>goldbot — {Path(folder).name}</h1><small>{m['days']} days · generated {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC</small>
<div class="k"><div><span>Return</span><b>{m['return_pct']}%</b></div><div><span>Max drawdown</span><b>{m['max_drawdown_pct']}%</b></div>
<div><span>Trades</span><b>{m['trades']}</b></div><div><span>Profit factor</span><b>{m['profit_factor']}</b></div>
<div><span>Win rate</span><b>{m['win_rate_pct']}%</b></div><div><span>Net P&amp;L</span><b>{m['net_pnl']}</b></div></div>
<svg viewBox="0 0 {w} {h}" role="img" aria-label="equity curve">{axis}<path d="{path}" fill="none" stroke="var(--line)" stroke-width="2"/></svg>
<h2>Go-live checklist</h2><ul>{checks}</ul>
<h2>Journal (latest 200)</h2><div class="wrap"><table><tr><th>time</th><th>event</th><th>side</th><th>lots</th><th>price</th><th>P&amp;L</th><th>reason</th></tr>{rows}</table></div>
</main></body></html>"""
    out = Path(folder) / "report.html"
    out.write_text(html, encoding="utf-8")
    return out
