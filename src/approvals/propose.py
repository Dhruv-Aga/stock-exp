"""Helpers to queue trades for user approval."""

from __future__ import annotations

from src.approvals.store import create_proposal


def propose_entry(
    *,
    symbol: str,
    side: int,
    quantity: float,
    price: float,
    stop_price: float,
    reason: str,
    strategy: str = "",
    source: str = "automation",
) -> dict:
    side_label = "long" if side == 1 else "short"
    return create_proposal(
        symbol=symbol,
        action="enter",
        side=side_label,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        reason=reason,
        strategy=strategy,
        source=source,
    )


def propose_exit(
    *,
    symbol: str,
    side: int,
    quantity: float,
    price: float,
    reason: str,
    strategy: str = "",
    source: str = "automation",
) -> dict:
    side_label = "long" if side == 1 else "short"
    return create_proposal(
        symbol=symbol,
        action="exit",
        side=side_label,
        quantity=quantity,
        price=price,
        stop_price=None,
        reason=reason,
        strategy=strategy,
        source=source,
    )
