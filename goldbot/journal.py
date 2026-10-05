"""Append-only CSV records of what the bot did, used by `status` and `report`.

state/journal.csv : one row per trade event (open / close / note)
state/equity.csv  : one row per closed bar (time, equity)
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FIELDS = ["time", "event", "id", "side", "lots", "price", "stop", "take_profit", "pnl", "reason", "equity", "mode"]


class Journal:
    def __init__(self, folder: Path, mode: str = "paper"):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.trades = self.folder / "journal.csv"
        self.eq = self.folder / "equity.csv"
        self.mode = mode

    def _append(self, path: Path, fields: list[str], row: dict) -> None:
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in fields})

    def event(self, event: str, **kw) -> None:
        kw.setdefault("time", datetime.now(timezone.utc).isoformat())
        kw["event"], kw["mode"] = event, self.mode
        self._append(self.trades, FIELDS, kw)

    def equity(self, ts, equity: float) -> None:
        self._append(self.eq, ["time", "equity"], {"time": pd.Timestamp(ts).isoformat(), "equity": round(equity, 2)})

    # ---------------------------------------------------------------- reading
    def load_trades(self) -> pd.DataFrame:
        if not self.trades.exists():
            return pd.DataFrame(columns=FIELDS)
        return pd.read_csv(self.trades)

    def load_equity(self) -> pd.Series:
        if not self.eq.exists():
            return pd.Series(dtype=float)
        df = pd.read_csv(self.eq, parse_dates=["time"])
        return df.drop_duplicates("time", keep="last").set_index("time")["equity"]
