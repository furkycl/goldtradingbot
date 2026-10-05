"""Live / paper / demo trading loop.

Each poll:
  1. refresh candles; act only when a NEW bar has started (previous one closed)
  2. record closed trades + equity, manage open positions (time stop, trailing)
  3. risk gates: halt state, daily loss, drawdown kill switch, max trades,
     pause flag, news blackout, venue cost guard
  4. strategy signal (+ news sentiment) -> sized order with broker-side SL/TP

Risk state and the journal live in state/<mode>/ so a restart can never reset
the daily loss limit or the drawdown kill switch, and paper results never mix
with live ones.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .brokers import make_broker
from .brokers.paper import PaperBroker
from .config import ROOT, Settings, StrategyParams
from .journal import Journal
from .news import NewsAggregator
from .risk import RiskManager
from .strategy import prepare, signal_at, warmup_bars

log = logging.getLogger("goldbot.engine")

TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}


def notify(text: str) -> None:
    """Optional Telegram notifications to YOUR phone (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    log.info(text)
    if token and chat:
        try:
            import requests
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=5)
        except Exception as exc:
            log.warning("notify failed: %s", exc)


def market_open(now: datetime) -> bool:
    """Spot gold / CFD hours (approx., UTC): closed Fri 21:00 -> Sun 22:00 and daily 21:00-22:00."""
    wd, h = now.weekday(), now.hour
    if wd == 5 or (wd == 4 and h >= 21) or (wd == 6 and h < 22):
        return False
    return h != 21


def mode_name(s: Settings) -> str:
    return "live" if s.live_enabled else ("demo" if s.demo_enabled else "paper")


