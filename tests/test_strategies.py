"""Strategy library + ensemble: no lookahead, shared exits, engine == backtest."""
import pandas as pd
import pytest

from goldbot.backtest import run_backtest
from goldbot.config import Settings, StrategyParams
from goldbot.data import synthetic_ohlc
from goldbot.ensemble import Selector
from goldbot.strategies import REGISTRY
from goldbot.strategies.base import Signal
from goldbot.strategy import candidates_at, prepare, warmup_bars

ALL = list(REGISTRY)


@pytest.fixture
def df():
    return synthetic_ohlc(3000, seed=9)


def _s(**kw):
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


@pytest.mark.parametrize("name", ALL)
def test_family_no_lookahead_and_valid_stops(df, name):
    p = StrategyParams(strategies=[name], adx_min=0)
    full, cut = prepare(df, p), prepare(df.iloc[:2000], p)
    for col in set(full.columns) - {"open", "high", "low", "close"}:
        a, b = full[col].iloc[1990:2000], cut[col].iloc[1990:2000]
        assert ((a == b) | (a.isna() & b.isna())).all(), col
    n = 0
    for i in range(warmup_bars(p), len(full)):
        sig = candidates_at(full.iloc[i], p)[0]
        if sig.side:
            n += 1
            assert sig.strategy == name
            assert (sig.entry_ref - sig.stop) * sig.side > 0
            assert (sig.take_profit - sig.entry_ref) * sig.side > 0
    assert n > 0, f"{name} never fires on synthetic data"


@pytest.mark.parametrize("name", ALL)
def test_family_backtests_with_shared_risk(df, name):
    p = StrategyParams(strategies=[name], adx_min=0)
    r = run_backtest(df, _s(), p)
    assert r.stats["trades"] > 0
    assert all(t.stop and t.lots > 0 and t.strategy == name for t in r.trades)
    if name == "overnight":
        assert all(t.side == 1 for t in r.trades)
        assert any(t.reason == "hard_exit" for t in r.trades)


def test_selector_benches_losers_and_stands_aside_on_conflict():
    sel = Selector(["a", "b"], lookback=5, min_score=-0.3)
    for _ in range(10):
        sel.update("a", -1.0)
    sel.update("b", 0.5)
    long_a = Signal(1, 100, 99, 102, 1, "", "a")
    short_b = Signal(-1, 100, 101, 98, 1, "", "b")
    assert sel.pick([long_a, short_b]) is short_b          # a is benched
    sel2 = Selector(["a", "b"])
    assert sel2.pick([long_a, short_b]) is None            # equal scores, opposite sides
    assert sel2.pick([long_a, Signal(0, 100, 0, 0, 1, "", "b")]) is long_a
    d = sel.to_dict(); sel3 = Selector(["a", "b"]); sel3.load(d)
    assert sel3.score == sel.score


def test_ensemble_backtest_uses_several_families(df):
    p = StrategyParams(strategies=ALL, adx_min=0)
    r = run_backtest(df, _s(), p)
    used = {t.strategy for t in r.trades}
    assert len(used) >= 2 and r.stats["trades"] > 20


def test_vol_scaled_risk_reduces_size_in_high_vol(df):
    from goldbot.backtest import risk_scale
    p = StrategyParams(risk_vol_scaling=True)
    assert risk_scale(p, 10.0, 20.0) == 0.5 and risk_scale(p, 10.0, 5.0) == 1.5
    assert risk_scale(StrategyParams(), 10.0, 20.0) == 1.0


def test_ensemble_engine_matches_backtest(df, tmp_path):
    import sys
    sys.path.insert(0, str(pd.io.common.Path(__file__).parent))
    from test_core import _replay
    s = _s()
    p = StrategyParams(strategies=ALL, adx_min=0, max_hold_bars=12)
    broker = _replay(df, s, p, tmp_path, 500, 1700)
    bt = run_backtest(df.iloc[:1700], s, p, trade_from=df.index[500])
    n = min(len(broker.closed), len(bt.trades), 12)
    assert n >= 6
    for c, t in zip(broker.closed[:n], bt.trades[:n]):
        assert pd.Timestamp(c["opened_at"]) == t.entry_time
        assert abs(c["pnl"] - t.pnl) < 0.05, (c["reason"], t.reason, t.strategy)


def test_touch_entry_fills_at_level_or_open(df):
    from goldbot.config import Settings
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    p = StrategyParams(strategies=["breakout"], adx_min=0, entry_mode="touch")
    r = run_backtest(df, s, p)
    assert r.stats["trades"] > 10
    d = prepare(df, p)
    for t in r.trades[:40]:
        i = d.index.get_loc(t.entry_time)
        bar = d.iloc[i]
        # fill price (ex spread) is the breakout level or the open if it gapped through
        raw = t.entry - t.side * s.spread / 2
        assert bar["low"] - 1e-9 <= raw <= bar["high"] + 1e-9
        assert t.strategy == "breakout" and t.initial_risk > 0
    import pytest
    with pytest.raises(ValueError):
        from goldbot.brokers.paper import PaperBroker
        from goldbot.engine import Engine
        from goldbot.news import NewsAggregator
        Engine(s, p, broker=PaperBroker(s, feed=df.iloc[:400], state_path=None), news=NewsAggregator(rss=[]))
