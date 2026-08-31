"""SQLite persistence for orders, fills, and daily P&L."""

from __future__ import annotations

import sqlite3
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
                trade_date TEXT PRIMARY KEY,
                realized_pnl REAL NOT NULL DEFAULT 0,
                unrealized_pnl REAL NOT NULL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
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


def get_today_realized_pnl() -> float:
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ?",
            (today,),
        ).fetchone()
    return float(row["realized_pnl"]) if row else 0.0


def update_daily_pnl(*, realized_delta: float = 0.0, unrealized: float = 0.0) -> None:
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ?",
            (today,),
        ).fetchone()
        if row:
            new_realized = float(row["realized_pnl"]) + realized_delta
            conn.execute(
                """
                UPDATE daily_pnl
                SET realized_pnl = ?, unrealized_pnl = ?
                WHERE trade_date = ?
                """,
                (new_realized, unrealized, today),
            )
        else:
            conn.execute(
                """
                INSERT INTO daily_pnl (trade_date, realized_pnl, unrealized_pnl)
                VALUES (?, ?, ?)
                """,
                (today, realized_delta, unrealized),
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


def record_session_equity(*, equity: float, cash: float, unrealized: float) -> None:
    """Snapshot end-of-session equity for daily P&L tracking."""
    init_db()
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT realized_pnl FROM daily_pnl WHERE trade_date = ?",
            (today,),
        ).fetchone()
        realized = float(row["realized_pnl"]) if row else 0.0
        conn.execute(
            """
            INSERT INTO daily_pnl (trade_date, realized_pnl, unrealized_pnl, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                unrealized_pnl = excluded.unrealized_pnl,
                notes = excluded.notes
            """,
            (today, realized, unrealized, f"equity={equity:.2f},cash={cash:.2f}"),
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
