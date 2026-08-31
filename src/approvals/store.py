"""Persist and manage trade proposals awaiting user approval."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from src.db import init_db, _conn

PROPOSAL_TTL_HOURS = 24


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_table() -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_proposals (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL,
                stop_price REAL,
                reason TEXT,
                strategy TEXT,
                source TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_at TEXT,
                execution_result TEXT,
                metadata TEXT
            )
            """
        )


def create_proposal(
    *,
    symbol: str,
    action: str,
    side: str,
    quantity: float,
    price: float | None = None,
    stop_price: float | None = None,
    reason: str = "",
    strategy: str = "",
    source: str = "automation",
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Create a pending trade proposal. Does NOT execute on Kite."""
    _ensure_table()
    proposal_id = str(uuid.uuid4())
    created = datetime.now()
    expires = created + timedelta(hours=PROPOSAL_TTL_HOURS)
    row = {
        "id": proposal_id,
        "created_at": created.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "symbol": symbol,
        "action": action,
        "side": side,
        "quantity": float(quantity),
        "price": price,
        "stop_price": stop_price,
        "reason": reason,
        "strategy": strategy,
        "source": source,
        "status": "pending",
        "reviewed_at": None,
        "execution_result": None,
        "metadata": json.dumps(metadata or {}),
    }
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO trade_proposals (
                id, created_at, expires_at, symbol, action, side, quantity,
                price, stop_price, reason, strategy, source, status,
                reviewed_at, execution_result, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["created_at"],
                row["expires_at"],
                row["symbol"],
                row["action"],
                row["side"],
                row["quantity"],
                row["price"],
                row["stop_price"],
                row["reason"],
                row["strategy"],
                row["source"],
                row["status"],
                row["reviewed_at"],
                row["execution_result"],
                row["metadata"],
            ),
        )
    return get_proposal(proposal_id)


def _row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    meta = data.get("metadata")
    if isinstance(meta, str) and meta:
        try:
            data["metadata"] = json.loads(meta)
        except json.JSONDecodeError:
            data["metadata"] = {}
    return data


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    _ensure_table()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM trade_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_proposals(*, status: str | None = "pending", limit: int = 50) -> list[dict[str, Any]]:
    _ensure_table()
    _expire_stale()
    with _conn() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM trade_proposals
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM trade_proposals
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _expire_stale() -> None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE trade_proposals
            SET status = 'expired', reviewed_at = ?
            WHERE status = 'pending' AND expires_at < ?
            """,
            (now, now),
        )


def reject_proposal(proposal_id: str, *, note: str = "") -> dict[str, Any]:
    proposal = get_proposal(proposal_id)
    if not proposal:
        raise ValueError("Proposal not found")
    if proposal["status"] != "pending":
        raise ValueError(f"Proposal is already {proposal['status']}")

    reviewed = _now()
    result = json.dumps({"rejected": True, "note": note})
    with _conn() as conn:
        conn.execute(
            """
            UPDATE trade_proposals
            SET status = 'rejected', reviewed_at = ?, execution_result = ?
            WHERE id = ?
            """,
            (reviewed, result, proposal_id),
        )
    return get_proposal(proposal_id)


def mark_executed(proposal_id: str, execution_result: dict) -> dict[str, Any]:
    reviewed = _now()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE trade_proposals
            SET status = 'executed', reviewed_at = ?, execution_result = ?
            WHERE id = ?
            """,
            (reviewed, json.dumps(execution_result, default=str), proposal_id),
        )
    return get_proposal(proposal_id)


def pending_count() -> int:
    return len(list_proposals(status="pending", limit=999))
