"""Operational safety helpers: secret redaction and a single-instance lock."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

SECRET_ENV = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_API_HASH", "FINNHUB_KEY", "MT5_PASSWORD",
              "CCXT_API_KEY", "CCXT_SECRET")
_PATTERNS = [re.compile(r"bot\d{5,}:[A-Za-z0-9_-]{20,}"),
             re.compile(r"(?i)(token|apikey|api_key|secret|password)=([^&\s'\"]+)")]


def redact(text: str) -> str:
    """Remove known secrets (env values, Telegram bot tokens, ?token=...) from text."""
    if not text:
        return text
    for name in SECRET_ENV:
        val = os.environ.get(name)
        if val and len(val) >= 4:
            text = text.replace(val, "***")
    text = _PATTERNS[0].sub("bot***", text)
    return _PATTERNS[1].sub(lambda m: f"{m.group(1)}=***", text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def install_redaction() -> None:
    """Make every handler on the root logger redact secrets (incl. tracebacks)."""
    root = logging.getLogger()
    for h in root.handlers:
        fmt = h.formatter._fmt if h.formatter else "%(asctime)s %(levelname)s %(name)s: %(message)s"
        h.setFormatter(RedactingFormatter(fmt))


class InstanceLock:
    """Exclusive, OS-level lock on state/<mode>/goldbot.lock. Released automatically
    if the process dies, so a crash never leaves a stale lock."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            self._fh = None
            return False
        self._fh.seek(0); self._fh.truncate(); self._fh.write(str(os.getpid())); self._fh.flush()
        return True

    def release(self) -> None:
        if self._fh:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None
