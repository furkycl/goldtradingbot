"""Live / paper trading loop.

Each poll:
  1. refresh candles; act only when a NEW bar has closed
  2. manage open position: trailing stop (sent to broker), client-side stop check
  3. risk gates: daily loss, drawdown kill switch, max trades, news blackout
  4. strategy signal (+ news sentiment) -> sized order with broker-side SL/TP
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

from .brokers import make_broker
from .brokers.paper import PaperBroker
from .config import Settings, StrategyParams
from .news import NewsAggregator
from .risk import RiskManager
from .strategy import prepare, signal_at, warmup_bars

log = logging.getLogger("goldbot.engine")


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


class Engine:
    def __init__(self, settings: Settings, params: StrategyParams, broker=None, news=None):
        self.s, self.p = settings, params
        self.broker = broker or make_broker(settings)
        self.news = news if news is not None else NewsAggregator(
            rss=settings.news.get("rss"), telegram=settings.news.get("telegram"),
            blackout_minutes=settings.news_blackout_minutes)
        self.rm = RiskManager(settings.risk, settings.contract_size, settings.min_lot,
                              settings.lot_step, self.broker.equity())
        self.last_bar = None
        self.stop_evt = threading.Event()
        mode = "LIVE" if settings.live_enabled else "PAPER"
        notify(f"goldbot started in {mode} mode, broker={type(self.broker).__name__}, "
               f"equity={self.broker.equity():.2f}")

    def step(self) -> str:
        df = self.broker.candles(self.p.timeframe, warmup_bars(self.p) + 200)
        if len(df) < warmup_bars(self.p):
            return "not enough data"
        if isinstance(self.broker, PaperBroker):
            self.broker.set_last(float(df["close"].iloc[-1]))
            self.broker.check_stops(float(df["high"].iloc[-1]), float(df["low"].iloc[-1]))

        bar_time = df.index[-1]
        if bar_time == self.last_bar:
            return "no new bar"
        self.last_bar = bar_time
        data = prepare(df, self.p)
        row = data.iloc[-2]  # last CLOSED bar
        now = datetime.now(timezone.utc)
        eq = self.broker.equity()
        self.rm.on_new_bar(now.date(), eq)

        positions = self.broker.positions()
        for pos in positions:
            self._manage(pos, row)
        positions = self.broker.positions()

        ok, why = self.rm.can_trade(len(positions))
        if not ok:
            return f"no entry: {why}"
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
        lots = self.rm.size_position(eq, entry, stop)
        if lots <= 0:
            return (f"signal {sig.reason} skipped: equity {eq:.2f} too small for min lot "
                    f"{self.s.min_lot} at 1% risk (see README: small accounts)")
        res = self.broker.open(sig.side, lots, stop, tp)
        if res.ok:
            self.rm.on_trade_opened()
            notify(f"OPEN {'BUY' if sig.side > 0 else 'SELL'} {lots} @ {entry:.2f} SL {stop} TP {tp} "
                   f"| {sig.reason} | news {sent:+.2f}")
            return "opened"
        notify(f"order rejected: {res.message}")
        return res.message

    def _manage(self, pos, row) -> None:
        bid, ask = self.broker.price()
        px = bid if pos.side > 0 else ask
        # client-side stop enforcement (backup for spot exchanges)
        if pos.stop and ((pos.side > 0 and px <= pos.stop) or (pos.side < 0 and px >= pos.stop)):
            self.broker.close(pos.id)
            notify(f"STOP hit {pos.id} @ {px:.2f}")
            return
        risk = abs(pos.entry - pos.stop) if pos.entry else 0
        if risk and pos.side * (px - pos.entry) >= risk:
            new_stop = round(px - pos.side * self.p.trail_atr_mult * float(row["atr"]), 2)
            if pos.side * (new_stop - pos.stop) > 0:
                if self.broker.modify_stop(pos.id, new_stop):
                    log.info("trail %s stop %.2f -> %.2f", pos.id, pos.stop, new_stop)

    def run(self) -> None:
        threading.Thread(target=self.news.run_forever, kwargs={"stop": self.stop_evt},
                         daemon=True, name="news").start()
        self.news.start_telegram()
        while not self.stop_evt.is_set():
            try:
                msg = self.step()
                if msg not in ("no new bar",):
                    log.info(msg)
            except Exception as exc:  # keep running; positions are protected broker-side
                log.exception("step failed: %s", exc)
            self.stop_evt.wait(self.s.poll_seconds)
