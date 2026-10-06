"""`python -m goldbot doctor`: what is configured, what is missing, what to do.

Checks (no trading, no secrets printed): settings/params load, mode & broker
consistency, required env vars for the chosen broker, Telegram bot token
(getMe) and chat id, Telegram news session, news feeds reachable, broker
package importable, risk settings sane, state/lock, go-live preconditions.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .config import LIVE_CONFIRM_PHRASE, ROOT, load_dotenv, load_params, load_settings


def _ok(msg): return ("OK", msg)
def _warn(msg): return ("WARN", msg)
def _todo(msg): return ("TODO", msg)


def run() -> list[tuple[str, str]]:
    out = []
    load_dotenv()
    try:
        s, p = load_settings(), load_params()
        out.append(_ok(f"config loaded: mode={s.mode} broker={s.broker} symbol={s.broker_options.get('symbol', s.symbol)} "
                       f"strategies={p.strategies}"))
    except Exception as exc:
        return [("FAIL", f"config does not load: {exc}")]

    # --- mode / broker consistency
    if s.mode == "paper" and s.broker != "paper":
        out.append(_warn(f"mode=paper but broker={s.broker}: paper mode always uses the simulated broker (fine for testing)"))
    if s.mode in ("demo", "live") and s.broker == "paper":
        out.append(_todo(f"mode={s.mode} needs broker: mt5 (or ccxt) in config/settings.yaml"))
    if s.mode == "live":
        if os.environ.get("GOLDBOT_LIVE_CONFIRM") == LIVE_CONFIRM_PHRASE:
            out.append(_warn("LIVE trading is ARMED (mode=live + GOLDBOT_LIVE_CONFIRM set)"))
        else:
            out.append(_todo('mode=live but GOLDBOT_LIVE_CONFIRM is not set -> bot will run in PAPER. '
                             'Set it in .env only after `goldbot status` says "criteria met"'))

    # --- broker requirements
    if s.broker == "mt5" and s.mode != "paper":
        for k in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
            out.append(_ok(f"{k} set") if os.environ.get(k) else _todo(f"{k} missing in .env (broker demo/live account)"))
        try:
            import MetaTrader5  # noqa: F401
            out.append(_ok("MetaTrader5 package installed"))
        except ImportError:
            out.append(_todo("pip install MetaTrader5 (Windows only; keep the MT5 terminal open and logged in)"))
    if s.broker == "ccxt" and s.mode != "paper":
        for k in ("CCXT_API_KEY", "CCXT_SECRET"):
            out.append(_ok(f"{k} set") if os.environ.get(k) else _todo(f"{k} missing in .env"))
        if not (os.environ.get("CCXT_EXCHANGE") or s.broker_options.get("exchange")):
            out.append(_todo("CCXT_EXCHANGE (or broker_options.exchange) missing: choose an SPK-permitted exchange"))
        try:
            import ccxt  # noqa: F401
            out.append(_ok("ccxt installed"))
        except ImportError:
            out.append(_todo("pip install ccxt"))

    # --- telegram notifications / control
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        out.append(_todo("Telegram notifications off: set TELEGRAM_BOT_TOKEN (@BotFather) and TELEGRAM_CHAT_ID in .env "
                         "(docs/DEPLOY.md). Without them you get no trade alerts and no /pause /closeall"))
    else:
        try:
            import requests
            r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=8).json()
            out.append(_ok(f"Telegram bot @{r['result']['username']} reachable") if r.get("ok")
                       else _todo("TELEGRAM_BOT_TOKEN rejected by Telegram: regenerate it in @BotFather"))
        except Exception as exc:
            out.append(_warn(f"Telegram not reachable from here ({type(exc).__name__}); will retry when the bot runs"))
        if not str(chat).lstrip("-").isdigit():
            out.append(_todo("TELEGRAM_CHAT_ID must be the numeric id from getUpdates, not a @username"))

    # --- telegram news channels
    ch = (s.news.get("telegram") or {}).get("channels") or []
    if ch:
        if os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"):
            sess = ROOT / "state" / "telegram"
            has = any(sess.glob("*.session")) if sess.exists() else False
            out.append(_ok(f"Telegram news: {len(ch)} channels, session present") if has
                       else _todo("Telegram news: run `python -m goldbot telegram-login` once (needs `pip install telethon`)"))
        else:
            out.append(_warn(f"Telegram news channels configured ({len(ch)}) but TELEGRAM_API_ID/HASH not set -> RSS only "
                             "(optional; get them at https://my.telegram.org)"))
    if os.environ.get("FINNHUB_KEY"):
        out.append(_ok("Finnhub key set"))
    else:
        out.append(_warn("FINNHUB_KEY not set (optional free headline API, https://finnhub.io)"))

    # --- news feeds
    try:
        from .news import NewsAggregator
        res = NewsAggregator(rss=s.news.get("rss")).probe()
        ok = sum(1 for _, st, _ in res if st == "ok")
        out.append((_ok if ok >= len(res) // 2 else _warn)(f"news feeds reachable: {ok}/{len(res)}"))
    except Exception as exc:
        out.append(_warn(f"feed probe failed: {type(exc).__name__}"))

    # --- risk sanity
    r = s.risk
    if r.risk_per_trade_pct > 2 or any(float(x[1]) > 2 for x in (r.risk_ladder or [])):
        out.append(_warn("risk per trade above 2%: Monte Carlo puts 5%+ in the ruin zone (docs/STRATEGY.md §4)"))
    if r.max_open_positions > 1 and r.max_total_risk_pct < r.risk_per_trade_pct * 1.5:
        out.append(_warn("max_total_risk_pct is low for multi-position: second position will often be blocked"))
    if s.min_lot >= 0.01 and s.starting_equity < 1000 and s.broker != "ccxt":
        out.append(_warn(f"equity {s.starting_equity:.0f} with min lot {s.min_lot}: most signals will be refused as too large "
                         "(docs/STRATEGY.md §7: micro/cent account or grow capital)"))
    if r.trading_cap:
        out.append(_ok(f"equity ladder: trading cap {r.trading_cap:.0f}, risk ladder {r.risk_ladder or 'flat'}"))

    # --- state / forward test
    st_dir = ROOT / "state" / s.mode
    lock = st_dir / "goldbot.lock"
    out.append(_warn("a bot may already be running in this mode (lock file present)") if lock.exists()
               else _ok("no running instance in this mode"))
    if (st_dir / "journal.csv").exists():
        from .forward import checklist, evaluate_journal
        m = evaluate_journal(st_dir)
        met = all(ok for _, ok, _ in checklist(m))
        out.append(_ok(f"forward test [{s.mode}]: {m['trades']} trades, PF {m['profit_factor']}, "
                       f"{'GO-LIVE CRITERIA MET' if met else 'criteria NOT met yet'}"))
    else:
        out.append(_todo(f"no forward-test data for mode={s.mode} yet: run `python -m goldbot run`"))
    out.append(_ok(f"checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"))
    return out


def render(rows) -> str:
    icon = {"OK": "✅", "WARN": "⚠️ ", "TODO": "⬜", "FAIL": "❌"}
    lines = [f"{icon[k]} {k:<4} {m}" for k, m in rows]
    todo = [m for k, m in rows if k == "TODO"]
    lines.append("")
    lines.append(f"{len(todo)} item(s) need YOUR input" if todo else "nothing missing for the current mode")
    return "\n".join(lines)
