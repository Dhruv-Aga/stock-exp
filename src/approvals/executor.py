"""Execute user-approved trade proposals on Kite."""

from __future__ import annotations

from typing import Any

from config import MARKETS
from src import settings
from src.approvals.store import get_proposal, mark_executed
from src.broker.kite_client import KiteClient
from src.broker.order_manager import OrderManager, TradeIntent
from src.broker.symbol_map import can_trade_side
from src.safety import SafetyHalt, check_can_trade


def _side_int(side: str) -> int:
    s = side.lower()
    if s in ("long", "buy", "1"):
        return 1
    if s in ("short", "sell", "-1"):
        return -1
    raise ValueError(f"Invalid side: {side}")


def execute_proposal(proposal_id: str) -> dict[str, Any]:
    """
    Execute an approved proposal on Kite.
    Called only after explicit user approval via the approvals UI/API.
    """
    settings.load_settings()
    if settings.dry_run_mode():
        raise RuntimeError(
            "LIVE_TRADING is not enabled. Set LIVE_TRADING=true only after paper review."
        )
    if not settings.kite_configured():
        raise RuntimeError("Kite credentials not configured in .env")

    proposal = get_proposal(proposal_id)
    if not proposal:
        raise ValueError("Proposal not found")
    if proposal["status"] != "pending":
        raise ValueError(f"Cannot execute proposal with status '{proposal['status']}'")

    try:
        check_can_trade(require_market_open=True)
    except SafetyHalt as exc:
        raise RuntimeError(str(exc)) from exc

    client = KiteClient(dry_run=False)
    if not client.is_live:
        raise RuntimeError("Could not connect to Kite")

    orders = OrderManager(client)
    side = _side_int(proposal["side"])
    action = proposal["action"].lower()
    qty = float(proposal["quantity"])
    price = float(proposal["price"] or 0)
    stop = float(proposal["stop_price"] or price * 0.99)

    market = next((m for m in MARKETS if m.symbol == proposal["symbol"]), None)
    if market and not can_trade_side(market.symbol, side, cash_only=settings.cash_only_mode()):
        raise RuntimeError(f"Trade not allowed: {proposal['symbol']} side {proposal['side']}")

    intent = TradeIntent(
        symbol=proposal["symbol"],
        side=side,
        quantity=qty,
        price=price,
        stop_price=stop,
        reason=proposal.get("reason") or "approved_proposal",
    )

    if action == "enter":
        result = orders.enter(intent)
    elif action == "exit":
        result = orders.exit(intent, position_side=side)
    else:
        raise ValueError(f"Unknown action: {action}")

    execution = {
        "order_id": result.order_id,
        "status": result.status,
        "message": result.message,
        "dry_run": result.dry_run,
    }
    mark_executed(proposal_id, execution)
    return {"proposal_id": proposal_id, "execution": execution, "proposal": get_proposal(proposal_id)}


def approve_and_execute(proposal_id: str) -> dict[str, Any]:
    """User-approved path: execute immediately after validation."""
    return execute_proposal(proposal_id)
