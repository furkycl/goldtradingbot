from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class Position:
    id: str
    side: int          # +1 long / -1 short
    lots: float
    entry: float
    stop: float
    take_profit: float
    opened_at: str = ""   # ISO UTC time of the entry bar ("" if unknown)
    initial_risk: float = 0.0  # |entry - initial stop|; trailing starts after 1R


@dataclass
class OrderResult:
    ok: bool
    position: Position | None = None
    message: str = ""


class Broker(ABC):
    """Every open() MUST carry a stop loss that lives on the broker side."""

    @abstractmethod
    def equity(self) -> float: ...

    @abstractmethod
    def price(self) -> tuple[float, float]:
        """(bid, ask)"""

    @abstractmethod
    def candles(self, timeframe: str, count: int) -> pd.DataFrame: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def open(self, side: int, lots: float, stop: float, take_profit: float) -> OrderResult: ...

    @abstractmethod
    def modify_stop(self, position_id: str, new_stop: float) -> bool: ...

    @abstractmethod
    def close(self, position_id: str) -> bool: ...

    def closed_pnl(self, position_id: str) -> float | None:
        """Realised P&L of a closed position, if the broker can tell (else None)."""
        return None
