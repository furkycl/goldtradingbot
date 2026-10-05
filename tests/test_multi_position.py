"""Multi-position mode: one per family, no hedging, total-risk cap, engine == backtest."""
import sys
from pathlib import Path

import pandas as pd

from goldbot.backtest import run_backtest
from goldbot.config import RiskSettings, Settings, StrategyParams
from goldbot.data import synthetic_ohlc

sys.path.insert(0, str(Path(__file__).parent))
from test_core import _replay  # noqa: E402

ALL = ["breakout", "squeeze", "overnight", "meanrev", "spike"]


def _s(n=3, total=3.0):
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    s.risk = RiskSettings(max_open_positions=n, max_total_risk_pct=total, max_trades_per_day=10)
    return s


def test_rules_one_per_family_no_hedge_and_cap():
    df = synthetic_ohlc(4000, seed=12)
    p = StrategyParams(strategies=ALL, adx_min=0, max_hold_bars=12)
    r = run_backtest(df, _s(), p)
    assert r.stats["trades"] > 30
    # positions open at the decision time of trade t = entered earlier and still open at t's entry bar
    max_open = 0
    for t in r.trades:
        open_ = [x for x in r.trades if x.entry_time < t.entry_time and x.exit_time >= t.entry_time]
        same_bar = [x for x in r.trades if x.entry_time == t.entry_time and x is not t]
        assert t.strategy not in [x.strategy for x in open_ + same_bar], "two positions from the same family"
        assert all(x.side == t.side for x in open_ + same_bar), "opposite directions held at once"
        risk = sum(x.initial_risk * x.lots * 100 for x in open_ + same_bar + [t])
        assert risk <= 10_000 * 1.6 * 0.03 + 1e-6              # cap vs (generously grown) equity
        max_open = max(max_open, len(open_) + len(same_bar) + 1)
    assert 2 <= max_open <= 3


def test_single_position_mode_unchanged():
    df = synthetic_ohlc(3000, seed=3)
    p = StrategyParams(strategies=["breakout", "squeeze"], adx_min=0)
    a = run_backtest(df, Settings(starting_equity=10_000, financing_pct_per_year=0.0), p)
    b = run_backtest(df, _s(n=1), p)
    assert [t.entry_time for t in a.trades] == [t.entry_time for t in b.trades]


def test_multi_engine_matches_backtest(tmp_path):
    df = synthetic_ohlc(3000, seed=9)
    s = _s()
    p = StrategyParams(strategies=ALL, adx_min=0, max_hold_bars=12)
    broker = _replay(df, s, p, tmp_path, 500, 1900)
    bt = run_backtest(df.iloc[:1900], s, p, trade_from=df.index[500])
    eng = sorted(broker.closed, key=lambda c: (c["opened_at"], c["entry"]))
    bts = sorted(bt.trades, key=lambda t: (t.entry_time.isoformat(), t.entry))
    n = min(len(eng), len(bts), 15)
    assert n >= 8
    for c, t in zip(eng[:n], bts[:n]):
        assert pd.Timestamp(c["opened_at"]) == t.entry_time
        assert abs(c["pnl"] - t.pnl) < 0.05, (c["reason"], t.reason, t.strategy)
