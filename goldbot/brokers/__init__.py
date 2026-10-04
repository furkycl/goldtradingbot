from .base import Broker, Position, OrderResult
from .paper import PaperBroker


def make_broker(settings) -> Broker:
    """Live brokers are only constructed when settings.live_enabled is True."""
    name = settings.broker
    if name == "paper" or not settings.live_enabled:
        return PaperBroker(settings)
    if name == "mt5":
        from .mt5 import MT5Broker
        return MT5Broker(settings)
    if name == "ccxt":
        from .ccxt_broker import CCXTBroker
        return CCXTBroker(settings)
    raise ValueError(f"unknown broker {name!r}")


__all__ = ["Broker", "Position", "OrderResult", "PaperBroker", "make_broker"]
