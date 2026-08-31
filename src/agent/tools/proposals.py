"""Agent tools for trade proposals (human approval required for execution)."""

from __future__ import annotations

from typing import Any

from src import settings
from src.approvals.propose import propose_entry, propose_exit
from src.approvals.store import get_proposal, list_proposals, pending_count


def propose_trade(args: dict[str, Any]) -> dict[str, Any]:
    """
    Queue a live trade for user approval. Does NOT execute on Kite.
    User must approve at /approvals/ before any real order is placed.
    """
    settings.load_settings()
    action = args.get("action", "enter").lower()
    symbol = args["symbol"]
    side = args.get("side", "long").lower()
    quantity = float(args["quantity"])
    price = float(args.get("price") or 0)
    stop_price = args.get("stop_price")
    reason = args.get("reason") or "Requested via assistant"
    strategy = args.get("strategy") or ""

    side_int = 1 if side in ("long", "buy") else -1

    if action == "enter":
        proposal = propose_entry(
            symbol=symbol,
            side=side_int,
            quantity=quantity,
            price=price,
            stop_price=float(stop_price or price * 0.99),
            reason=reason,
            strategy=strategy,
            source="assistant",
        )
    elif action == "exit":
        proposal = propose_exit(
            symbol=symbol,
            side=side_int,
            quantity=quantity,
            price=price,
            reason=reason,
            strategy=strategy,
            source="assistant",
        )
    else:
        raise ValueError("action must be 'enter' or 'exit'")

    if proposal.get("status") == "executed":
        message = "Trade auto-approved and executed on Kite (AUTO_APPROVE_TRADES=true)."
    elif proposal.get("auto_execute_error"):
        message = (
            "Trade queued for your approval. Auto-execute failed: "
            f"{proposal['auto_execute_error']}. Review at /approvals/."
        )
    else:
        message = (
            "Trade queued for your approval. Open /approvals/ to review and approve or reject. "
            "No real order has been placed yet."
        )

    return {
        "proposal": proposal,
        "message": message,
        "pending_count": pending_count(),
        "auto_approve_enabled": settings.auto_approve_trades(),
    }


def list_trade_proposals(args: dict[str, Any]) -> dict[str, Any]:
    status = args.get("status", "pending")
    proposals = list_proposals(status=status if status != "all" else None, limit=int(args.get("limit", 20)))
    return {
        "proposals": proposals,
        "count": len(proposals),
        "pending_count": pending_count(),
        "note": "Live trades require user approval at /approvals/. The assistant cannot approve trades.",
    }


def get_trade_proposal(args: dict[str, Any]) -> dict[str, Any]:
    proposal = get_proposal(args["proposal_id"])
    if not proposal:
        raise ValueError("Proposal not found")
    return {"proposal": proposal}
