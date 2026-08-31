"""Helpers to queue trades for user approval."""

from __future__ import annotations

from typing import Any

from src import settings
from src.approvals.store import create_proposal, get_proposal


def _should_auto_execute(*, source: str, auto_execute: bool | None) -> bool:
    if source == "paper_shadow":
        return False
    if auto_execute is None:
        auto_execute = settings.auto_approve_trades()
    return bool(
        auto_execute
        and settings.require_trade_approval()
        and settings.live_trading_enabled()
    )


def _finalize_proposal(proposal: dict[str, Any], *, auto_execute: bool) -> dict[str, Any]:
    if not auto_execute:
        return proposal

    from src.approvals.executor import execute_proposal

    try:
        result = execute_proposal(proposal["id"])
        return result.get("proposal") or get_proposal(proposal["id"]) or proposal
    except Exception as exc:
        refreshed = get_proposal(proposal["id"]) or proposal
        refreshed["auto_execute_error"] = str(exc)
        return refreshed


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
    auto_execute: bool | None = None,
) -> dict:
    side_label = "long" if side == 1 else "short"
    proposal = create_proposal(
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
    return _finalize_proposal(
        proposal,
        auto_execute=_should_auto_execute(source=source, auto_execute=auto_execute),
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
    auto_execute: bool | None = None,
) -> dict:
    side_label = "long" if side == 1 else "short"
    proposal = create_proposal(
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
    return _finalize_proposal(
        proposal,
        auto_execute=_should_auto_execute(source=source, auto_execute=auto_execute),
    )


def proposal_action_suffix(proposal: dict[str, Any]) -> str:
    """Human-readable status for automation logs."""
    if proposal.get("status") == "executed":
        return "auto-approved and executed on Kite"
    if proposal.get("auto_execute_error"):
        return f"awaiting approval (auto-execute failed: {proposal['auto_execute_error']})"
    return f"awaiting your approval (id={proposal['id'][:8]}…)"
