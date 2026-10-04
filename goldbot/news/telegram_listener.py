"""Telegram channel listener (Telethon user-API client, read-only).

Telegram bots cannot read channels they are not admin of, so this uses a user
session. It only READS messages from the channels listed in settings.yaml.

Env: TELEGRAM_API_ID, TELEGRAM_API_HASH (from https://my.telegram.org).
First run asks for your phone number + login code once and stores a session
file locally (goldbot.session — never commit it; it is in .gitignore).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .aggregator import NewsAggregator

log = logging.getLogger(__name__)


def run_listener(agg: "NewsAggregator", cfg: dict) -> None:
    try:
        from telethon import TelegramClient, events
    except ImportError:
        log.error("telethon not installed: pip install telethon")
        return

    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        log.error("TELEGRAM_API_ID / TELEGRAM_API_HASH not set; telegram disabled")
        return

    channels = cfg.get("channels", [])
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(cfg.get("session", "goldbot"), int(api_id), api_hash, loop=loop)

    @client.on(events.NewMessage(chats=channels))
    async def handler(event):  # noqa: ANN001
        text = event.raw_text or ""
        chat = getattr(event.chat, "username", None) or str(event.chat_id)
        agg.add(text.split("\n")[0][:300], f"telegram:{chat}", event.date)

    log.info("telegram listening to %s", channels)
    client.start()
    client.run_until_disconnected()
