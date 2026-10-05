from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from goldbot.backtest import run_backtest
from goldbot.brokers import make_broker
from goldbot.brokers.paper import PaperBroker
from goldbot.config import LIVE_CONFIRM_PHRASE, RiskSettings, Settings, StrategyParams, load_params, load_settings
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine
from goldbot.news import NewsAggregator, aggregate, score_headline
from goldbot.optimize import evaluate, folds, passes_guardrails
from goldbot.risk import RiskManager
from goldbot.strategy import prepare, signal_at


@pytest.fixture
def df():
    return synthetic_ohlc(3000, seed=3)


def big_settings(**kw):
    s = Settings(starting_equity=10_000)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


# ---------------------------------------------------------------- config
def test_shipped_config_is_paper():
    s = load_settings()
    assert s.mode == "paper" and s.broker == "paper"
    assert not s.live_enabled
    load_params()


def test_live_needs_env_confirmation(monkeypatch):
    s = Settings(mode="live", broker="mt5")
    monkeypatch.delenv("GOLDBOT_LIVE_CONFIRM", raising=False)
    assert not s.live_enabled
    assert isinstance(make_broker(s), PaperBroker)  # falls back to paper
    monkeypatch.setenv("GOLDBOT_LIVE_CONFIRM", LIVE_CONFIRM_PHRASE)
    assert s.live_enabled


# ------------------------------------------------------------------ risk
def test_position_size_respects_risk_and_leverage():
    rm = RiskManager(RiskSettings(risk_per_trade_pct=1, max_leverage=10), 100, 0.01, 0.01, 10_000)
    lots = rm.size_position(10_000, 2000, 1990)        # $10/oz stop -> $100 risk -> 0.1 lot
    assert lots == pytest.approx(0.10)
    lots = rm.size_position(10_000, 2000, 1999.9)      # tiny stop -> leverage cap 0.5 lot
    assert lots * 100 * 2000 <= 10 * 10_000 + 1e-6


def test_small_account_refuses_oversized_lot():
    rm = RiskManager(RiskSettings(), 100, 0.01, 0.01, 100)
    assert rm.size_position(100, 3000, 2980) == 0.0     # 0.01 lot would risk 20%


def test_daily_loss_and_drawdown_halt():
    rm = RiskManager(RiskSettings(max_daily_loss_pct=3, max_drawdown_pct=10), 100, 0.01, 0.01, 1000)
    d = datetime(2026, 1, 5).date()
    rm.on_new_bar(d, 1000)
    rm.on_new_bar(d, 965)
    assert not rm.can_trade(0)[0]
    rm.on_new_bar(d + timedelta(days=1), 965)           # new day resets daily halt
    assert rm.can_trade(0)[0]
    rm.on_new_bar(d + timedelta(days=2), 890)
    rm.on_new_bar(d + timedelta(days=3), 900)
    ok, why = rm.can_trade(0)
    assert not ok and "drawdown" in why                  # permanent


# -------------------------------------------------------------- strategy
def test_no_lookahead_in_signals(df):
    p = StrategyParams()
    full = prepare(df, p)
    cut = prepare(df.iloc[:2000], p)
    for col in ("ema_fast", "atr", "dc_up", "adx"):
        assert full[col].iloc[1999] == pytest.approx(cut[col].iloc[1999])


def test_news_veto(df):
    p = StrategyParams(adx_min=0)
    data = prepare(df, p)
    row = next(data.iloc[i] for i in range(300, len(data))
               if signal_at(data.iloc[i], p).side == 1)
    assert signal_at(row, p, news_sentiment=-0.9).side == 0
    assert signal_at(row, p, news_sentiment=+0.9).side == 1


def test_every_signal_has_stop(df):
    p = StrategyParams(adx_min=0)
    data = prepare(df, p)
    for i in range(300, len(data), 7):
        s = signal_at(data.iloc[i], p)
        if s.side:
            assert s.stop and (s.entry_ref - s.stop) * s.side > 0


# -------------------------------------------------------------- backtest
def test_backtest_runs_and_charges_costs(df):
    s = big_settings()
    r = run_backtest(df, s, StrategyParams())
    assert r.stats["trades"] > 0
    free = run_backtest(df, big_settings(spread=0.0, commission_per_lot=0.0), StrategyParams())
    assert r.equity.iloc[-1] < free.equity.iloc[-1]
    for t in r.trades:
        assert t.stop and t.lots > 0


def test_backtest_100_dollar_account_reports_skips(df):
    r = run_backtest(df, Settings(starting_equity=100), StrategyParams())
    assert r.stats["trades"] == 0 and r.skipped_min_lot > 0


# -------------------------------------------------------------- optimize
def test_walk_forward_folds_are_out_of_sample(df):
    for train, test, oos_start in folds(df, 4):
        assert test.index[0] < oos_start <= test.index[-1]
        assert train.index[-1] < test.index[-1]
        assert len(test) > 0


