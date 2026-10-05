"""Telegram channel listener (Telethon user-API client, read-only).

Telegram bots cannot read channels they are not admin of, so this uses a user
session. It only READS messages from the channels listed in settings.yaml.

Env: TELEGRAM_API_ID, TELEGRAM_API_HASH (from https://my.telegram.org).
Log in ONCE interactively with `python -m goldbot telegram-login` (asks for your
phone number + code). The session is stored in state/telegram/ (never commit it;
it is in .gitignore). The bot then reuses it without a console (Docker/systemd).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
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
    session = _session_path(cfg)
    if not Path(str(session) + ".session").exists():
        log.error("no Telegram session: run `python -m goldbot telegram-login` once; telegram news disabled")
        return
    client = TelegramClient(str(session), int(api_id), api_hash, loop=loop)

    @client.on(events.NewMessage(chats=channels))
    async def handler(event):  # noqa: ANN001
        text = event.raw_text or ""
        chat = getattr(event.chat, "username", None) or str(event.chat_id)
        agg.add(text.split("\n")[0][:300], f"telegram:{chat}", event.date)

    log.info("telegram listening to %s", channels)
    loop.run_until_complete(client.connect())
    if not loop.run_until_complete(client.is_user_authorized()):
        log.error("Telegram session expired: run `python -m goldbot telegram-login`")
        return
    client.run_until_disconnected()


def _session_path(cfg: dict) -> Path:
    from ..config import ROOT
    d = ROOT / "state" / "telegram"
    d.mkdir(parents=True, exist_ok=True)
    return d / cfg.get("session", "goldbot")


def interactive_login(cfg: dict) -> None:
    from telethon.sync import TelegramClient

    api_id, api_hash = os.environ.get("TELEGRAM_API_ID"), os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        raise SystemExit("set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env first (https://my.telegram.org)")
    with TelegramClient(str(_session_path(cfg)), int(api_id), api_hash) as client:
        me = client.get_me()
        print(f"logged in as {getattr(me, 'username', None) or me.id}; session saved in state/telegram/")
