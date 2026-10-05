from goldbot.brokers.paper import PaperBroker
from goldbot.config import Settings, StrategyParams
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine
from goldbot.news import NewsAggregator
from goldbot.telegram_control import handle_command


def _engine(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = Settings(starting_equity=10_000)
    b = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    e = Engine(s, StrategyParams(adx_min=0), broker=b, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 1200):
        b.feed = df.iloc[: i + 1]
        e.step()
        if b.positions():
            break
    return e, b


def test_only_owner_is_obeyed(tmp_path):
    e, _ = _engine(tmp_path)
    assert handle_command(e, "/pause", "999", "123") is None
    assert not e.paused
    assert handle_command(e, "/pause", "123", "") is None        # no owner configured -> nothing
    assert handle_command(e, "/pause", 123, "123")
    assert e.paused
    handle_command(e, "/resume", "123", "123")
    assert not e.paused


def test_closeall_needs_confirmation(tmp_path):
    e, b = _engine(tmp_path)
    assert b.positions()
    assert "emin misin" in handle_command(e, "/closeall", "1", "1")
    assert b.positions()
    assert "1 pozisyon" in handle_command(e, "/closeall yes", "1", "1")
    assert not b.positions()


def test_status_and_forward(tmp_path):
    e, _ = _engine(tmp_path)
    assert "equity" in handle_command(e, "/status@goldbot", "1", "1")
    assert "Go-live checklist" in handle_command(e, "/forward", "1", "1")
    assert "/pause" in handle_command(e, "/help", "1", "1")
    assert "bilinmeyen" in handle_command(e, "/setrisk 50", "1", "1")
