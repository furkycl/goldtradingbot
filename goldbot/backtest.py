"""Event-driven backtester with realistic costs.

- Signals on bar close, fills on NEXT bar open (no lookahead).
- Spread charged on entry and exit; commission per lot round turn.
- Intrabar stop/TP: if both are touched in the same bar, the stop is assumed
  first (pessimistic).
- Overnight financing charged on open notional (settings.financing_pct_per_year).
- `trade_from`: no signals before this timestamp and stats start there, so
  warm-up bars can never leak in-sample trades into out-of-sample results.
- Uses the same RiskManager as live trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .config import Settings, StrategyParams
from .risk import RiskManager
from .strategy import Selector, families, prepare, signal_at, warmup_bars


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
    entry_bar: int = 0
    strategy: str = ""
    hard_exit_bars: int = 0

    @property
    def r_multiple(self) -> float:
        risk_usd = self.initial_risk * self.lots
        return self.pnl / risk_usd if risk_usd else 0.0


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
                 sentiment_fn: SentimentFn | None = None,
                 trade_from: pd.Timestamp | None = None,
                 entry_fn: Callable[[int, pd.Timestamp], int] | None = None) -> BacktestResult:
    """entry_fn(i, ts) -> side overrides the strategy signal (used for random-entry
    benchmarks: same exits, sizing and costs, random entries)."""
    data = prepare(df, params)
    start_i = 0 if trade_from is None else int(data.index.searchsorted(pd.Timestamp(trade_from)))
    fin_rate = getattr(settings, "financing_pct_per_year", 0.0) / 100
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
    o, h, lo, c = (data[k].to_numpy() for k in ("open", "high", "low", "close"))
    atr_v = data["atr"].to_numpy()

    selector = Selector(families(params), params.ensemble_lookback, params.ensemble_min_score)
    median_atr = float(data["atr"].dropna().median()) if data["atr"].notna().any() else 0.0

    def close_pos(t: Trade, price: float, when, reason: str) -> float:
        fill = price - t.side * half_spread
        gross = t.side * (fill - t.entry) * t.lots * settings.contract_size
        t.exit, t.exit_time, t.reason = fill, when, reason
        t.pnl = gross - settings.commission_per_lot * t.lots
        trades.append(t)
        risk_usd = t.initial_risk * t.lots * settings.contract_size
        selector.update(t.strategy, t.pnl / risk_usd if risk_usd else 0.0)
        return t.pnl

    secs = np.diff(idx.asi8) / 1e9 if len(idx) > 1 else np.array([])
    for i in range(len(data)):
        ts = idx[i]
        # 0) financing on positions held from the previous bar
        if pos is not None and fin_rate and i > 0:
            cash -= pos.lots * settings.contract_size * c[i - 1] * fin_rate * secs[i - 1] / (365 * 86400)
        # 1) execute pending entry at this bar's open
        if pending is not None and pos is None:
            sig = pending
            pending = None
            entry = o[i] + sig.side * half_spread
            stop_dist = abs(sig.entry_ref - sig.stop)
            stop = entry - sig.side * stop_dist
            tp = entry + sig.side * stop_dist * params.take_profit_r
            lots = rm.size_position(cash, entry, stop, risk_scale(params, median_atr, atr_v[i]))
            if lots > 0:
                pos = Trade(sig.side, lots, ts, entry, stop, tp, stop_dist, entry_bar=i,
                            strategy=sig.strategy, hard_exit_bars=sig.hard_exit_bars)
                rm.on_trade_opened()
            else:
                skipped += 1

        # 2) manage open position intrabar
        if pos is not None:
            hit_stop = (lo[i] <= pos.stop) if pos.side > 0 else (h[i] >= pos.stop)
            hit_tp = (h[i] >= pos.take_profit) if pos.side > 0 else (lo[i] <= pos.take_profit)
            if hit_stop:
                gap_price = o[i] if ((pos.side > 0 and o[i] < pos.stop) or (pos.side < 0 and o[i] > pos.stop)) else pos.stop
                cash += close_pos(pos, gap_price, ts, "stop")
                pos = None
            elif hit_tp:
                cash += close_pos(pos, pos.take_profit, ts, "take_profit")
                pos = None
            elif pos.hard_exit_bars and i - pos.entry_bar >= pos.hard_exit_bars:
                cash += close_pos(pos, c[i], ts, "hard_exit")
                pos = None
            elif (params.max_hold_bars and i - pos.entry_bar >= params.max_hold_bars
                  and pos.side * (c[i] - pos.entry) < 0.5 * atr_v[i]):
                cash += close_pos(pos, c[i], ts, "time_stop")
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
        if i >= max(warmup_bars(params), start_i) and pos is None and pending is None and i < len(data) - 1:
            ok, _ = rm.can_trade(0)
            if ok:
                if entry_fn is not None:
                    side = entry_fn(i, ts)
                    sig = _forced_signal(data.iloc[i], params, side) if side else None
                else:
                    sent = sentiment_fn(ts) if sentiment_fn else 0.0
                    sig = signal_at(data.iloc[i], params, sent, selector)
                if sig is not None and sig.side != 0 and not (settings.long_only and sig.side < 0):
                    pending = sig

    if pos is not None:
        cash += close_pos(pos, c[-1], idx[-1], "end_of_data")
        equity_curve[-1] = cash

    eq = pd.Series(equity_curve, index=idx)
    if start_i:
        eq = eq.iloc[max(0, start_i - 1):]
    return BacktestResult(eq, trades, skipped, rm.state.history)


def risk_scale(params: StrategyParams, median_atr: float, atr_now: float) -> float:
    """Volatility-scaled risk: trade smaller when ATR is far above its median
    (Harvey et al.: cuts tails, little effect on Sharpe for commodities)."""
    if not params.risk_vol_scaling or not median_atr or not atr_now or np.isnan(atr_now):
        return 1.0
    return float(np.clip(median_atr / atr_now, 0.5, 1.5))


def _forced_signal(row, params: StrategyParams, side: int):
    from .strategy import Signal
    a = float(row["atr"])
    if not a or np.isnan(a):
        return None
    close = float(row["close"])
    stop = close - side * params.atr_stop_mult * a
    tp = close + side * params.atr_stop_mult * a * params.take_profit_r
    return Signal(side, close, stop, tp, a, "random", "random")
