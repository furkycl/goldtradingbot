"""Configuration loading.

Two files:
  config/settings.yaml  - human-owned: broker, mode, risk limits, news sources.
                          The self-improvement loop NEVER edits this file.
  config/params.yaml    - strategy parameters. The self-improvement loop may
                          propose changes to this file only, via pull request.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.yaml"
PARAMS_PATH = ROOT / "config" / "params.yaml"

LIVE_CONFIRM_PHRASE = "I UNDERSTAND I CAN LOSE ALL MY MONEY"


def load_dotenv(path: Path | None = None) -> int:
    """Minimal .env loader (KEY=VALUE, # comments, optional quotes).
    Never overrides variables that are already set in the environment."""
    path = path or ROOT / ".env"
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and val and key not in os.environ:
            os.environ[key] = val
            n += 1
    return n


@dataclass
class RiskSettings:
    risk_per_trade_pct: float = 1.0      # % of equity lost if stop is hit
    max_daily_loss_pct: float = 3.0      # stop trading for the day after this
    max_drawdown_pct: float = 20.0       # kill switch from equity peak
    max_leverage: float = 10.0           # SPK cap for Turkish residents is 10:1
    max_open_positions: int = 1
    max_trades_per_day: int = 4
    # Refuse LIVE entries when round-trip cost exceeds this fraction of the
    # trade's risk (1R). Validation 2026-10-05: edge survives ~0.01R (MT5 CFD),
    # mostly gone at 0.10R (VIOP), negative at 0.20R+ (token spot).
    max_cost_in_r: float = 0.05


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
    # --- strategy library / ensemble (goldbot/strategies). Each family has its
    # own entry logic; exits, sizing and risk limits are shared. The selector
    # picks, per bar, the family with the best recent realised R (EWMA).
    strategies: list[str] = field(default_factory=lambda: ["breakout"])
    ensemble_lookback: int = 30          # trades of memory in the EWMA score
    ensemble_min_score: float = -0.3     # families scoring below this are benched
    squeeze_lookback: int = 100          # bars for the Bollinger-width percentile
    squeeze_pct: float = 0.25            # width must be in the lowest X of lookback
    spike_mult: float = 3.0              # bar range >= X * ATR = "news spike"
    spike_mode: str = "fade"             # fade | follow the spike (Smales 2015: overreaction)
    meanrev_bb: float = 2.0              # Bollinger sigma for mean reversion
    meanrev_adx_max: float = 18.0        # mean reversion only in non-trending regime
    overnight_start_utc: int = 22        # Asian-session long (Blose & Gondhalekar 2014)
    overnight_bars: int = 9              # hard exit after N bars (before London/NY)
    risk_vol_scaling: bool = False       # scale risk% by median ATR / current ATR (0.5-1.5x)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StrategyParams":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Settings:
    mode: str = "paper"                  # paper | demo | live
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
    def demo_enabled(self) -> bool:
        """Broker DEMO account (real spreads/execution, no real money). The broker
        adapter must verify the account really is a demo account."""
        return self.mode == "demo"

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