def test_guardrails(df):
    ev = evaluate(df, big_settings(), StrategyParams())
    ok, _ = passes_guardrails({**ev, "worst_dd": 99})
    assert not ok


# ------------------------------------------------------------------ news
def test_sentiment_direction():
    assert score_headline("Fed signals rate cuts as dollar weakens") > 0.5
    assert score_headline("Hawkish Fed: Treasury yields surge, dollar rallies") < -0.5
    assert score_headline("Gold rises to record high on safe-haven demand") > 0
    assert score_headline("Altın düştü, Fed faiz artırımı sinyali verdi") < 0
    assert score_headline("Local football results") == 0


def test_sentiment_time_decay():
    now = datetime.now(timezone.utc)
    s = aggregate([(now, 1.0), (now - timedelta(hours=10), -1.0)], now)
    assert s > 0.9


def test_aggregator_dedup_and_blackout():
    agg = NewsAggregator(rss=[], blackout_minutes=30)
    assert agg.add("Gold surges as dollar weakens", "x")
    assert agg.add("Gold surges as dollar weakens", "y") is None
    now = datetime.now(timezone.utc)
    agg.events = [now + timedelta(minutes=10)]
    assert agg.in_blackout(now)
    assert not agg.in_blackout(now + timedelta(hours=2))


# ---------------------------------------------------------------- engine
def test_engine_paper_end_to_end(df, tmp_path):
    s = big_settings()
    p = StrategyParams(adx_min=0)
    feed = df.iloc[:400]
    broker = PaperBroker(s, feed=feed, state_path=tmp_path / "p.json")
    eng = Engine(s, p, broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    opened = 0
    for i in range(400, 1400):
        broker.feed = df.iloc[: i + 1]
        if eng.step() == "opened":
            opened += 1
            assert all(pos.stop for pos in broker.positions())
    assert opened > 0
    assert len(broker.closed) > 0


def test_small_account_paxg_profile_trades_long_only(df):
    from goldbot.config import ROOT
    s = load_settings(ROOT / "config" / "profiles" / "small_account_paxg.yaml")
    assert s.long_only and s.risk.max_leverage == 1.0 and s.mode == "paper"
    r = run_backtest(df, s, StrategyParams())
    assert r.stats["trades"] > 0
    assert all(t.side == 1 for t in r.trades)
    for t in r.trades:  # notional never exceeds equity (no leverage)
        assert t.lots * t.entry <= s.starting_equity * 3


# ------------------------------------------------------- research variants
def test_daily_trend_has_no_lookahead(df):
    from goldbot.strategy import daily_trend
    full = daily_trend(df["close"], 20)
    cut = daily_trend(df["close"].iloc[:1500], 20)
    assert (full.iloc[:1500] == cut).all()
    # value used during day D must not depend on any bar of day D
    day = df.index[1000].normalize()
    same_day = full[df.index.normalize() == day]
    assert same_day.nunique() == 1


def test_session_filter():
    import pandas as pd

    from goldbot.strategy import in_session
    p = StrategyParams(session_start_utc=7, session_end_utc=17)
    assert in_session(pd.Timestamp("2026-01-05 08:00", tz="UTC"), p)
    assert not in_session(pd.Timestamp("2026-01-05 21:00", tz="UTC"), p)
    assert in_session(pd.Timestamp("2026-01-05 03:00-05:00"), p)  # = 08:00 UTC
    wrap = StrategyParams(session_start_utc=22, session_end_utc=3)
    assert in_session(pd.Timestamp("2026-01-05 23:00", tz="UTC"), wrap)


def test_variants_only_restrict_trades(df):
    base = run_backtest(df, big_settings(), StrategyParams()).stats["trades"]
    for kw in ({"daily_trend_days": 20}, {"session_start_utc": 7, "session_end_utc": 17}):
        assert run_backtest(df, big_settings(), StrategyParams(**kw)).stats["trades"] <= base


def test_time_stop_exits(df):
    r = run_backtest(df, big_settings(), StrategyParams(max_hold_bars=6))
    assert any(t.reason == "time_stop" for t in r.trades)


def test_engine_time_stop_matches_backtest_rule(df, tmp_path):
    s = big_settings()
    p = StrategyParams(adx_min=0, max_hold_bars=6)
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, p, broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 1400):
        broker.feed = df.iloc[: i + 1]
        eng.step()
    assert any(c["reason"] == "manual" for c in broker.closed)  # engine-initiated time-stop closes
    assert all(pos.opened_at for pos in broker.positions())


