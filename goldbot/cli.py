"""Command line: python -m goldbot <command>

  backtest   [--csv FILE | --yf] [--equity N]   run a backtest
  optimize   [--csv FILE | --yf] [--trials N]   walk-forward search (prints result)
  news                                          print current headlines + sentiment
  probe-feeds                                   check RSS feeds are alive and fresh
  run                                           start paper / demo / live trading
  status [--mode M]                             forward-test results vs go-live checklist
  report [--mode M]                             HTML report (equity curve, trades)
  core                                          unlevered core-holding signal (daily trend)
  reset-halt                                    clear the kill switch after a human review
"""
from __future__ import annotations

import argparse
import json
import logging

from .config import load_dotenv, load_params, load_settings


def _data(args):
    from . import data
    if args.csv:
        return data.load_csv(args.csv)
    if args.yf:
        return data.load_yfinance("GC=F", period="730d", interval="1h")
    return data.synthetic_ohlc()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="goldbot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("backtest", "optimize"):
        sp = sub.add_parser(name)
        sp.add_argument("--csv")
        sp.add_argument("--yf", action="store_true", help="download GC=F hourly from Yahoo")
        sp.add_argument("--equity", type=float)
        sp.add_argument("--trials", type=int, default=40)
    sub.add_parser("news")
    sub.add_parser("probe-feeds", help="check every RSS feed is reachable and fresh")
    sub.add_parser("run")
    sp = sub.add_parser("status", help="forward-test results vs go-live criteria")
    sp.add_argument("--mode", choices=["paper", "demo", "live"], help="default: all present")
    sp = sub.add_parser("report", help="write state/<mode>/report.html")
    sp.add_argument("--mode", choices=["paper", "demo", "live"], default="paper")
    sub.add_parser("core", help="unlevered core-holding signal (daily gold trend)")
    sub.add_parser("reset-halt", help="clear a drawdown/daily halt after reviewing what happened")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    settings, params = load_settings(), load_params()

    if args.cmd == "backtest":
        from .backtest import run_backtest
        if args.equity:
            settings.starting_equity = args.equity
        print(json.dumps(run_backtest(_data(args), settings, params).stats, indent=2))
    elif args.cmd == "optimize":
        from .optimize import search
        if args.equity:
            settings.starting_equity = args.equity
        r = search(_data(args), settings, params, trials=args.trials)
        r.pop("baseline", None); r.pop("candidate", None)
        if "params" in r:
            r["params"] = r["params"].to_dict()
        print(json.dumps(r, indent=2, default=str))
    elif args.cmd == "news":
        from .news import NewsAggregator
        agg = NewsAggregator(rss=settings.news.get("rss"))
        agg.poll_rss(); agg.poll_calendar()
        for it in sorted(agg.items.values(), key=lambda i: i.ts)[-25:]:
            print(f"{it.ts:%m-%d %H:%M} {it.score:+.2f} {it.text[:110]}")
        print(f"\naggregate sentiment: {agg.sentiment():+.2f} | blackout now: {agg.in_blackout()}")
    elif args.cmd == "probe-feeds":
        from .news import NewsAggregator
        for url, status, age in NewsAggregator(rss=settings.news.get("rss")).probe():
            print(f"{status:<22} newest {age:>8}  {url}")
    elif args.cmd == "run":
        from logging.handlers import RotatingFileHandler

        from .config import ROOT
        from .engine import Engine, mode_name
        logdir = ROOT / "state" / mode_name(settings)
        logdir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(logdir / "goldbot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(fh)
        Engine(settings, params).run()
    elif args.cmd == "status":
        from .config import ROOT
        from .forward import checklist, evaluate_journal, render_status
        modes = [args.mode] if args.mode else ["paper", "demo", "live"]
        found = False
        for m in modes:
            folder = ROOT / "state" / m
            if (folder / "journal.csv").exists() or (folder / "equity.csv").exists():
                found = True
                met = evaluate_journal(folder)
                print(render_status(met, checklist(met)))
                risk = folder / "risk.json"
                if risk.exists():
                    print("  risk state:", json.loads(risk.read_text()).get("halted_reason") or "no halt")
        if not found:
            print("no forward-test data yet — start with: python -m goldbot run")
    elif args.cmd == "report":
        from .config import ROOT
        from .forward import html_report
        print("written:", html_report(ROOT / "state" / args.mode))
    elif args.cmd == "core":
        from . import data as data_mod
        from .core import core_signal
        print(json.dumps(core_signal(data_mod.load_yfinance("GC=F", "5y", "1d")["close"]), indent=2))
    elif args.cmd == "reset-halt":
        from .brokers import make_broker
        from .config import ROOT
        from .engine import mode_name
        from .risk import RiskManager
        broker = make_broker(settings)
        rm = RiskManager(settings.risk, settings.contract_size, settings.min_lot, settings.lot_step, broker.equity())
        rm.attach(ROOT / "state" / mode_name(settings) / "risk.json")
        old = rm.reset_halt(broker.equity())
        print(f"halt cleared (was: {old or 'none'}); drawdown now measured from {broker.equity():.2f}")


if __name__ == "__main__":
    main()
