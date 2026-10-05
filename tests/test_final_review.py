"""Regression tests for the final independent review findings."""
import json
import logging
import types

from goldbot.brokers.paper import PaperBroker
from goldbot.config import Settings, StrategyParams
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine
from goldbot.journal import Journal
from goldbot.news import NewsAggregator
from goldbot.safety import InstanceLock, RedactingFormatter, redact
from goldbot.telegram_control import handle_command


def _engine(tmp_path, upto=1200):
    df = synthetic_ohlc(1400, seed=3)
    s = Settings(starting_equity=10_000)
    b = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    e = Engine(s, StrategyParams(adx_min=0), broker=b, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, upto):
        b.feed = df.iloc[: i + 1]
        e.step()
        if b.positions():
            break
    return e, b, s, df, i


def test_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("FINNHUB_KEY", "FINNSECRET123")
    msg = "ConnectionError with url: /bot123456789:AAHsecretsecretsecretsecret/sendMessage and /news?token=FINNSECRET123"
    out = redact(msg)
    assert "AAHsecret" not in out and "FINNSECRET123" not in out
    rec = logging.LogRecord("x", logging.ERROR, __file__, 1, msg, (), None)
    assert "FINNSECRET123" not in RedactingFormatter("%(message)s").format(rec)


def test_pause_survives_restart(tmp_path):
    e, b, s, df, i = _engine(tmp_path)
    handle_command(e, "/pause", "1", "1")
    e2 = Engine(s, StrategyParams(adx_min=0), broker=b, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    assert e2.paused


def test_offline_close_is_journaled(tmp_path):
    e, b, s, df, i = _engine(tmp_path)
    pid = b.positions()[0].id
    b.close(pid, reason="stop")                     # happens while the bot is down
    Engine(s, StrategyParams(adx_min=0), broker=b, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    t = Journal(tmp_path).load_trades()
    row = t[(t.event == "close") & (t.id == pid)]
    assert len(row) == 1 and "offline" in row.iloc[0]["reason"] and row.iloc[0]["pnl"] == row.iloc[0]["pnl"]


def test_close_all_reports_failures(tmp_path):
    e, b, s, df, i = _engine(tmp_path)
    b.close = lambda *a, **k: False
    assert e.close_all() == (0, 1)
    assert "KAPATILAMADI" in handle_command(e, "/closeall yes", "1", "1")


def test_group_member_is_not_owner(tmp_path):
    e, *_ = _engine(tmp_path, upto=420)
    assert handle_command(e, "/pause", "555", "1") is None          # sender id, not chat id
    assert not e.paused


def test_single_instance_lock(tmp_path):
    a, b = InstanceLock(tmp_path / "x.lock"), InstanceLock(tmp_path / "x.lock")
    assert a.acquire()
    assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_paper_financing_charged(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = Settings(starting_equity=10_000, financing_pct_per_year=50.0)
    b = PaperBroker(s, feed=df.iloc[:10], state_path=tmp_path / "p.json")
    b.set_last(2000.0)
    b.open(1, 1.0, 1900.0, 2200.0)
    before = b.cash
    b.charge_financing(df.index[0], df.index[24])
    assert b.cash < before


def test_ccxt_never_keeps_unprotected_position(tmp_path, monkeypatch):
    from goldbot.brokers import ccxt_broker
    monkeypatch.setattr("goldbot.config.ROOT", tmp_path)
    sold = []

    class FakeEx:
        def __init__(self):
            self.bal = {"PAXG": 5.0, "USDT": 1000.0}          # 5 PAXG = user's own core holding
        def create_market_buy_order(self, sym, q):
            self.bal["PAXG"] += q
            return {"average": 4000.0, "filled": q}
        def create_market_sell_order(self, sym, q):
            sold.append(q); self.bal["PAXG"] -= q
        def create_order(self, *a, **k):
            raise RuntimeError("stop orders not supported")
        def fetch_balance(self):
            return {"total": dict(self.bal)}
        def fetch_ticker(self, sym):
            return {"bid": 3999.0, "ask": 4001.0}
        def cancel_order(self, *a):
            pass

    br = object.__new__(ccxt_broker.CCXTBroker)
    br.ex, br.symbol = FakeEx(), "PAXG/USDT"
    br.s = types.SimpleNamespace(min_lot=0.0001, mode="paper")
    br._path = tmp_path / "pos.json"
    br.stops = {}
    assert br.positions() == []                       # own holding is NOT a bot position
    r = br.open(1, 0.5, 3900.0, 4200.0)
    assert not r.ok and sold == [0.5]                 # stop refused -> sold immediately
    assert br.positions() == [] and br.ex.bal["PAXG"] == 5.0

    br.ex.create_order = lambda *a, **k: {"id": "s1"}
    r = br.open(1, 0.5, 3900.0, 4200.0)
    assert r.ok and br.positions()[0].lots == 0.5     # only the bot's quantity
    assert json.loads(br._path.read_text())["spot"]["stop_id"] == "s1"
    assert br.close("spot") and sold[-1] == 0.5 and br.ex.bal["PAXG"] == 5.0


def test_holdout_restarts_after_acceptance(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    (tmp_path / "reports").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "validation.yaml").write_text((root / "config" / "validation.yaml").read_text())
    (tmp_path / "reports" / "self-improve-2026-12-20.json").write_text('{"date": "2026-12-20", "accepted": true}')
    (tmp_path / "reports" / "self-improve-2027-01-03.json").write_text('{"date": "2027-01-03", "accepted": false}')
    monkeypatch.setattr("goldbot.config.ROOT", tmp_path)
    spec = importlib.util.spec_from_file_location("si", root / "scripts" / "self_improve.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["si"] = mod
    spec.loader.exec_module(mod)
    assert str(mod.HOLDOUT_START.date()) == "2026-12-21"
