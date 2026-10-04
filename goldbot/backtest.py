"""Event-driven backtester with realistic costs.

- Signals on bar close, fills on NEXT bar open (no lookahead).
- Spread charged on entry and exit; commission per lot round turn.
- Intrabar stop/TP: if both are touched in the same bar, the stop is assumed
  first (pessimistic).
- Uses the same RiskManager as live trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .config import Settings, StrategyParams
from .risk import RiskManager
from .strategy import prepare, signal_at, warmup_bars


@dataclass
class Trade:
    side: int
    lots: float
    entry_time: pd.Timestamp
    entry: float
    stop: float
    take_profit: float
    initial_risk: float
    exit_time: pd.Timestamp | None = None
    exit: float | None = None
    pnl: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: list[Trade] = field(default_factory=list)
    skipped_min_lot: int = 0
    halts: list[str] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        eq = self.equity
        start, end = float(eq.iloc[0]), float(eq.iloc[-1])
        peak = eq.cummax()
        max_dd = float(((peak - eq) / peak).max() * 100) if len(eq) else 0.0
        pnls = np.array([t.pnl for t in self.trades])
        wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
        rets = eq.pct_change().dropna()
        bars_per_year = _bars_per_year(eq.index)
        sharpe = float(rets.mean() / rets.std() * np.sqrt(bars_per_year)) if rets.std() > 0 else 0.0
        pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf") if len(wins) else 0.0
        return {
            "start_equity": round(start, 2),
            "end_equity": round(end, 2),
            "return_pct": round(100 * (end / start - 1), 2) if start else 0.0,
            "max_drawdown_pct": round(max_dd, 2),
            "trades": len(self.trades),
            "win_rate_pct": round(100 * len(wins) / len(pnls), 1) if len(pnls) else 0.0,
            "profit_factor": round(pf, 2) if pf != float("inf") else 999.0,
            "sharpe": round(sharpe, 2),
            "skipped_below_min_lot": self.skipped_min_lot,
            "halts": self.halts[-3:],
        }


def _bars_per_year(idx: pd.Index) -> float:
    if len(idx) < 2:
        return 252.0
    step = pd.Series(idx).diff().median().total_seconds()
    # gold trades ~23h x 5d
    return max(1.0, 252 * 23 * 3600 / step) if step > 0 else 252.0


SentimentFn = Callable[[pd.Timestamp], float]


def run_backtest(df: pd.DataFrame, settings: Settings, params: StrategyParams,
                 sentiment_fn: SentimentFn | None = None) -> BacktestResult:
    data = prepare(df, params)
    rm = RiskManager(settings.risk, settings.contract_size, settings.min_lot,
                     settings.lot_step, settings.starting_equity)
    cash = settings.starting_equity
    half_spread = settings.spread / 2
    pos: Trade | None = None
    pending = None
    trades: list[Trade] = []
    equity_curve = []
    skipped = 0

    idx = data.index
    o, h, l, c = (data[k].to_numpy() for k in ("open", "high", "low", "close"))
    atr_v = data["atr"].to_numpy()

    def close_pos(t: Trade, price: float, when, reason: str) -> float:
        fill = price - t.side * half_spread
        gross = t.side * (fill - t.entry) * t.lots * settings.contract_size
        t.exit, t.exit_time, t.reason = fill, when, reason
        t.pnl = gross - settings.commission_per_lot * t.lots
        trades.append(t)
        return t.pnl

    for i in range(len(data)):
        ts = idx[i]
        # 1) execute pending entry at this bar's open
        if pending is not None and pos is None:
            sig = pending
            pending = None
            entry = o[i] + sig.side * half_spread
            stop_dist = abs(sig.entry_ref - sig.stop)
            stop = entry - sig.side * stop_dist
            tp = entry + sig.side * stop_dist * params.take_profit_r
            lots = rm.size_position(cash, entry, stop)
            if lots > 0:
                pos = Trade(sig.side, lots, ts, entry, stop, tp, stop_dist)
                rm.on_trade_opened()
            else:
                skipped += 1

        # 2) manage open position intrabar
        if pos is not None:
            hit_stop = (l[i] <= pos.stop) if pos.side > 0 else (h[i] >= pos.stop)
            hit_tp = (h[i] >= pos.take_profit) if pos.side > 0 else (l[i] <= pos.take_profit)
            if hit_stop:
                gap_price = o[i] if ((pos.side > 0 and o[i] < pos.stop) or (pos.side < 0 and o[i] > pos.stop)) else pos.stop
                cash += close_pos(pos, gap_price, ts, "stop")
                pos = None
            elif hit_tp:
                cash += close_pos(pos, pos.take_profit, ts, "take_profit")
                pos = None
            else:
                # trailing stop once 1R in profit
                move = pos.side * (c[i] - pos.entry)
                if move >= pos.initial_risk and not np.isnan(atr_v[i]):
                    new_stop = c[i] - pos.side * params.trail_atr_mult * atr_v[i]
                    if pos.side * (new_stop - pos.stop) > 0:
                        pos.stop = new_stop

        # 3) mark to market
        mtm = cash
        if pos is not None:
            mtm += pos.side * (c[i] - pos.entry) * pos.lots * settings.contract_size
        equity_curve.append(mtm)
        rm.on_new_bar(ts.date(), mtm)

        # 4) new signal on close
        if i >= warmup_bars(params) and pos is None and pending is None:
            ok, _ = rm.can_trade(0)
            if ok:
                sent = sentiment_fn(ts) if sentiment_fn else 0.0
                sig = signal_at(data.iloc[i], params, sent)
                if sig.side != 0 and not (settings.long_only and sig.side < 0):
                    pending = sig

    if pos is not None:
        cash += close_pos(pos, c[-1], idx[-1], "end_of_data")
        equity_curve[-1] = cash

    return BacktestResult(pd.Series(equity_curve, index=idx), trades, skipped, rm.state.history)
