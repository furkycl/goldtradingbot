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
        self.ex.load_markets()
        self.s = settings
        self.symbol = settings.broker_options.get("symbol", "PAXG/USDT")
        m = self.ex.market(self.symbol)
        settings.contract_size = 1.0  # 1 token ~ 1 troy oz
        settings.min_lot = float((m.get("limits", {}).get("amount", {}) or {}).get("min") or 0.0001)
        settings.lot_step = float(10 ** -(m.get("precision", {}).get("amount") or 4)) \
            if isinstance(m.get("precision", {}).get("amount"), int) else settings.min_lot
        self.stops: dict[str, tuple[float, float]] = {}

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
        base = self.symbol.split("/")[0]
        amt = float(self.ex.fetch_balance()["total"].get(base, 0))
        if amt < self.s.min_lot:
            return []
        stop, tp = self.stops.get("spot", (0.0, 0.0))
        return [Position("spot", 1, amt, 0.0, stop, tp)]

    def open(self, side: int, lots: float, stop: float, take_profit: float) -> OrderResult:
        if side < 0:
            return OrderResult(False, message="spot adapter is long-only")
        if not stop:
            return OrderResult(False, message="refused: no stop loss")
        o = self.ex.create_market_buy_order(self.symbol, lots)
        self.stops["spot"] = (stop, take_profit)
        try:
            self.ex.create_order(self.symbol, "STOP_LOSS_LIMIT", "sell", lots, stop * 0.998,
                                 {"stopPrice": stop})
        except Exception:
            pass  # engine enforces the stop client-side
        return OrderResult(True, Position("spot", 1, lots, float(o.get("average") or o.get("price") or 0), stop, take_profit))

    def modify_stop(self, position_id: str, new_stop: float) -> bool:
        if "spot" in self.stops:
            self.stops["spot"] = (new_stop, self.stops["spot"][1])
            return True
        return False

    def close(self, position_id: str) -> bool:
        try:
            self.ex.cancel_all_orders(self.symbol)
        except Exception:
            pass
        pos = self.positions()
        if not pos:
            return False
        self.ex.create_market_sell_order(self.symbol, pos[0].lots)
        self.stops.pop("spot", None)
        return True
