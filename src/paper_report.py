"""Daily paper-trading dashboard report from live portfolio state."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from config import INITIAL_CAPITAL, MARKETS
from src.db import all_trades, daily_equity_history, trades_on_date
from src.paper_trader import STATE_FILE, _load_state
from src.risk import portfolio_equity
from src.risk_governor import format_risk_decision, load_last_risk_decision
from src.trade_reasons import exit_reason_label, symbol_label


def _parse_trade_date(exit_time: str) -> date:
    ts = pd.to_datetime(exit_time)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.date()


def _period_realized_pnl(trades: list[dict], start: date, end: date) -> float:
    total = 0.0
    for t in trades:
        d = _parse_trade_date(t["exit_time"])
        if start <= d <= end:
            total += float(t["pnl"])
    return total


def _split_reason(reason: str) -> tuple[str, str]:
    if "| Exit:" in reason:
        entry_part, exit_part = reason.split("| Exit:", 1)
        return entry_part.replace("Entry:", "").strip(), exit_part.strip()
    if reason.startswith("entry:") and "|exit:" in reason:
        entry_part, exit_part = reason.split("|exit:", 1)
        return entry_part.replace("entry:", "").strip(), exit_part.strip()
    return "", reason


def build_paper_analysis(*, session: dict | None = None) -> dict:
    portfolio = _load_state()
    prices = (session or {}).get("prices") or {
        sym: p.entry_price for sym, p in portfolio.positions.items()
    }
    equity = portfolio_equity(portfolio, prices)
    unrealized = sum(
        (prices.get(sym, p.entry_price) - p.entry_price) * p.quantity * p.side
        for sym, p in portfolio.positions.items()
    )
    realized_all = sum(float(t.get("pnl", 0)) for t in portfolio.trades)
    db_trades = all_trades(run_type="paper")
    if db_trades:
        realized_all = sum(float(t["pnl"]) for t in db_trades)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    today_pnl = _period_realized_pnl(db_trades, today, today)
    week_pnl = _period_realized_pnl(db_trades, week_start, today)
    month_pnl = _period_realized_pnl(db_trades, month_start, today)
    total_pnl = equity - INITIAL_CAPITAL
    total_return_pct = (equity / INITIAL_CAPITAL - 1) * 100 if INITIAL_CAPITAL else 0.0

    today_trades = trades_on_date(today, run_type="paper")
    recent_trades = list(reversed(db_trades[-20:]))

    equity_hist = daily_equity_history(limit=14)
    daily_rows = []
    for row in reversed(equity_hist):
        notes = row.get("notes") or ""
        eq_val = None
        if "equity=" in notes:
            try:
                eq_val = float(notes.split("equity=")[1].split(",")[0])
            except (IndexError, ValueError):
                eq_val = None
        daily_rows.append(
            {
                "date": row["trade_date"],
                "realized_pnl": float(row["realized_pnl"]),
                "unrealized_pnl": float(row["unrealized_pnl"]),
                "equity": eq_val,
            }
        )

    open_positions = []
    for sym, p in portfolio.positions.items():
        mark = prices.get(sym, p.entry_price)
        u_pnl = (mark - p.entry_price) * p.quantity * p.side
        open_positions.append(
            {
                "symbol": sym,
                "name": symbol_label(sym),
                "side": "LONG" if p.side == 1 else "SHORT",
                "entry_price": p.entry_price,
                "mark_price": mark,
                "quantity": p.quantity,
                "unrealized_pnl": u_pnl,
                "entry_reason": p.entry_reason,
                "entry_time": str(p.entry_time),
                "stop_price": p.stop_price,
            }
        )

    state_updated = None
    if STATE_FILE.exists():
        import json

        raw = json.loads(STATE_FILE.read_text())
        state_updated = raw.get("updated_at")

    return {
        "generated_at": datetime.now(),
        "state_updated": state_updated,
        "session_actions": (session or {}).get("actions", []),
        "data_as_of": (session or {}).get("data_as_of", {}),
        "equity": equity,
        "cash": portfolio.cash,
        "unrealized_pnl": unrealized,
        "realized_pnl_all": realized_all,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "today_pnl": today_pnl,
        "week_pnl": week_pnl,
        "month_pnl": month_pnl,
        "week_start": week_start,
        "month_start": month_start,
        "today_trades": today_trades,
        "recent_trades": recent_trades,
        "open_positions": open_positions,
        "daily_equity": daily_rows,
        "total_closed_trades": len(db_trades),
        "markets": [m.name for m in MARKETS],
        "risk_decision": (session or {}).get("risk_decision") or load_last_risk_decision(),
        "signals": ((session or {}).get("governor_context") or {}).get("signals", []),
    }


def format_paper_report(analysis: dict) -> str:
    names = {m.symbol: m.name for m in MARKETS}
    gen = analysis["generated_at"].strftime("%Y-%m-%d %H:%M")

    lines = [
        "INDIA TRADING BOT - DAILY PAPER TRADING REPORT",
        "=" * 62,
        f"Generated      : {gen}",
        f"State updated  : {analysis.get('state_updated') or 'n/a'}",
        f"Capital        : Rs {INITIAL_CAPITAL:,.0f}",
        f"Mode           : Paper trading (simulated, no real orders)",
        "",
        "PORTFOLIO SNAPSHOT",
        f"  Equity now     : Rs {analysis['equity']:,.0f}",
        f"  Cash           : Rs {analysis['cash']:,.0f}",
        f"  Unrealized P&L : Rs {analysis['unrealized_pnl']:,.0f}",
        f"  Total return   : {analysis['total_return_pct']:+.2f}% "
        f"(Rs {analysis['total_pnl']:+,.0f} vs start)",
        f"  Closed trades  : {analysis['total_closed_trades']}",
        f"  Open positions : {len(analysis['open_positions'])}",
        "",
        "P&L SUMMARY",
        f"  Today ({date.today()})     : Rs {analysis['today_pnl']:+,.0f}",
        f"  This week (from {analysis['week_start']}) : Rs {analysis['week_pnl']:+,.0f}",
        f"  This month (from {analysis['month_start']}) : Rs {analysis['month_pnl']:+,.0f}",
        f"  All-time realized : Rs {analysis['realized_pnl_all']:+,.0f}",
        "",
    ]

    risk = analysis.get("risk_decision")
    if risk:
        lines.extend([format_risk_decision(risk), ""])

    signals = analysis.get("signals") or []
    if signals:
        lines.extend(["STRATEGY SIGNALS (latest bar)", "-" * 62])
        for s in signals:
            lines.append(
                f"  {s.get('name', s.get('symbol')):22s}  "
                f"{s.get('signal_label', 'flat'):5s}  "
                f"Rs {s.get('price', 0):,.2f}  "
                f"{'OPEN' if s.get('has_position') else 'flat'}"
            )
            entry_r = s.get("entry_reason_text", "")
            if entry_r and s.get("signal", 0) != 0:
                lines.append(f"    Signal reason: {entry_r}")
        lines.append("")

    if analysis["data_as_of"]:
        lines.extend(["MARKET DATA AS OF", "-" * 62])
        for sym, ts in analysis["data_as_of"].items():
            lines.append(f"  {names.get(sym, sym):22s}  latest bar {ts}")
        lines.append("")

    session_actions = analysis.get("session_actions") or []
    lines.extend(["SESSION ACTIONS (this run)", "-" * 62])
    if session_actions:
        for action in session_actions:
            lines.append(f"  * {action}")
    else:
        lines.append("  No new entries or exits on the latest bar.")
    lines.append("")

    if analysis["today_trades"]:
        lines.extend(["TRADES CLOSED TODAY", "-" * 62])
        for t in analysis["today_trades"]:
            entry_r, exit_r = _split_reason(t.get("reason", ""))
            lines.append(
                f"  {symbol_label(t['symbol'])} {t['side'].upper()}  "
                f"entry Rs{t['entry_price']:.2f} -> exit Rs{t['exit_price']:.2f}  "
                f"P&L Rs {t['pnl']:+,.0f} ({t['return_pct']:+.2f}%)"
            )
            if entry_r:
                lines.append(f"    Entry reason: {entry_r}")
            lines.append(f"    Exit reason : {exit_r or exit_reason_label(t.get('reason', ''))}")
        lines.append("")

    if analysis["open_positions"]:
        lines.extend(["OPEN POSITIONS", "-" * 62])
        for p in analysis["open_positions"]:
            lines.append(
                f"  {p['name']} {p['side']}  qty {p['quantity']:.2f}  "
                f"entry Rs{p['entry_price']:.2f}  mark Rs{p['mark_price']:.2f}  "
                f"uP&L Rs {p['unrealized_pnl']:+,.0f}  stop Rs{p['stop_price']:.2f}"
            )
            if p["entry_reason"]:
                lines.append(f"    Entry reason: {p['entry_reason']}")
        lines.append("")

    if analysis["recent_trades"]:
        lines.extend(["RECENT CLOSED TRADES (last 20)", "-" * 62])
        for t in reversed(analysis["recent_trades"]):
            entry_r, exit_r = _split_reason(t.get("reason", ""))
            exit_ts = str(t["exit_time"])[:16]
            lines.append(
                f"  {exit_ts}  {symbol_label(t['symbol'])} {t['side'].upper()}  "
                f"Rs{t['entry_price']:.2f} -> Rs{t['exit_price']:.2f}  "
                f"P&L Rs {t['pnl']:+,.0f}"
            )
            if entry_r:
                lines.append(f"    Entry reason: {entry_r}")
            lines.append(f"    Exit reason : {exit_r or exit_reason_label(t.get('reason', ''))}")
        lines.append("")

    daily = analysis.get("daily_equity") or []
    if daily:
        lines.extend(["DAILY EQUITY SNAPSHOTS (last sessions)", "-" * 62])
        for row in daily[-14:]:
            eq = row.get("equity")
            eq_text = f"equity Rs {eq:,.0f}" if eq is not None else "equity n/a"
            lines.append(
                f"  {row['date']}  realized Rs {row['realized_pnl']:+,.0f}  "
                f"unrealized Rs {row['unrealized_pnl']:+,.0f}  {eq_text}"
            )
        lines.append("")

    lines.extend(
        [
            "=" * 62,
            "Note: Paper trading only. Brokerage and taxes not included.",
            "Past simulated results do not guarantee future returns.",
        ]
    )
    return "\n".join(lines)
