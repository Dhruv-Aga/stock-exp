"""SQLite persistence for orders, fills, and daily P&L."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime

from src.settings import DB_PATH


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                status TEXT NOT NULL,
                dry_run INTEGER NOT NULL DEFAULT 1,
                reason TEXT,
                price REAL,
                stop_price REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                filled_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_pnl (
                trade_date TEXT NOT NULL,
                run_type TEXT NOT NULL DEFAULT 'paper',
                realized_pnl REAL NOT NULL DEFAULT 0,
                unrealized_pnl REAL NOT NULL DEFAULT 0,
                notes TEXT,
                PRIMARY KEY (trade_date, run_type)
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                symbols TEXT NOT NULL DEFAULT '[]',
                config TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT 'agent'
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New chat',
                messages TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                entry_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_time TEXT NOT NULL,
                exit_price REAL NOT NULL,
                pnl REAL NOT NULL,
                return_pct REAL NOT NULL,
                reason TEXT NOT NULL,
                run_type TEXT NOT NULL,
                dry_run INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        _migrate_daily_pnl(conn)


def _migrate_daily_pnl(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daily_pnl)").fetchall()}
    if not cols:
        return
    if "run_type" in cols:
        return
    conn.execute("ALTER TABLE daily_pnl RENAME TO daily_pnl_legacy")
    conn.execute(
        """
        CREATE TABLE daily_pnl (
            trade_date TEXT NOT NULL,
            run_type TEXT NOT NULL DEFAULT 'paper',
            realized_pnl REAL NOT NULL DEFAULT 0,
            unrealized_pnl REAL NOT NULL DEFAULT 0,
            notes TEXT,
            PRIMARY KEY (trade_date, run_type)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO daily_pnl (trade_date, run_type, realized_pnl, unrealized_pnl, notes)
        SELECT trade_date, 'paper', realized_pnl, unrealized_pnl, notes
        FROM daily_pnl_legacy
        """
    )
    conn.execute("DROP TABLE daily_pnl_legacy")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_order(
    *,
    order_id: str,
    symbol: str,
    side: str,
    quantity: int,
    order_type: str,
    status: str,
    dry_run: bool,
    reason: str,
    price: float | None = None,
    stop_price: float | None = None,
) -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO orders (
                order_id, symbol, side, quantity, order_type, status,
                dry_run, reason, price, stop_price, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                symbol,
                side,
                quantity,
                order_type,
                status,
                1 if dry_run else 0,
                reason,
                price,
                stop_price,
                datetime.now().isoformat(),
            ),
        )


def record_fill(*, order_id: str, symbol: str, price: float, quantity: int) -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO fills (order_id, symbol, price, quantity, filled_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, symbol, price, quantity, datetime.now().isoformat()),
        )


def get_today_realized_pnl(*, run_type: str | None = None) -> float:
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        if run_type:
            row = conn.execute(
                "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ? AND run_type = ?",
                (today, run_type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(realized_pnl), 0) AS realized_pnl FROM daily_pnl WHERE trade_date = ?",
                (today,),
            ).fetchone()
    return float(row["realized_pnl"]) if row else 0.0


def update_daily_pnl(
    *,
    realized_delta: float = 0.0,
    unrealized: float = 0.0,
    run_type: str = "paper",
) -> None:
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ? AND run_type = ?",
            (today, run_type),
        ).fetchone()
        if row:
            new_realized = float(row["realized_pnl"]) + realized_delta
            conn.execute(
                """
                UPDATE daily_pnl
                SET realized_pnl = ?, unrealized_pnl = ?
                WHERE trade_date = ? AND run_type = ?
                """,
                (new_realized, unrealized, today, run_type),
            )
        else:
            conn.execute(
                """
                INSERT INTO daily_pnl (trade_date, run_type, realized_pnl, unrealized_pnl)
                VALUES (?, ?, ?, ?)
                """,
                (today, run_type, realized_delta, unrealized),
            )


def set_state(key: str, value: str) -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO bot_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, datetime.now().isoformat()),
        )


def get_state(key: str, default: str = "") -> str:
    init_db()
    with _conn() as conn:
        row = conn.execute(
            "SELECT value FROM bot_state WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def save_custom_strategy(
    *,
    name: str,
    description: str,
    symbols: list[str] | None = None,
    config: dict | None = None,
    enabled: bool = True,
    author: str = "agent",
) -> dict:
    """Persist a custom strategy definition for future paper sessions."""
    init_db()
    now = datetime.now().isoformat()
    payload = {
        "name": name.strip(),
        "description": description.strip(),
        "symbols": symbols or [],
        "config": config or {},
        "enabled": 1 if enabled else 0,
        "author": author.strip() or "agent",
    }
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM custom_strategies WHERE name = ?",
            (payload["name"],),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE custom_strategies
                SET description = ?, symbols = ?, config = ?, enabled = ?, updated_at = ?, author = ?
                WHERE name = ?
                """,
                (
                    payload["description"],
                    json.dumps(payload["symbols"]),
                    json.dumps(payload["config"]),
                    payload["enabled"],
                    now,
                    payload["author"],
                    payload["name"],
                ),
            )
            strategy_id = row["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO custom_strategies (
                    name, description, symbols, config, enabled, created_at, updated_at, author
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["name"],
                    payload["description"],
                    json.dumps(payload["symbols"]),
                    json.dumps(payload["config"]),
                    payload["enabled"],
                    now,
                    now,
                    payload["author"],
                ),
            )
            strategy_id = cur.lastrowid
    return {
        "id": strategy_id,
        "name": payload["name"],
        "description": payload["description"],
        "symbols": payload["symbols"],
        "config": payload["config"],
        "enabled": bool(payload["enabled"]),
        "author": payload["author"],
        "updated_at": now,
    }


