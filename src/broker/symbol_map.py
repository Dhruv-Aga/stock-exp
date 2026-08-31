"""Map strategy symbols to Zerodha tradable instruments."""

from __future__ import annotations

from config import MARKETS, MarketConfig


def get_market(symbol: str) -> MarketConfig | None:
    for m in MARKETS:
        if m.symbol == symbol:
            return m
    return None


def kite_tradingsymbol(symbol: str) -> str:
    market = get_market(symbol)
    if not market:
        raise KeyError(f"No market config for {symbol}")
    return market.kite_symbol


def kite_exchange(symbol: str) -> str:
    market = get_market(symbol)
    if not market:
        raise KeyError(f"No market config for {symbol}")
    return market.kite_exchange


def kite_product(symbol: str) -> str:
    market = get_market(symbol)
    if not market:
        raise KeyError(f"No market config for {symbol}")
    return market.kite_product


def can_trade_side(symbol: str, side: int, *, cash_only: bool) -> bool:
    """Return False if side is not allowed (e.g. short in cash-only mode)."""
    if side == 0:
        return False
    market = get_market(symbol)
    if not market:
        return False
    if side == -1 and cash_only and not market.allow_short:
        return False
    return True


def round_quantity(symbol: str, qty: float) -> int:
    """Zerodha equity quantities are whole shares."""
    market = get_market(symbol)
    if market and market.kite_product == "CNC":
        return max(1, int(qty))
    return max(1, int(qty))