def _replay(df, s, p, tmp_path, start=400, end=1400):
    """Replay where the last row is the bar still FORMING (only its open is known),
    exactly like MT5 / ccxt / yfinance return candles live."""
    broker = PaperBroker(s, feed=df.iloc[:start], state_path=tmp_path / "p.json")
    eng = Engine(s, p, broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(start, end):
        feed = df.iloc[: i + 1].copy()
        o = feed["open"].iloc[-1]
        feed.iloc[-1, feed.columns.get_indexer(["high", "low", "close"])] = o
        broker.feed = feed
        eng.step()
    return broker


def test_engine_entries_match_backtest(df, tmp_path):
    s = big_settings(financing_pct_per_year=0.0)
    p = StrategyParams(adx_min=0, max_hold_bars=12)
    broker = _replay(df, s, p, tmp_path)
    bt = run_backtest(df.iloc[:1400], s, p, trade_from=df.index[400])
    eng_entries = [pd.Timestamp(c["opened_at"]) for c in broker.closed]
    bt_entries = [t.entry_time for t in bt.trades if t.entry_time < df.index[1390]]
    n = min(len(eng_entries), len(bt_entries), 10)
    assert n >= 5
    assert eng_entries[:n] == bt_entries[:n]
    for c, t in zip(broker.closed[:n], bt.trades[:n]):
        assert c["reason"].replace("manual", "time_stop") == t.reason
        assert abs(c["entry"] - t.entry) < 1e-6
        assert abs(c["pnl"] - t.pnl) < 0.05          # same exits, incl. time stops (to the cent)


# ------------------------------------------------------------- audit fixes
def test_trade_from_blocks_warmup_trades(df):
    start = df.index[1500]
    r = run_backtest(df, big_settings(), StrategyParams(adx_min=0), trade_from=start)
    assert r.trades and all(t.entry_time > start for t in r.trades)
    assert r.equity.index[0] <= start and r.equity.iloc[0] == 10_000


def test_financing_costs_money(df):
    a = run_backtest(df, big_settings(financing_pct_per_year=0.0), StrategyParams()).equity.iloc[-1]
    b = run_backtest(df, big_settings(financing_pct_per_year=5.0), StrategyParams()).equity.iloc[-1]
    assert b < a


def test_random_entry_hook(df):
    import numpy as np
    rng = np.random.default_rng(0)
    r = run_backtest(df, big_settings(), StrategyParams(),
                     entry_fn=lambda i, ts: (1 if rng.random() < 0.5 else -1) if rng.random() < 0.05 else 0)
    assert r.stats["trades"] > 20 and all(t.stop for t in r.trades)


def test_optimizer_requires_paired_fold_wins():
    from goldbot.optimize import clearly_better
    base = {"median_score": 1.0, "total_return_pct": 10, "folds": [{"return_pct": x} for x in (1, 2, 3, 4)]}
    cand = {"median_score": 2.0, "total_return_pct": 20, "folds": [{"return_pct": x} for x in (9, 9, 0, 0)]}
    assert not clearly_better(cand, base)[0]          # big score jump but wins only 2/4 folds
    cand["folds"] = [{"return_pct": x} for x in (2, 3, 4, 5)]
    assert clearly_better(cand, base)[0]


def test_daily_strategies_no_lookahead():
    from goldbot import daily as D
    from goldbot.data import synthetic_ohlc
    d = synthetic_ohlc(1500, seed=2, freq="1D", vol=0.01)
    c = d["close"]
    t = d.iloc[:900]
    pairs = [(D.tsmom(c, 63), D.tsmom(t["close"], 63)),
             (D.sma_filter(c, 50), D.sma_filter(t["close"], 50)),
             (D.donchian_daily(c, d["high"], d["low"], 20, 10),
              D.donchian_daily(t["close"], t["high"], t["low"], 20, 10))]
    for full, part in pairs:   # truncating the future must not change past positions
        assert (full.iloc[:900] == part).all()
    r = D.returns_from_positions(c, D.buy_hold(c), cost_bps=0, financing_pct=0)
    assert abs((1 + r).prod() - c.iloc[-1] / c.iloc[0]) < 1e-9


def test_cost_guard_blocks_expensive_venue(df, tmp_path):
    s = big_settings(mode="demo", commission_per_lot=5000.0)   # ~token-exchange fees
    p = StrategyParams(adx_min=0)
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, p, broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    msgs = []
    for i in range(400, 900):
        broker.feed = df.iloc[: i + 1]
        msgs.append(eng.step())
    assert any("too expensive" in m for m in msgs)
    assert not broker.closed and not broker.positions()


def test_cost_guard_off_in_paper_mode(df, tmp_path):
    s = big_settings(commission_per_lot=5000.0)                 # paper: research allowed
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, StrategyParams(adx_min=0), broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 900):
        broker.feed = df.iloc[: i + 1]
        eng.step()
    assert broker.closed or broker.positions()