def list_custom_strategies(*, enabled_only: bool = False, limit: int = 50) -> list[dict]:
    init_db()
    query = "SELECT * FROM custom_strategies"
    params: list = []
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "symbols": json.loads(row["symbols"] or "[]"),
                "config": json.loads(row["config"] or "{}"),
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "author": row["author"],
            }
        )
    return result


def save_chat_session(*, session_id: str | None = None, title: str = "New chat", messages: list[dict] | None = None, metadata: dict | None = None) -> dict:
    """Persist an assistant chat session and its message history to SQLite."""
    init_db()
    now = datetime.now().isoformat()
    sid = (session_id or str(uuid.uuid4())).strip() or str(uuid.uuid4())
    message_payload = messages or []
    meta = metadata or {}
    with _conn() as conn:
        row = conn.execute("SELECT id FROM chat_sessions WHERE id = ?", (sid,)).fetchone()
        if row:
            conn.execute(
                """
                UPDATE chat_sessions
                SET title = ?, messages = ?, updated_at = ?, metadata = ?
                WHERE id = ?
                """,
                (title.strip() or "New chat", json.dumps(message_payload), now, json.dumps(meta), sid),
            )
        else:
            conn.execute(
                """
                INSERT INTO chat_sessions (id, title, messages, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sid, title.strip() or "New chat", json.dumps(message_payload), now, now, json.dumps(meta)),
            )
    return {
        "id": sid,
        "title": title.strip() or "New chat",
        "messages": message_payload,
        "created_at": now,
        "updated_at": now,
        "metadata": meta,
    }


def get_chat_session(session_id: str) -> dict | None:
    init_db()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "messages": json.loads(row["messages"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "metadata": json.loads(row["metadata"] or "{}"),
    }


def list_chat_sessions(limit: int = 50) -> list[dict]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "messages": json.loads(row["messages"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": json.loads(row["metadata"] or "{}"),
        }
        for row in rows
    ]


def delete_chat_session(session_id: str) -> bool:
    init_db()
    with _conn() as conn:
        cur = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    return cur.rowcount > 0


def recent_orders(limit: int = 20) -> list[dict]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def record_trade(
    *,
    symbol: str,
    side: str,
    quantity: float,
    entry_time: str,
    entry_price: float,
    exit_time: str,
    exit_price: float,
    pnl: float,
    reason: str,
    run_type: str,
    dry_run: bool,
) -> None:
    init_db()
    return_pct = (pnl / (entry_price * quantity)) * 100 if (entry_price * quantity) != 0 else 0.0
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO trades (
                symbol, side, quantity, entry_time, entry_price,
                exit_time, exit_price, pnl, return_pct, reason,
                run_type, dry_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                side,
                quantity,
                str(entry_time),
                entry_price,
                str(exit_time),
                exit_price,
                pnl,
                return_pct,
                reason,
                run_type,
                1 if dry_run else 0,
            ),
        )


def recent_trades(limit: int = 20) -> list[dict]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM trades ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def all_trades(*, run_type: str = "paper", dry_run: bool | None = True) -> list[dict]:
    init_db()
    query = "SELECT * FROM trades WHERE run_type = ?"
    params: list = [run_type]
    if dry_run is not None:
        query += " AND dry_run = ?"
        params.append(1 if dry_run else 0)
    query += " ORDER BY exit_time ASC"
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def trades_on_date(trade_date: date, *, run_type: str = "paper") -> list[dict]:
    init_db()
    day = trade_date.isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM trades
            WHERE run_type = ? AND exit_time LIKE ?
            ORDER BY exit_time ASC
            """,
            (run_type, f"{day}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def record_session_equity(*, equity: float, cash: float, unrealized: float, run_type: str = "paper") -> None:
    """Snapshot end-of-session equity for daily P&L tracking."""
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ? AND run_type = ?",
            (today, run_type),
        ).fetchone()
        realized = float(row["realized_pnl"]) if row else 0.0
        conn.execute(
            """
            INSERT INTO daily_pnl (trade_date, run_type, realized_pnl, unrealized_pnl, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, run_type) DO UPDATE SET
                unrealized_pnl = excluded.unrealized_pnl,
                notes = excluded.notes
            """,
            (today, run_type, realized, unrealized, f"equity={equity:.2f},cash={cash:.2f}"),
        )


def daily_equity_history(limit: int = 90) -> list[dict]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT trade_date, realized_pnl, unrealized_pnl, notes
            FROM daily_pnl
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
