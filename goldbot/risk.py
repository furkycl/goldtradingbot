"""Risk management: position sizing, daily loss limit, drawdown kill switch.

Every order goes through RiskManager.size_position() and RiskManager.can_trade().
A trade without a stop loss is impossible by construction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from .config import RiskSettings


@dataclass
class RiskState:
    peak_equity: float
    day: date | None = None
    day_start_equity: float = 0.0
    trades_today: int = 0
    halted_reason: str = ""
    history: list[str] = field(default_factory=list)


class RiskManager:
    def __init__(self, cfg: RiskSettings, contract_size: float, min_lot: float,
                 lot_step: float, starting_equity: float):
        self.cfg = cfg
        self.contract_size = contract_size
        self.min_lot = min_lot
        self.lot_step = lot_step
        self.state = RiskState(peak_equity=starting_equity, day_start_equity=starting_equity)

    # ------------------------------------------------------------------ state
    def on_new_bar(self, today: date, equity: float) -> None:
        if self.state.day != today:
            self.state.day = today
            self.state.day_start_equity = equity
            self.state.trades_today = 0
            if self.state.halted_reason.startswith("daily"):
                self.state.halted_reason = ""
        self.state.peak_equity = max(self.state.peak_equity, equity)
        self._check_limits(equity)

    def on_trade_opened(self) -> None:
        self.state.trades_today += 1

    def _check_limits(self, equity: float) -> None:
        if self.state.halted_reason.startswith("drawdown"):
            return  # permanent until a human resets it
        dd = 100 * (1 - equity / self.state.peak_equity) if self.state.peak_equity > 0 else 0
        if dd >= self.cfg.max_drawdown_pct:
            self.state.halted_reason = f"drawdown kill switch: {dd:.1f}% from peak"
            self.state.history.append(self.state.halted_reason)
            return
        if self.state.day_start_equity > 0:
            day_loss = 100 * (1 - equity / self.state.day_start_equity)
            if day_loss >= self.cfg.max_daily_loss_pct:
                self.state.halted_reason = f"daily loss limit: {day_loss:.1f}%"
                self.state.history.append(self.state.halted_reason)

    def can_trade(self, open_positions: int) -> tuple[bool, str]:
        if self.state.halted_reason:
            return False, self.state.halted_reason
        if open_positions >= self.cfg.max_open_positions:
            return False, "max open positions"
        if self.state.trades_today >= self.cfg.max_trades_per_day:
            return False, "max trades per day"
        return True, ""

    # ----------------------------------------------------------------- sizing
    def size_position(self, equity: float, entry: float, stop: float) -> float:
        """Lots such that hitting the stop loses <= risk_per_trade_pct of equity,
        and notional <= max_leverage * equity. Returns 0 if below the min lot."""
        stop_dist = abs(entry - stop)
        if stop_dist <= 0 or equity <= 0 or entry <= 0:
            return 0.0
        risk_usd = equity * self.cfg.risk_per_trade_pct / 100
        lots_by_risk = risk_usd / (stop_dist * self.contract_size)
        lots_by_leverage = equity * self.cfg.max_leverage / (entry * self.contract_size)
        lots = min(lots_by_risk, lots_by_leverage)
        lots = math.floor(lots / self.lot_step + 1e-9) * self.lot_step
        lots = round(lots, 8)
        return lots if lots >= self.min_lot else 0.0
