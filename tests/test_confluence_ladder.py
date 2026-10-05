import pandas as pd

from goldbot.backtest import run_backtest
from goldbot.brokers.paper import PaperBroker
from goldbot.config import RiskSettings, Settings, StrategyParams
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine
from goldbot.journal import Journal
from goldbot.news import NewsAggregator
from goldbot.risk import RiskManager
from goldbot.strategy import candidates_at, confluence, prepare, tier_multiplier, warmup_bars

TIERS = [[0.75, 1.5], [0.5, 1.0], [0.0, 0.5]]


def test_tier_lookup():
    assert tier_multiplier(0.9, TIERS) == 1.5
    assert tier_multiplier(0.6, TIERS) == 1.0
    assert tier_multiplier(0.1, TIERS) == 0.5
    assert tier_multiplier(0.9, []) == 1.0


def test_confluence_score_bounds_and_news_effect():
    df = synthetic_ohlc(2000, seed=5)
    p = StrategyParams(strategies=["breakout"], adx_min=0, confluence_tiers=TIERS)
    d = prepare(df, p)
    row = d.iloc[1500]
    s_pos, _ = confluence(row, 1, +0.8, agree=1)
    s_neg, _ = confluence(row, 1, -0.1, agree=0)
    assert 0 <= s_neg < s_pos <= 1
    sigs = [c for i in range(warmup_bars(p), len(d)) for c in candidates_at(d.iloc[i], p) if c.side]
    assert sigs and all(c.risk_mult in (0.5, 1.0, 1.5) for c in sigs)
    assert any("conf" in c.reason for c in sigs)


def test_tiers_change_sizing_not_entries():
    df = synthetic_ohlc(3000, seed=7)
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    start = df.index[600]                     # after both warm-ups (tiers need 21 days of history)
    base = run_backtest(df, s, StrategyParams(strategies=["breakout"], adx_min=0), trade_from=start)
    tiered = run_backtest(df, s, StrategyParams(strategies=["breakout"], adx_min=0, confluence_tiers=TIERS),
                          trade_from=start)
    assert [t.entry_time for t in base.trades] == [t.entry_time for t in tiered.trades]
    # first trade: identical equity, so the lot ratio IS the tier multiplier (later trades diverge
    # because the equity paths differ)
    first = round(tiered.trades[0].lots / base.trades[0].lots, 1)
    assert first in (0.5, 1.0, 1.5)
    assert any(abs(t2.lots - t1.lots) > 1e-9 for t1, t2 in zip(base.trades, tiered.trades))


def test_stretch_filter_only_removes_entries():
    df = synthetic_ohlc(3000, seed=7)
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    p0 = StrategyParams(strategies=["breakout"], adx_min=0)
    p1 = StrategyParams(strategies=["breakout"], adx_min=0, max_entry_stretch_atr=1.5)
    a = run_backtest(df, s, p0).trades
    b = run_backtest(df, s, p1).trades
    assert 0 < len(b)
    d = prepare(df, p1)
    for t in b:   # every surviving entry was decided on a bar within 1.5 ATR of the fast EMA
        row = d.loc[: t.entry_time].iloc[-2]
        assert abs(row["close"] - row["ema_fast"]) / row["atr"] <= 1.5
    far = [t for t in a if abs((r := d.loc[: t.entry_time].iloc[-2])["close"] - r["ema_fast"]) / r["atr"] > 1.5]
    assert far and not any(t.entry_time in {x.entry_time for x in far} for t in b)


def test_risk_ladder_and_trading_cap():
    rm = RiskManager(RiskSettings(risk_per_trade_pct=1.0, risk_ladder=[[0, 2.0], [1000, 1.0], [5000, 0.5]],
                                  trading_cap=1000.0), 100, 0.01, 0.01, 100)
    assert rm.risk_pct(500) == 2.0 and rm.risk_pct(1000) == 1.0 and rm.risk_pct(9000) == 0.5
    assert rm.trading_equity(2500) == 1000.0
    # at $2,500 equity the bot risks 1% of the $1,000 cap = $10 -> 0.01 lot with a $10 stop
    assert rm.size_position(2500, 4000, 3990) == 0.01
    assert rm.size_position(2500, 4000, 3980) == 0.0
    assert RiskManager(RiskSettings(risk_ladder=[[0, 9.0]]), 100, 0.01, 0.01, 100).risk_pct(100) == 3.0  # ceiling


def test_engine_sweep_notification(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = Settings(starting_equity=10_000, financing_pct_per_year=0.0)
    s.risk = RiskSettings(trading_cap=9_000.0, sweep_min=50.0, max_trades_per_day=10)
    b = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    e = Engine(s, StrategyParams(adx_min=0), broker=b, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 600):
        b.feed = df.iloc[: i + 1]
        e.step()
    t = Journal(tmp_path).load_trades()
    sweeps = t[t.event == "sweep"]
    assert len(sweeps) >= 1 and float(sweeps.iloc[0]["pnl"]) >= 1000 - 1e-6
    assert "of 9000.00" in e.status()
    assert pd.notna(sweeps.iloc[0]["reason"])
