"""Store and manage portfolio monitoring alerts for LLM analysis."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from src.db import init_db, _conn

ALERT_TTL_HOURS = 72


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_table() -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_alerts (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                symbol TEXT,
                portfolio_value REAL,
                metric_name TEXT,
                metric_value REAL,
                threshold REAL,
                description TEXT NOT NULL,
                raw_data TEXT,
                llm_analysis TEXT,
                status TEXT NOT NULL DEFAULT 'pending_analysis',
                reviewed_at TEXT,
                action_taken TEXT,
                metadata TEXT
            )
            """
        )


def create_alert(
    *,
    alert_type: str,
    severity: str,
    description: str,
    symbol: str | None = None,
    portfolio_value: float | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
    threshold: float | None = None,
    raw_data: dict | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Create a new portfolio alert awaiting LLM analysis."""
    _ensure_table()
    alert_id = str(uuid.uuid4())
    created = datetime.now()
    expires = created + timedelta(hours=ALERT_TTL_HOURS)

    row = {
        "id": alert_id,
        "created_at": created.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "alert_type": alert_type,
        "severity": severity,
        "symbol": symbol,
        "portfolio_value": portfolio_value,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "threshold": threshold,
        "description": description,
        "raw_data": json.dumps(raw_data or {}),
        "llm_analysis": None,
        "status": "pending_analysis",
        "reviewed_at": None,
        "action_taken": None,
        "metadata": json.dumps(metadata or {}),
    }

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_alerts (
                id, created_at, expires_at, alert_type, severity, symbol,
                portfolio_value, metric_name, metric_value, threshold, description,
                raw_data, llm_analysis, status, reviewed_at, action_taken, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["created_at"],
                row["expires_at"],
                row["alert_type"],
                row["severity"],
                row["symbol"],
                row["portfolio_value"],
                row["metric_name"],
                row["metric_value"],
                row["threshold"],
                row["description"],
                row["raw_data"],
                row["llm_analysis"],
                row["status"],
                row["reviewed_at"],
                row["action_taken"],
                row["metadata"],
            ),
        )
    return get_alert(alert_id)


def _row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    for field in ["raw_data", "metadata"]:
        val = data.get(field)
        if isinstance(val, str) and val:
            try:
                data[field] = json.loads(val)
            except json.JSONDecodeError:
                data[field] = {}

    val = data.get("llm_analysis")
    if isinstance(val, str) and val:
        try:
            data["llm_analysis"] = json.loads(val)
        except json.JSONDecodeError:
            data["llm_analysis"] = None

    return data


def get_alert(alert_id: str) -> dict[str, Any] | None:
    _ensure_table()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio_alerts WHERE id = ?", (alert_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_alerts(
    *, status: str | None = None, limit: int = 50, symbol: str | None = None
) -> list[dict[str, Any]]:
    _ensure_table()
    _expire_stale()

    with _conn() as conn:
        if status and symbol:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_alerts
                WHERE status = ? AND symbol = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, symbol, limit),
            ).fetchall()
        elif status:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_alerts
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        elif symbol:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_alerts
                WHERE symbol = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM portfolio_alerts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    return [_row_to_dict(r) for r in rows]


def update_alert_with_analysis(
    alert_id: str, llm_analysis: dict, new_status: str = "analyzed"
) -> dict[str, Any]:
    """Update alert with LLM analysis result."""
    with _conn() as conn:
        conn.execute(
            """
            UPDATE portfolio_alerts
            SET llm_analysis = ?, status = ?
            WHERE id = ?
            """,
            (json.dumps(llm_analysis, default=str), new_status, alert_id),
        )
    return get_alert(alert_id)


def mark_reviewed(alert_id: str, *, action_taken: str = "") -> dict[str, Any]:
    """Mark alert as reviewed and action taken."""
    reviewed = _now()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE portfolio_alerts
            SET status = 'reviewed', reviewed_at = ?, action_taken = ?
            WHERE id = ?
            """,
            (reviewed, action_taken or None, alert_id),
        )
    return get_alert(alert_id)


def _expire_stale() -> None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE portfolio_alerts
            SET status = 'expired'
            WHERE status IN ('pending_analysis', 'analyzed') AND expires_at < ?
            """,
            (now,),
        )
