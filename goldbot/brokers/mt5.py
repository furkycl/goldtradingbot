"""MetaTrader 5 adapter (Windows, `pip install MetaTrader5`).

MT5 is offered by most SPK-licensed Turkish intermediaries and by most global
brokers, so this is the most portable live adapter. SL/TP are attached to the
order itself, so they live on the broker server.

Env: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER (+ optional MT5_PATH to terminal64.exe).
"""
from __future__ import annotations

import os

import pandas as pd

from .base import Broker, OrderResult, Position

TF = {"1m": "TIMEFRAME_M1", "5m": "TIMEFRAME_M5", "15m": "TIMEFRAME_M15",
      "30m": "TIMEFRAME_M30", "1h": "TIMEFRAME_H1", "4h": "TIMEFRAME_H4", "1d": "TIMEFRAME_D1"}


class MT5Broker(Broker):
    def __init__(self, settings):
        import MetaTrader5 as mt5

        self.mt5 = mt5
        self.s = settings
        self.symbol = settings.broker_options.get("symbol", settings.symbol)
        self.magic = int(settings.broker_options.get("magic", 770077))
        ok = mt5.initialize(
            path=os.environ.get("MT5_PATH") or None,
            login=int(os.environ["MT5_LOGIN"]),
            password=os.environ["MT5_PASSWORD"],
            server=os.environ["MT5_SERVER"],
        )
        if not ok:
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        info = mt5.symbol_info(self.symbol)
        if info is None or not mt5.symbol_select(self.symbol, True):
            raise RuntimeError(f"symbol {self.symbol} not available at this broker")
        settings.contract_size = info.trade_contract_size
        settings.min_lot = info.volume_min
        settings.lot_step = info.volume_step

    def equity(self) -> float:
        return float(self.mt5.account_info().equity)

    def price(self) -> tuple[float, float]:
        t = self.mt5.symbol_info_tick(self.symbol)
        return float(t.bid), float(t.ask)

    def candles(self, timeframe: str, count: int) -> pd.DataFrame:
        rates = self.mt5.copy_rates_from_pos(self.symbol, getattr(self.mt5, TF[timeframe]), 0, count)
        df = pd.DataFrame(rates)
        df.index = pd.to_datetime(df["time"], unit="s", utc=True)
        return df[["open", "high", "low", "close"]]

    def positions(self) -> list[Position]:
        out = []
        for p in self.mt5.positions_get(symbol=self.symbol) or []:
            if p.magic != self.magic:
                continue
            side = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
            out.append(Position(str(p.ticket), side, p.volume, p.price_open, p.sl, p.tp))
        return out

    def open(self, side: int, lots: float, stop: float, take_profit: float) -> OrderResult:
        if not stop:
            return OrderResult(False, message="refused: no stop loss")
        bid, ask = self.price()
        req = {
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": lots,
            "type": self.mt5.ORDER_TYPE_BUY if side > 0 else self.mt5.ORDER_TYPE_SELL,
            "price": ask if side > 0 else bid, "sl": stop, "tp": take_profit,
            "deviation": 30, "magic": self.magic, "comment": "goldbot",
            "type_time": self.mt5.ORDER_TIME_GTC, "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        r = self.mt5.order_send(req)
        if r is None or r.retcode != self.mt5.TRADE_RETCODE_DONE:
            return OrderResult(False, message=f"order failed: {getattr(r, 'comment', self.mt5.last_error())}")
        return OrderResult(True, Position(str(r.order), side, lots, r.price, stop, take_profit))

    def modify_stop(self, position_id: str, new_stop: float) -> bool:
        pos = next((p for p in self.positions() if p.id == position_id), None)
        if pos is None:
            return False
        r = self.mt5.order_send({"action": self.mt5.TRADE_ACTION_SLTP, "position": int(position_id),
                                 "symbol": self.symbol, "sl": new_stop, "tp": pos.take_profit})
        return r is not None and r.retcode == self.mt5.TRADE_RETCODE_DONE

    def close(self, position_id: str) -> bool:
        pos = next((p for p in self.positions() if p.id == position_id), None)
        if pos is None:
            return False
        bid, ask = self.price()
        r = self.mt5.order_send({
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": pos.lots,
            "type": self.mt5.ORDER_TYPE_SELL if pos.side > 0 else self.mt5.ORDER_TYPE_BUY,
            "position": int(position_id), "price": bid if pos.side > 0 else ask,
            "deviation": 30, "magic": self.magic, "type_filling": self.mt5.ORDER_FILLING_IOC,
        })
        return r is not None and r.retcode == self.mt5.TRADE_RETCODE_DONE