class Engine:
    def __init__(self, settings: Settings, params: StrategyParams, broker=None, news=None,
                 state_dir: Path | None = None):
        self.s, self.p = settings, params
        self.mode = mode_name(settings)
        self.state_dir = Path(state_dir) if state_dir else ROOT / "state" / self.mode
        self.broker = broker or make_broker(settings)
        self.news = news if news is not None else NewsAggregator(
            rss=settings.news.get("rss"), telegram=settings.news.get("telegram"),
            blackout_minutes=settings.news_blackout_minutes)
        self.rm = RiskManager(settings.risk, settings.contract_size, settings.min_lot,
                              settings.lot_step, self.broker.equity())
        self.rm.attach(self.state_dir / "risk.json")
        self.journal = Journal(self.state_dir, self.mode)
        self.last_bar = None
        self.paused = False
        self.stop_evt = threading.Event()
        self.lock = threading.RLock()          # step() vs remote commands
        self._open: dict[str, dict] = {p.id: vars(p).copy() for p in self.broker.positions()}
        self._close_reason: dict[str, str] = {}
        self._stale_notified = False
        self._last_err = 0.0
        notify(f"goldbot started in {self.mode.upper()} mode, broker={type(self.broker).__name__}, "
               f"equity={self.broker.equity():.2f}"
               + (f" — HALTED: {self.rm.state.halted_reason}" if self.rm.state.halted_reason else ""))

    # ------------------------------------------------------------ bookkeeping
    def _sync_positions(self) -> None:
        """Journal positions that disappeared (broker SL/TP, our own closes)."""
        now_ids = {p.id for p in self.broker.positions()}
        for pid in list(self._open):
            if pid not in now_ids:
                info = self._open.pop(pid)
                ct = self.broker.closed_trade(pid) or {}
                pnl, exit_px = ct.get("pnl"), ct.get("exit")
                reason = self._close_reason.pop(pid, "broker SL/TP")
                self.journal.event("close", time=self._now_iso(), id=pid, side=info.get("side"),
                                   lots=info.get("lots"), price=None if exit_px is None else round(exit_px, 2),
                                   pnl=None if pnl is None else round(pnl, 2),
                                   reason=reason, equity=round(self.broker.equity(), 2))
                notify(f"CLOSED {pid} ({reason}) pnl {pnl if pnl is not None else '?'}")

    def _now_iso(self) -> str:
        """Bar time in replays/backtests, wall-clock time live."""
        if isinstance(self.broker, PaperBroker) and self.broker.feed is not None and self.last_bar is not None:
            return pd.Timestamp(self.last_bar).isoformat()
        return datetime.now(timezone.utc).isoformat()

    def _close(self, pos, reason: str) -> None:
        self._close_reason[pos.id] = reason
        self.broker.close(pos.id)

    # ------------------------------------------------------------------ step
    def step(self) -> str:
        df = self.broker.candles(self.p.timeframe, warmup_bars(self.p) + 200)
        if len(df) < warmup_bars(self.p):
            return "not enough data"
        if isinstance(self.broker, PaperBroker):
            self.broker.set_last(float(df["close"].iloc[-1]))

        bar_time = df.index[-1]
        self._watchdog(bar_time)
        if bar_time == self.last_bar:
            return "no new bar"
        self.last_bar = bar_time
        if isinstance(self.broker, PaperBroker):
            # simulate broker-side SL/TP over the bar that just CLOSED (same as backtest)
            done = df.iloc[-2]
            self.broker.check_stops(float(done["high"]), float(done["low"]), float(done["open"]))
        self._sync_positions()

        data = prepare(df, self.p)
        row = data.iloc[-2]  # last CLOSED bar
        now = datetime.now(timezone.utc)
        eq = self.broker.equity()
        bt = pd.Timestamp(bar_time)
        self.rm.on_new_bar((bt.tz_convert("UTC") if bt.tzinfo else bt).date(), eq)
        self.journal.equity(df.index[-2], eq)

        for pos in self.broker.positions():
            self._manage(pos, row, df)
        self._sync_positions()
        positions = self.broker.positions()

        ok, why = self.rm.can_trade(len(positions))
        if not ok:
            return f"no entry: {why}"
        if self.paused:
            return "no entry: paused by operator"
        if self.news.in_blackout(now):
            return "no entry: high-impact news blackout"

        sent = self.news.sentiment(now)
        sig = signal_at(row, self.p, sent)
        if sig.side == 0:
            return f"flat (sentiment {sent:+.2f}) {sig.reason}"
        if self.s.long_only and sig.side < 0:
            return "short signal ignored (long_only)"

        bid, ask = self.broker.price()
        entry = ask if sig.side > 0 else bid
        dist = abs(sig.entry_ref - sig.stop)
        stop = round(entry - sig.side * dist, 2)
        tp = round(entry + sig.side * dist * self.p.take_profit_r, 2)
        cost_oz = (ask - bid) + self.s.commission_per_lot / max(self.s.contract_size, 1e-9)
        cost_r = cost_oz / max(dist, 1e-9)
        if cost_r > self.s.risk.max_cost_in_r and (self.s.live_enabled or self.s.demo_enabled):
            return (f"no entry: cost {cost_r:.2f}R > max {self.s.risk.max_cost_in_r}R — this venue is too "
                    f"expensive for this strategy (see docs/STRATEGY.md)")
        lots = self.rm.size_position(eq, entry, stop)
        if lots <= 0:
            return (f"signal {sig.reason} skipped: equity {eq:.2f} too small for min lot "
                    f"{self.s.min_lot} at {self.s.risk.risk_per_trade_pct}% risk (see docs/STRATEGY.md)")
        res = self.broker.open(sig.side, lots, stop, tp)
        if res.ok:
            self.rm.on_trade_opened()
            p = res.position
            self._open[p.id] = vars(p).copy()
            self.journal.event("open", time=self._now_iso(), id=p.id, side=p.side, lots=p.lots, price=round(p.entry, 2), stop=stop,
                               take_profit=tp, reason=sig.reason, equity=round(eq, 2))
            notify(f"OPEN {'BUY' if sig.side > 0 else 'SELL'} {lots} @ {p.entry:.2f} SL {stop} TP {tp} "
                   f"| {sig.reason} | news {sent:+.2f} | cost {cost_r:.3f}R")
            return "opened"
        notify(f"order rejected: {res.message}")
        return res.message

    def _manage(self, pos, row, df=None) -> None:
        bid, ask = self.broker.price()
        px = bid if pos.side > 0 else ask
        # client-side stop enforcement (backup for spot exchanges)
        if pos.stop and ((pos.side > 0 and px <= pos.stop) or (pos.side < 0 and px >= pos.stop)):
            self._close(pos, "client-side stop")
            return
        # time stop: same rule as the backtest (closed bars only, decided on the closed bar)
        close = float(row["close"])
        if self.p.max_hold_bars and pos.opened_at and df is not None and pos.entry:
            held = int((df.index[:-1] >= pd.Timestamp(pos.opened_at)).sum())
            if held >= self.p.max_hold_bars and pos.side * (close - pos.entry) < 0.5 * float(row["atr"]):
                self._close(pos, f"time stop after {held} bars")
                return
        # trailing: same rule as the backtest (initial risk, closed-bar price)
        risk = pos.initial_risk or (abs(pos.entry - pos.stop) if pos.entry else 0)
        if risk and pos.entry and pos.side * (close - pos.entry) >= risk:
            new_stop = round(close - pos.side * self.p.trail_atr_mult * float(row["atr"]), 2)
            if pos.side * (new_stop - pos.stop) > 0:
                if self.broker.modify_stop(pos.id, new_stop):
                    log.info("trail %s stop %.2f -> %.2f", pos.id, pos.stop, new_stop)

    # ------------------------------------------------------------ operations
    def _watchdog(self, bar_time) -> None:
        now = datetime.now(timezone.utc)
        age = (now - pd.Timestamp(bar_time).tz_convert("UTC").to_pydatetime()).total_seconds() \
            if pd.Timestamp(bar_time).tzinfo else 0
        limit = 3 * TF_SECONDS.get(self.p.timeframe, 3600)
        if market_open(now) and age > limit:
            if not self._stale_notified:
                notify(f"⚠️ price feed stale: last bar {bar_time} ({age / 3600:.1f}h old)")
                self._stale_notified = True
        elif self._stale_notified:
            notify("price feed recovered")
            self._stale_notified = False

    def close_all(self, reason: str = "operator close-all") -> int:
        n = 0
        for pos in self.broker.positions():
            self._close(pos, reason)
            n += 1
        self._sync_positions()
        return n

    def status(self) -> str:
        st = self.rm.state
        pos = self.broker.positions()
        lines = [f"mode {self.mode} | equity {self.broker.equity():.2f} | peak {st.peak_equity:.2f}",
                 f"trades today {st.trades_today}/{self.s.risk.max_trades_per_day} | paused {self.paused}",
                 f"halt: {st.halted_reason or 'none'} | news sentiment {self.news.sentiment():+.2f}"]
        for p in pos:
            lines.append(f"open {p.id} {'BUY' if p.side > 0 else 'SELL'} {p.lots} @ {p.entry:.2f} SL {p.stop} TP {p.take_profit}")
        return "\n".join(lines)

    def request_stop(self, *_):
        log.info("shutdown requested")
        self.stop_evt.set()

    def run(self) -> None:
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self.request_stop)
        threading.Thread(target=self.news.run_forever, kwargs={"stop": self.stop_evt},
                         daemon=True, name="news").start()
        self.news.start_telegram()
        try:
            from .telegram_control import start_control
            start_control(self)
        except Exception as exc:  # optional feature
            log.debug("telegram control not started: %s", exc)
        while not self.stop_evt.is_set():
            try:
                with self.lock:
                    msg = self.step()
                if msg not in ("no new bar",):
                    log.info(msg)
            except Exception as exc:  # keep running; positions are protected broker-side
                log.exception("step failed: %s", exc)
                if time.time() - self._last_err > 1800:
                    notify(f"⚠️ step error: {exc}")
                    self._last_err = time.time()
            self.stop_evt.wait(self.s.poll_seconds)
        self.rm.save()
        notify("goldbot stopped (open positions keep their broker-side SL/TP)")
