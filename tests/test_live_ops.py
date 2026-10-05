"""Live-operation safety: state survives restarts, journal is written."""
from datetime import date, datetime, timezone

from goldbot.brokers.paper import PaperBroker
from goldbot.config import RiskSettings, Settings, StrategyParams
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine, market_open
from goldbot.journal import Journal
from goldbot.news import NewsAggregator
from goldbot.risk import RiskManager


def _settings(**kw):
    s = Settings(starting_equity=10_000)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_kill_switch_survives_restart(tmp_path):
    path = tmp_path / "risk.json"
    rm = RiskManager(RiskSettings(max_drawdown_pct=10), 100, 0.01, 0.01, 1000)
    rm.attach(path)
    rm.on_new_bar(date(2026, 1, 5), 1000)
    rm.on_new_bar(date(2026, 1, 6), 880)
    assert "drawdown" in rm.state.halted_reason
    rm2 = RiskManager(RiskSettings(max_drawdown_pct=10), 100, 0.01, 0.01, 880)   # "restart"
    rm2.attach(path)
    assert not rm2.can_trade(0)[0]
    assert rm2.state.peak_equity == 1000
    rm2.reset_halt(880)
    assert rm2.can_trade(0)[0]
    rm3 = RiskManager(RiskSettings(max_drawdown_pct=10), 100, 0.01, 0.01, 880)
    rm3.attach(path)
    assert rm3.can_trade(0)[0] and rm3.state.peak_equity == 880


def test_daily_counter_survives_restart(tmp_path):
    path = tmp_path / "risk.json"
    rm = RiskManager(RiskSettings(max_trades_per_day=2), 100, 0.01, 0.01, 1000)
    rm.attach(path)
    rm.on_new_bar(date(2026, 1, 5), 1000)
    rm.on_trade_opened(); rm.on_trade_opened()
    rm2 = RiskManager(RiskSettings(max_trades_per_day=2), 100, 0.01, 0.01, 1000)
    rm2.attach(path)
    rm2.on_new_bar(date(2026, 1, 5), 1000)
    assert not rm2.can_trade(0)[0]


def test_engine_writes_journal_and_equity(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = _settings()
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, StrategyParams(adx_min=0), broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 1200):
        broker.feed = df.iloc[: i + 1]
        eng.step()
    j = Journal(tmp_path)
    t = j.load_trades()
    opens, closes = t[t.event == "open"], t[t.event == "close"]
    assert len(opens) > 3 and len(closes) >= len(opens) - 1
    assert closes["pnl"].notna().all()
    assert abs(closes["pnl"].sum() - sum(c["pnl"] for c in broker.closed)) < 1e-6
    assert len(j.load_equity()) > 700
    assert "equity" in eng.status()


def test_close_all_and_pause(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = _settings()
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, StrategyParams(adx_min=0), broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 1200):
        broker.feed = df.iloc[: i + 1]
        eng.step()
        if broker.positions():
            break
    assert broker.positions()
    assert eng.close_all() == (1, 0) and not broker.positions()
    eng.paused = True
    msgs = []
    for j in range(i + 1, i + 300):
        broker.feed = df.iloc[: j + 1]
        msgs.append(eng.step())
    assert not broker.positions()
    assert any("paused" in m for m in msgs)


def test_market_hours():
    assert not market_open(datetime(2026, 10, 3, 12, tzinfo=timezone.utc))   # Saturday
    assert not market_open(datetime(2026, 10, 4, 20, tzinfo=timezone.utc))   # Sunday before open
    assert market_open(datetime(2026, 10, 4, 23, tzinfo=timezone.utc))      # Sunday after open
    assert market_open(datetime(2026, 10, 5, 13, tzinfo=timezone.utc))      # Monday
    assert not market_open(datetime(2026, 10, 9, 21, 30, tzinfo=timezone.utc))  # Friday close


def test_dotenv_loader(tmp_path, monkeypatch):
    import os

    from goldbot.config import load_dotenv
    f = tmp_path / ".env"
    f.write_text('# c\nGB_A=1\nexport GB_B="two words"\nGB_C=\nGB_D=keep\nnot a line\n')
    monkeypatch.delenv("GB_A", raising=False); monkeypatch.delenv("GB_B", raising=False)
    monkeypatch.setenv("GB_D", "env-wins")
    assert load_dotenv(f) == 2
    assert os.environ["GB_A"] == "1" and os.environ["GB_B"] == "two words"
    assert os.environ["GB_D"] == "env-wins" and "GB_C" not in os.environ
    monkeypatch.delenv("GB_A"); monkeypatch.delenv("GB_B")
