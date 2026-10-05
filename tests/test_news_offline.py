from datetime import datetime, timezone
from pathlib import Path

from goldbot.news import NewsAggregator

FEED = str(Path(__file__).parent / "fixtures" / "feed.xml")


def test_rss_parsing_relevance_dedup():
    agg = NewsAggregator(rss=[FEED])
    assert agg.poll_rss() == 2                      # football dropped, duplicate dropped
    scores = sorted(i.score for i in agg.items.values())
    assert scores[0] < 0 < scores[1]
    assert all(i.ts.tzinfo is not None for i in agg.items.values())


def test_probe_reports_fixture_ok():
    (url, status, age), = NewsAggregator(rss=[FEED]).probe()
    assert status == "ok" and age.endswith("h")


def test_sentiment_window():
    agg = NewsAggregator(rss=[FEED])
    agg.poll_rss()
    s = agg.sentiment(datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc))
    assert -1 <= s <= 1
    assert agg.sentiment(datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)) == 0.0   # nothing known yet
