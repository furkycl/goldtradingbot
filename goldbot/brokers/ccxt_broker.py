"""Crypto-exchange adapter for tokenised gold (e.g. PAXG/USDT, XAUT/USDT) via ccxt.

Why: with ~$100 a standard XAUUSD lot (min 0.01 lot = 1 oz) is far too large
for 1% risk, while PAXG trades in fractional units with ~0.1% fees, so position
sizing actually works at small equity. Spot = long-only, no leverage.

Stops: placed as an exchange stop-loss order right after the fill when the
exchange supports it; otherwise the engine enforces them client-side.

Env: CCXT_EXCHANGE (e.g. "binance"), CCXT_API_KEY, CCXT_SECRET.
Check that the exchange is licensed/permitted for Turkish residents (SPK
crypto-asset service provider list) before using it.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from .base import Broker, OrderResult, Position


class CCXTBroker(Broker):
    def __init__(self, settings):
        import ccxt

        ex_name = os.environ.get("CCXT_EXCHANGE") or settings.broker_options.get("exchange")
        if not ex_name:
            raise ValueError("set CCXT_EXCHANGE or broker_options.exchange (an SPK-permitted exchange)")
        self.ex = getattr(ccxt, ex_name)({
            "apiKey": os.environ.get("CCXT_API_KEY"), "secret": os.environ.get("CCXT_SECRET"),
            "enableRateLimit": True,
        })
        if settings.mode == "demo":
            try:
                self.ex.set_sandbox_mode(True)   # exchange testnet, no real money
            except Exception as exc:
                raise RuntimeError(f"{ex_name} has no sandbox/testnet; demo mode impossible") from exc
        self.ex.load_markets()
        self.s = settings
        self.symbol = settings.broker_options.get("symbol", "PAXG/USDT")
        m = self.ex.market(self.symbol)
        settings.contract_size = 1.0  # 1 token ~ 1 troy oz
        settings.min_lot = float((m.get("limits", {}).get("amount", {}) or {}).get("min") or 0.0001)
        settings.lot_step = float(10 ** -(m.get("precision", {}).get("amount") or 4)) \
            if isinstance(m.get("precision", {}).get("amount"), int) else settings.min_lot
        # only the quantity THIS bot bought is managed; other holdings (e.g. an
        # unlevered core position) are never touched. Persisted across restarts.
        from ..config import ROOT
        self._path = ROOT / "state" / settings.mode / "ccxt_position.json"
        self.stops: dict[str, dict] = json.loads(self._path.read_text()) if self._path.exists() else {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self.stops, indent=1))

    def equity(self) -> float:
        bal = self.ex.fetch_balance()
        base = self.symbol.split("/")[0]
        bid, _ = self.price()
        return float(bal["total"].get("USDT", 0)) + float(bal["total"].get(base, 0)) * bid

    def price(self) -> tuple[float, float]:
        t = self.ex.fetch_ticker(self.symbol)
        return float(t["bid"]), float(t["ask"])

    def candles(self, timeframe: str, count: int) -> pd.DataFrame:
        rows = self.ex.fetch_ohlcv(self.symbol, timeframe, limit=count)
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df[["open", "high", "low", "close", "volume"]]

    def positions(self) -> list[Position]:
        meta = self.stops.get("spot")
        if not meta:
            return []
        base = self.symbol.split("/")[0]
        held = float(self.ex.fetch_balance()["total"].get(base, 0))
        qty = min(held, float(meta["qty"]))
        if qty < self.s.min_lot:          # sold by the exchange stop (or manually)
            return []
        return [Position("spot", 1, qty, meta["entry"], meta["stop"], meta["tp"],
                         meta["opened_at"], meta["initial_risk"])]

    def _place_stop(self, qty: float, stop: float) -> str | None:
        """Exchange-side stop. Tries ccxt's unified stopLossPrice, then Binance-style."""
        attempts = [
            lambda: self.ex.create_order(self.symbol, "market", "sell", qty, None, {"stopLossPrice": stop}),
            lambda: self.ex.create_order(self.symbol, "STOP_LOSS_LIMIT", "sell", qty, stop * 0.998,
                                         {"stopPrice": stop}),
        ]
        for f in attempts:
            try:
                return str(f().get("id"))
            except Exception:
                continue
        return None

    def open(self, side: int, lots: float, stop: float, take_profit: float) -> OrderResult:
        if side < 0:
            return OrderResult(False, message="spot adapter is long-only")
        if not stop:
            return OrderResult(False, message="refused: no stop loss")
        if self.stops.get("spot"):
            return OrderResult(False, message="already holding a bot position")
        o = self.ex.create_market_buy_order(self.symbol, lots)
        entry = float(o.get("average") or o.get("price") or self.price()[1])
        qty = float(o.get("filled") or lots)
        oid = self._place_stop(qty, stop)
        if oid is None:
            # never leave a position without an exchange-side stop
            self.ex.create_market_sell_order(self.symbol, qty)
            return OrderResult(False, message="exchange refused the stop order; position closed immediately")
        self.stops["spot"] = {"qty": qty, "stop": stop, "tp": take_profit, "entry": entry, "stop_id": oid,
                              "opened_at": pd.Timestamp.now(tz="UTC").isoformat(),
                              "initial_risk": abs(entry - stop)}
        self._save()
        m = self.stops["spot"]
        return OrderResult(True, Position("spot", 1, qty, entry, stop, take_profit, m["opened_at"], m["initial_risk"]))

    def modify_stop(self, position_id: str, new_stop: float) -> bool:
        m = self.stops.get("spot")
        if not m:
            return False
        oid = self._place_stop(m["qty"], new_stop)       # place the new stop first ...
        if oid is None:
            return False                                 # ... keep the old one if that fails
        try:
            self.ex.cancel_order(m["stop_id"], self.symbol)
        except Exception:
            pass
        m.update(stop=new_stop, stop_id=oid)
        self._save()
        return True

    def close(self, position_id: str) -> bool:
        m = self.stops.get("spot")
        if not m:
            return False
        try:
            self.ex.cancel_order(m["stop_id"], self.symbol)
        except Exception:
            pass
        pos = self.positions()
        if pos:
            self.ex.create_market_sell_order(self.symbol, pos[0].lots)
        self.stops.pop("spot", None)
        self._save()
        return True
