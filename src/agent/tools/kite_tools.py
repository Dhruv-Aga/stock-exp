"""Kite portfolio tools — mirrors Kite MCP tool surface using Kite Connect."""

from __future__ import annotations

from typing import Any

from src import settings
from src.broker.kite_client import KiteClient


def _client() -> KiteClient:
    settings.load_settings()
    if not settings.kite_configured():
        raise RuntimeError(
            "Kite not configured. Add KITE_API_KEY, KITE_API_SECRET, and KITE_ACCESS_TOKEN "
            "to .env (run python run_kite_login.py to refresh the token)."
        )
    return KiteClient(dry_run=False)


def get_profile(_args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    profile = client.profile()
    return {"profile": profile, "source": "kite_connect"}


def get_holdings(_args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    holdings = client.holdings()
    total_value = sum(float(h.get("last_price", 0)) * float(h.get("quantity", 0)) for h in holdings)
    return {
        "holdings": holdings,
        "count": len(holdings),
        "total_market_value": round(total_value, 2),
        "source": "kite_connect",
    }


def get_positions(_args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    positions = client.positions()
    net = positions.get("net", [])
    day = positions.get("day", [])
    total_pnl = sum(float(p.get("pnl", 0)) for p in net)
    return {
        "net": net,
        "day": day,
        "net_count": len(net),
        "total_unrealized_pnl": round(total_pnl, 2),
        "source": "kite_connect",
    }


def get_margins(_args: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    margins = client.margins()
    equity = margins.get("equity", {})
    return {
        "margins": margins,
        "available_cash": equity.get("available", {}).get("cash"),
        "available_live_balance": equity.get("available", {}).get("live_balance"),
        "utilised_debits": equity.get("utilised", {}).get("debits"),
        "source": "kite_connect",
    }
