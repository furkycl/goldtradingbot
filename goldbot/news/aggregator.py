"""Collects headlines from RSS feeds and Telegram channels, de-duplicates them,
scores them and exposes a rolling gold sentiment + high-impact event blackout."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from .sentiment import aggregate, is_relevant, score_headline

log = logging.getLogger(__name__)

# Public, free feeds — each verified to return a current RSS/Atom feed on
# 2026-10-04 (see docs/RESEARCH.md §4). Check yours with: python -m goldbot probe-feeds
DEFAULT_RSS = [
    "https://www.financialjuice.com/feed.ashx?xy=rss",          # fastest free squawk-style headlines
    "https://investinglive.com/feed/news",                      # ex-ForexLive, data prints at release
    "https://www.investing.com/rss/news_95.rss",                # economic indicators
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_11.rss",
    "https://www.federalreserve.gov/feeds/press_monetary.xml",  # FOMC statements
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.bls.gov/feed/cpi.rss",
    "https://www.bls.gov/feed/empsit.rss",                      # jobs report (NFP)
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://www.bloomberght.com/rss",
]
FF_CALENDAR = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


@dataclass
class NewsItem:
    ts: datetime
    source: str
    text: str
    score: float

    @property
    def key(self) -> str:
        return hashlib.sha1(self.text.lower().strip()[:200].encode()).hexdigest()


class NewsAggregator:
    def __init__(self, rss: list[str] | None = None, telegram: dict | None = None,
                 scorer: Callable[[str], float] = score_headline,
                 max_age_hours: float = 12, blackout_minutes: int = 30):
        self.rss = rss if rss is not None else DEFAULT_RSS
        self.telegram_cfg = telegram or {}
        self.scorer = scorer
        self.max_age = timedelta(hours=max_age_hours)
        self.blackout = timedelta(minutes=blackout_minutes)
        self.items: dict[str, NewsItem] = {}
        self.events: list[datetime] = []
        self._lock = threading.Lock()

    # ----------------------------------------------------------- ingestion
    def add(self, text: str, source: str, ts: datetime | None = None) -> NewsItem | None:
        text = " ".join(text.split())
        if not text or not is_relevant(text):
            return None
        item = NewsItem(ts or datetime.now(timezone.utc), source, text, self.scorer(text))
        with self._lock:
            if item.key in self.items:
                return None
            self.items[item.key] = item
        if abs(item.score) >= 0.3:
            log.info("news %+.2f [%s] %s", item.score, source, text[:140])
        return item

    def poll_rss(self) -> int:
        import feedparser

        n = 0
        for url in self.rss:
            try:
                feed = feedparser.parse(url)
            except Exception as exc:  # network errors must never kill the bot
                log.warning("rss %s failed: %s", url, exc)
                continue
            for e in feed.entries[:40]:
                ts = datetime.now(timezone.utc)
                if getattr(e, "published_parsed", None):
                    ts = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                title = getattr(e, "title", "")
                if self.add(title, url, ts):
                    n += 1
        return n

    def poll_finnhub(self) -> int:
        """Optional: Finnhub general news (free key, ~60 calls/min, non-commercial)."""
        import os
        import requests

        key = os.environ.get("FINNHUB_KEY")
        if not key:
            return 0
        try:
            rows = requests.get("https://finnhub.io/api/v1/news",
                                params={"category": "general", "token": key}, timeout=10).json()
        except Exception as exc:
            log.warning("finnhub failed: %s", exc)
            return 0
        n = 0
        for r in rows[:50]:
            ts = datetime.fromtimestamp(r.get("datetime", 0), tz=timezone.utc)
            if self.add(r.get("headline", ""), f"finnhub:{r.get('source', '')}", ts):
                n += 1
        return n

    def probe(self) -> list[tuple[str, str, str]]:
        """(url, status, newest entry age) for every configured feed."""
        import feedparser

        out = []
        now = datetime.now(timezone.utc)
        for url in self.rss:
            try:
                f = feedparser.parse(url)
            except Exception as exc:
                out.append((url, f"ERROR {exc}", "-")); continue
            dates = [datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                     for e in f.entries if getattr(e, "published_parsed", None)]
            if not f.entries:
                out.append((url, f"EMPTY (http {getattr(f, 'status', '?')})", "-"))
            else:
                age = now - max(dates) if dates else None
                out.append((url, "ok", f"{age.total_seconds() / 3600:.1f}h" if age else "no dates"))
        return out

    def poll_calendar(self) -> int:
        """High-impact USD events (CPI, NFP, FOMC...) -> entry blackout windows."""
        import requests

        try:
            rows = requests.get(FF_CALENDAR, timeout=10).json()
        except Exception as exc:
            log.warning("calendar fetch failed: %s", exc)
            return 0
        events = []
        for r in rows:
            if r.get("country") == "USD" and r.get("impact") == "High":
                try:
                    events.append(datetime.fromisoformat(r["date"]).astimezone(timezone.utc))
                except (KeyError, ValueError):
                    continue
        with self._lock:
            self.events = events
        return len(events)

    def start_telegram(self) -> None:
        """Listen to public Telegram channels in a background thread (Telethon).

        Needs TELEGRAM_API_ID / TELEGRAM_API_HASH from https://my.telegram.org.
        """
        if not self.telegram_cfg.get("channels"):
            return
        from .telegram_listener import run_listener

        threading.Thread(target=run_listener, args=(self, self.telegram_cfg),
                         daemon=True, name="telegram").start()

    # ------------------------------------------------------------- queries
    def prune(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            self.items = {k: v for k, v in self.items.items() if now - v.ts <= self.max_age}

    def sentiment(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            pts = [(i.ts, i.score) for i in self.items.values() if i.score != 0 and i.ts <= now]
        return aggregate(pts, now)

    def in_blackout(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            return any(abs(now - ev) <= self.blackout for ev in self.events)

    def run_forever(self, every_s: int = 60, stop: threading.Event | None = None) -> None:
        stop = stop or threading.Event()
        last_cal = 0.0
        while not stop.is_set():
            self.poll_rss()
            self.poll_finnhub()
            if time.time() - last_cal > 3600:
                self.poll_calendar()
                last_cal = time.time()
            self.prune()
            stop.wait(every_s)
