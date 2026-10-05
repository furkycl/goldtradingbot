from goldbot.brokers.paper import PaperBroker
from goldbot.config import Settings, StrategyParams
from goldbot.core import core_signal
from goldbot.data import synthetic_ohlc
from goldbot.engine import Engine
from goldbot.forward import checklist, evaluate_journal, html_report, render_status
from goldbot.news import NewsAggregator


def test_forward_status_and_html(tmp_path):
    df = synthetic_ohlc(1400, seed=3)
    s = Settings(starting_equity=10_000)
    broker = PaperBroker(s, feed=df.iloc[:400], state_path=tmp_path / "p.json")
    eng = Engine(s, StrategyParams(adx_min=0), broker=broker, news=NewsAggregator(rss=[]), state_dir=tmp_path)
    for i in range(400, 1200):
        broker.feed = df.iloc[: i + 1]
        eng.step()
    m = evaluate_journal(tmp_path)
    assert m["trades"] > 3 and m["days"] > 20
    checks = checklist(m, {"min_trades": 1, "min_profit_factor": 0.0, "max_drawdown_pct": 100, "min_days": 1})
    assert all(ok for _, ok, _ in checks)
    assert "VERDICT: criteria met" in render_status(m, checks)
    strict = checklist(m)
    assert "do NOT go live" in render_status(m, strict)
    html = html_report(tmp_path).read_text()
    assert "<svg" in html and "Go-live checklist" in html and "prefers-color-scheme" in html


def test_empty_journal(tmp_path):
    m = evaluate_journal(tmp_path)
    assert m["trades"] == 0
    assert "no equity data yet" in html_report(tmp_path).read_text()


def test_core_signal():
    c = synthetic_ohlc(800, seed=1, freq="1D", vol=0.01, drift=0.001)["close"]
    out = core_signal(c)
    assert out["trend_6m_up"] in (True, False) and "advice" in out and out["vol_60d_pct"] > 0
