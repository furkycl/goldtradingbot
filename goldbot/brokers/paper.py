"""Paper broker: simulated fills against a price feed (default: yfinance GC=F,
or replayed candles). Persists state to state/paper.json."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

from ..config import ROOT
from .base import Broker, OrderResult, Position

STATE = ROOT / "state" / "paper.json"


class PaperBroker(Broker):
    def __init__(self, settings, feed: pd.DataFrame | None = None, state_path: Path | None = STATE):
        self.s = settings
        self.state_path = state_path
        self.cash = settings.starting_equity
        self._pos: dict[str, Position] = {}
        self.closed: list[dict] = []
        self.feed = feed
        self._last: float | None = None
        self._cache: pd.DataFrame | None = None
        self._cache_t = 0.0
        self._load()

    # ---------------------------------------------------------- persistence
    def _load(self) -> None:
        if self.state_path and self.state_path.exists():
            d = json.loads(self.state_path.read_text())
            self.cash = d["cash"]
            self._pos = {k: Position(**v) for k, v in d["positions"].items()}
            self.closed = d.get("closed", [])

    def _save(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(exist_ok=True)
        self.state_path.write_text(json.dumps({
            "cash": self.cash,
            "positions": {k: vars(v) for k, v in self._pos.items()},
            "closed": self.closed[-500:],
        }, indent=1, default=str))

    # --------------------------------------------------------------- market
    def candles(self, timeframe: str, count: int) -> pd.DataFrame:
        if self.feed is not None:
            return self.feed.tail(count)
        import time
        if self._cache is not None and time.time() - self._cache_t < 55:
            return self._cache.tail(count)
        from ..data import load_yfinance
        bars_per_day = {"5m": 276, "15m": 92, "30m": 46, "1h": 23, "4h": 6, "1d": 1}.get(timeframe, 23)
        days = int(count / bars_per_day * 1.6) + 7          # weekends + holidays margin
        days = min(days, 59 if timeframe in ("5m", "15m", "30m") else 729)
        df = load_yfinance(self.s.broker_options.get("paper_symbol", "GC=F"), period=f"{days}d",
                           interval=timeframe, min_bars=min(count, 50))
        self._cache, self._cache_t = df, time.time()
        return df.tail(count)

    def closed_trade(self, position_id: str) -> dict | None:
        for c in reversed(self.closed):
            if c["id"] == position_id:
                return {"pnl": float(c["pnl"]), "exit": float(c["exit"])}
        return None

    def set_last(self, price: float) -> None:
        self._last = price

    def price(self) -> tuple[float, float]:
        mid = self._last if self._last is not None else float(self.candles("1h", 1)["close"].iloc[-1])
        half = self.s.spread / 2
        return mid - half, mid + half

    # -------------------------------------------------------------- account
    def positions(self) -> list[Position]:
        return list(self._pos.values())

    def equity(self) -> float:
        if not self._pos:
            return self.cash
        bid, ask = self.price()
        u = sum(p.side * ((bid if p.side > 0 else ask) - p.entry) * p.lots * self.s.contract_size
                for p in self._pos.values())
        return self.cash + u

    def open(self, side: int, lots: float, stop: float, take_profit: float) -> OrderResult:
        if not stop:
            return OrderResult(False, message="refused: no stop loss")
        bid, ask = self.price()
        entry = ask if side > 0 else bid
        if self.feed is not None and len(self.feed):
            opened = pd.Timestamp(self.feed.index[-1]).isoformat()
        else:
            opened = pd.Timestamp.now(tz="UTC").isoformat()
        p = Position(uuid.uuid4().hex[:8], side, lots, entry, stop, take_profit, opened,
                     abs(entry - stop))
        self._pos[p.id] = p
        self._save()
        return OrderResult(True, p)

    def modify_stop(self, position_id: str, new_stop: float) -> bool:
        if position_id in self._pos:
            self._pos[position_id].stop = new_stop
            self._save()
            return True
        return False

    def close(self, position_id: str, price: float | None = None, reason: str = "manual") -> bool:
        p = self._pos.pop(position_id, None)
        if p is None:
            return False
        bid, ask = self.price()
        fill = price if price is not None else (bid if p.side > 0 else ask)
        pnl = p.side * (fill - p.entry) * p.lots * self.s.contract_size - self.s.commission_per_lot * p.lots
        self.cash += pnl
        self.closed.append({**vars(p), "exit": fill, "pnl": round(pnl, 2), "reason": reason})
        self._save()
        return True

    def check_stops(self, high: float, low: float, open_: float | None = None) -> list[str]:
        """Simulate broker-side stop/TP execution for the latest bar range, with the
        same rules as the backtest: gaps through the stop fill at the open, and
        every exit pays half the spread."""
        hits = []
        half = self.s.spread / 2
        for p in list(self._pos.values()):
            if (p.side > 0 and low <= p.stop) or (p.side < 0 and high >= p.stop):
                px = p.stop
                if open_ is not None and ((p.side > 0 and open_ < p.stop) or (p.side < 0 and open_ > p.stop)):
                    px = open_
                self.close(p.id, px - p.side * half, "stop"); hits.append(p.id)
            elif p.take_profit and ((p.side > 0 and high >= p.take_profit) or (p.side < 0 and low <= p.take_profit)):
                self.close(p.id, p.take_profit - p.side * half, "take_profit"); hits.append(p.id)
        return hits
