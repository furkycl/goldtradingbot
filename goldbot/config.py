"""Configuration loading.

Two files:
  config/settings.yaml  - human-owned: broker, mode, risk limits, news sources.
                          The self-improvement loop NEVER edits this file.
  config/params.yaml    - strategy parameters. The self-improvement loop may
                          propose changes to this file only, via pull request.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.yaml"
PARAMS_PATH = ROOT / "config" / "params.yaml"

LIVE_CONFIRM_PHRASE = "I UNDERSTAND I CAN LOSE ALL MY MONEY"


@dataclass
class RiskSettings:
    risk_per_trade_pct: float = 1.0      # % of equity lost if stop is hit
    max_daily_loss_pct: float = 3.0      # stop trading for the day after this
    max_drawdown_pct: float = 20.0       # kill switch from equity peak
    max_leverage: float = 10.0           # SPK cap for Turkish residents is 10:1
    max_open_positions: int = 1
    max_trades_per_day: int = 4


@dataclass
class StrategyParams:
    timeframe: str = "1h"
    ema_fast: int = 20
    ema_slow: int = 100
    breakout_lookback: int = 24
    atr_period: int = 14
    atr_stop_mult: float = 2.0
    take_profit_r: float = 2.0           # take profit at N x initial risk
    trail_atr_mult: float = 2.5          # trailing stop distance after 1R
    news_weight: float = 0.5             # how much news sentiment can veto/allow
    news_veto_threshold: float = 0.4     # |sentiment| above this vetoes opposite trades
    adx_period: int = 14
    adx_min: float = 18.0                # no trend trades in chop
    # research variants (0 / -1 = off). See docs/RESEARCH.md section 3.
    daily_trend_days: int = 0            # only trade in direction of N-day return (multi-timeframe)
    session_start_utc: int = -1          # allow new entries only between these UTC hours
    session_end_utc: int = -1
    max_hold_bars: int = 0               # exit trades not yet +0.5 ATR after N bars

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StrategyParams":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Settings:
    mode: str = "paper"                  # paper | live
    broker: str = "paper"                # paper | mt5 | ccxt
    symbol: str = "XAUUSD"
    starting_equity: float = 100.0
    commission_per_lot: float = 7.0      # round turn, USD per 100oz lot
    spread: float = 0.30                 # USD per oz, assumed for backtests
    financing_pct_per_year: float = 5.0  # overnight swap on CFD notional (conservative)
    contract_size: float = 100.0         # oz per lot
    min_lot: float = 0.01
    lot_step: float = 0.01
    long_only: bool = False              # spot tokenised gold (PAXG) cannot short
    poll_seconds: int = 30
    news_blackout_minutes: int = 30      # no new entries around high-impact events
    risk: RiskSettings = field(default_factory=RiskSettings)
    news: dict[str, Any] = field(default_factory=dict)
    broker_options: dict[str, Any] = field(default_factory=dict)

    @property
    def live_enabled(self) -> bool:
        """Live trading requires BOTH settings.mode == live AND an env confirmation.

        The env var must be set by the human operator on the machine that runs
        the bot. Nothing in this repo (including CI / self-improvement) sets it.
        """
        return (
            self.mode == "live"
            and os.environ.get("GOLDBOT_LIVE_CONFIRM", "") == LIVE_CONFIRM_PHRASE
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    raw = _read_yaml(path)
    risk = RiskSettings(**raw.pop("risk", {}))
    known = {k: v for k, v in raw.items() if k in Settings.__dataclass_fields__}
    s = Settings(**known, risk=risk)
    if s.risk.max_leverage > 10 and os.environ.get("GOLDBOT_ALLOW_HIGH_LEVERAGE") != "1":
        s.risk.max_leverage = 10.0
    return s


def load_params(path: Path = PARAMS_PATH) -> StrategyParams:
    return StrategyParams.from_dict(_read_yaml(path))


def save_params(params: StrategyParams, path: Path = PARAMS_PATH, header: str = "") -> None:
    text = yaml.safe_dump(params.to_dict(), sort_keys=False)
    with path.open("w", encoding="utf-8") as fh:
        if header:
            for line in header.splitlines():
                fh.write(f"# {line}\n")
        fh.write(text)
