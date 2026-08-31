"""Position sizing, stop loss, and correlation filter."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import CORRELATION_GROUPS, INITIAL_CAPITAL, RISK_PER_TRADE


@dataclass
class Position:
    symbol: str
    side: int  # 1 long, -1 short
    entry_price: float
    quantity: float
    stop_price: float
    group: str
    entry_time: object = None
    entry_reason: str = ""


@dataclass
class Portfolio:
    cash: float = INITIAL_CAPITAL
    positions: dict[str, Position] = field(default_factory=dict)
    equity_curve: list[tuple] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)


def calc_position_size(
    equity: float,
    entry_price: float,
    atr: float,
    *,
    risk_pct: float = RISK_PER_TRADE,
) -> float:
    """Size so a 1 ATR move against us ~= risk_pct of equity."""
    if atr <= 0 or entry_price <= 0:
        return 0.0
    risk_amount = equity * risk_pct
    # Stop at 1 ATR from entry (maps to ~1% portfolio risk)
    qty = risk_amount / atr
    max_qty = (equity * 0.25) / entry_price  # cap at 25% notional per trade
    return min(qty, max_qty)


def calc_stop(entry_price: float, side: int, atr: float) -> float:
    """Hard stop: 1 ATR against position (~1% risk when sized correctly)."""
    if side == 1:
        return entry_price - atr
    return entry_price + atr


def correlation_blocks_new_trade(
    symbol: str,
    side: int,
    group: str,
    positions: dict[str, Position],
) -> bool:
    """
    Block stacking correlated risk-on exposure.
    If multiple symbols in the same group are already long, reject another long.
    """
    if group not in CORRELATION_GROUPS:
        return False

    group_symbols = CORRELATION_GROUPS[group]
    same_group_longs = [
        p
        for sym, p in positions.items()
        if sym in group_symbols and p.side == 1
    ]
    if side == 1 and len(same_group_longs) >= 1:
        # Already long one index — don't pile into another
        existing = same_group_longs[0].symbol
        if symbol != existing:
            return True
    return False


def portfolio_equity(portfolio: Portfolio, prices: dict[str, float]) -> float:
    equity = portfolio.cash
    for sym, pos in portfolio.positions.items():
        price = prices.get(sym, pos.entry_price)
        if pos.side == 1:
            equity += pos.quantity * price
        else:
            equity -= pos.quantity * price
    return equity
