"""Remote control via YOUR Telegram bot (the same one used for notifications).

Only messages from TELEGRAM_CHAT_ID are obeyed; everything else is ignored.
Commands:
  /status            equity, positions, halt state, today's trades
  /forward           forward-test results vs the go-live checklist
  /pause             stop opening NEW trades (open ones keep their SL/TP)
  /resume            allow new trades again
  /closeall yes      close every open position now (needs the word 'yes')
  /help
There is deliberately no command to change risk, mode or to reset the kill
switch: those require a human at the machine (python -m goldbot reset-halt).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Engine

log = logging.getLogger("goldbot.telegram_control")

HELP = ("/status – durum\n/forward – ileriye dönük test ve canlıya geçiş listesi\n"
        "/pause – yeni işlem açma\n/resume – devam\n/closeall yes – tüm pozisyonları kapat\n/help")


def handle_command(engine: "Engine", text: str, sender_id: str, owner_id: str) -> str | None:
    """`sender_id` must be the SENDER's user id (message.from.id), so in a group
    only the owner is obeyed."""
    if not owner_id or str(sender_id) != str(owner_id):
        return None                                   # ignore strangers silently
    parts = (text or "").strip().split()
    if not parts:
        return None
    cmd = parts[0].split("@")[0].lower()
    with engine.lock:
        if cmd == "/status":
            return engine.status()
        if cmd == "/forward":
            from .forward import checklist, evaluate_journal, render_status
            m = evaluate_journal(engine.state_dir)
            return render_status(m, checklist(m))
        if cmd == "/pause":
            engine.set_paused(True)
            return "⏸ yeni işlem açma durduruldu (açık pozisyonlar SL/TP ile korunuyor)"
        if cmd == "/resume":
            engine.set_paused(False)
            return "▶️ devam ediliyor"
        if cmd == "/closeall":
            if len(parts) < 2 or parts[1].lower() != "yes":
                return "emin misin? göndermek için: /closeall yes"
            n, failed = engine.close_all("telegram /closeall")
            return f"{n} pozisyon kapatıldı" + (f", ⚠️ {failed} KAPATILAMADI — brokeri kontrol et" if failed else "")
        if cmd in ("/help", "/start"):
            return HELP
    return "bilinmeyen komut. /help"


def _poll(engine: "Engine", token: str, owner: str) -> None:
    import time

    import requests

    url = f"https://api.telegram.org/bot{token}"
    started = time.time()
    offset = None
    try:   # drop the backlog: commands sent while the bot was down must NOT run now
        last = requests.get(f"{url}/getUpdates", params={"offset": -1}, timeout=15).json().get("result", [])
        offset = last[-1]["update_id"] + 1 if last else None
    except Exception as exc:
        log.warning("telegram backlog skip failed: %s", type(exc).__name__)
    while not engine.stop_evt.is_set():
        try:
            r = requests.get(f"{url}/getUpdates", params={"timeout": 25, "offset": offset}, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                if msg.get("date", 0) < started:
                    continue
                reply = handle_command(engine, msg.get("text", ""), (msg.get("from") or {}).get("id"), owner)
                if reply:
                    requests.post(f"{url}/sendMessage", json={"chat_id": owner, "text": reply[:4000]}, timeout=10)
        except Exception as exc:
            log.warning("telegram poll failed: %s", type(exc).__name__)   # never log the URL (token)
            engine.stop_evt.wait(10)


def start_control(engine: "Engine") -> bool:
    token, owner = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not owner:
        return False
    threading.Thread(target=_poll, args=(engine, token, owner), daemon=True, name="tg-control").start()
    log.info("telegram remote control active for chat %s", owner)
    return True
