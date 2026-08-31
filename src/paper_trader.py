"""Paper trading session: fetch latest bars and simulate live decisions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config import MARKETS
from src import settings
from src.db import record_session_equity, record_trade, recent_trades, update_daily_pnl
from src.risk import Position, Portfolio, portfolio_equity
from src.risk_governor import format_risk_decision
from src.trade_reasons import (
    exit_reason_label,
    symbol_label,
    trade_reason_summary,
)
from src.trading.session_plan import build_session_plan

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "paper_state.json"


def _load_state() -> Portfolio:
    if not STATE_FILE.exists():
        return Portfolio()
    raw = json.loads(STATE_FILE.read_text())
    portfolio = Portfolio(cash=raw["cash"])
    for sym, p in raw.get("positions", {}).items():
        portfolio.positions[sym] = Position(**p)
    portfolio.trades = raw.get("trades", [])
    return portfolio


def _save_state(portfolio: Portfolio):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cash": portfolio.cash,
        "positions": {
            sym: {
                "symbol": p.symbol,
                "side": p.side,
                "entry_price": p.entry_price,
                "quantity": p.quantity,
                "stop_price": p.stop_price,
                "group": p.group,
                "entry_time": str(p.entry_time) if p.entry_time else None,
                "entry_reason": p.entry_reason,
            }
            for sym, p in portfolio.positions.items()
        },
        "trades": portfolio.trades,
        "updated_at": datetime.now().isoformat(),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2))


def _record_closed_trade(
    portfolio: Portfolio,
    *,
    symbol: str,
    side: str,
    entry_time,
    entry_price: float,
    exit_time,
    exit_price: float,
    quantity: float,
    pnl: float,
    entry_reason_text: str,
    exit_reason_code: str,
):
    summary = trade_reason_summary(
        entry_reason=entry_reason_text,
        exit_reason=exit_reason_code,
    )
    trade = {
        "symbol": symbol,
        "side": side,
        "entry_time": str(entry_time),
        "exit_time": str(exit_time),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "pnl": pnl,
        "entry_reason": entry_reason_text,
        "exit_reason": exit_reason_code,
        "reason": summary,
    }
    portfolio.trades.append(trade)
    record_trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_time=str(entry_time),
        entry_price=entry_price,
        exit_time=str(exit_time),
        exit_price=exit_price,
        pnl=pnl,
        reason=summary,
        run_type="paper",
        dry_run=True,
    )
    update_daily_pnl(realized_delta=pnl, run_type="paper")


def _close_long(
    portfolio: Portfolio,
    symbol: str,
    *,
    exit_price: float,
    ts,
    exit_reason_code: str,
    actions: list[str],
):
    pos = portfolio.positions.pop(symbol)
    pnl = (exit_price - pos.entry_price) * pos.quantity
    portfolio.cash += exit_price * pos.quantity
    _record_closed_trade(
        portfolio,
        symbol=symbol,
        side="long",
        entry_time=pos.entry_time,
        entry_price=pos.entry_price,
        exit_time=ts,
        exit_price=exit_price,
        quantity=pos.quantity,
        pnl=pnl,
        entry_reason_text=pos.entry_reason,
        exit_reason_code=exit_reason_code,
    )
    label = symbol_label(symbol)
    actions.append(
        f"EXIT {label} LONG @ Rs{exit_price:.2f} (P&L Rs{pnl:,.0f}) "
        f"- {exit_reason_label(exit_reason_code)}"
    )


def _close_short(
    portfolio: Portfolio,
    symbol: str,
    *,
    exit_price: float,
    ts,
    exit_reason_code: str,
    actions: list[str],
):
    pos = portfolio.positions.pop(symbol)
    pnl = (pos.entry_price - exit_price) * pos.quantity
    portfolio.cash -= exit_price * pos.quantity
    _record_closed_trade(
        portfolio,
        symbol=symbol,
        side="short",
        entry_time=pos.entry_time,
        entry_price=pos.entry_price,
        exit_time=ts,
        exit_price=exit_price,
        quantity=pos.quantity,
        pnl=pnl,
        entry_reason_text=pos.entry_reason,
        exit_reason_code=exit_reason_code,
    )
    label = symbol_label(symbol)
    actions.append(
        f"EXIT {label} SHORT @ Rs{exit_price:.2f} (P&L Rs{pnl:,.0f}) "
        f"- {exit_reason_label(exit_reason_code)}"
    )


def run_paper_session(*, refresh: bool = True) -> dict:
    """Evaluate latest bar for each market and update paper portfolio."""
    portfolio = _load_state()
    plan = build_session_plan(portfolio, refresh=refresh)
    prices = plan.prices
    data_as_of = plan.data_as_of
    actions: list[str] = []

    for intent in plan.exit_intents:
        if intent.side == 1:
            _close_long(
                portfolio,
                intent.symbol,
                exit_price=intent.price,
                ts=intent.ts,
                exit_reason_code=intent.reason_code,
                actions=actions,
            )
        else:
            _close_short(
                portfolio,
                intent.symbol,
                exit_price=intent.price,
                ts=intent.ts,
                exit_reason_code=intent.reason_code,
                actions=actions,
            )

    for msg in plan.skip_messages:
        actions.append(msg)

    for intent in plan.entry_intents:
        market = next((x for x in MARKETS if x.symbol == intent.symbol), None)
        if not market:
            continue
        cost = intent.price * intent.quantity
        if intent.side == 1:
            portfolio.cash -= cost
        else:
            portfolio.cash += cost
        portfolio.positions[intent.symbol] = Position(
            symbol=intent.symbol,
            side=intent.side,
            entry_price=intent.price,
            quantity=intent.quantity,
            stop_price=intent.stop_price,
            group=market.group,
            entry_time=str(intent.ts),
            entry_reason=intent.reason_text,
        )
        side = "LONG" if intent.side == 1 else "SHORT"
        mult_note = (
            f" [risk {plan.risk_decision.get('risk_multiplier', 1.0):.2f}x]"
            if plan.risk_decision.get("risk_multiplier", 1.0) != 1.0
            else ""
        )
        actions.append(
            f"ENTER {side} {intent.name} @ Rs{intent.price:.2f} qty={intent.quantity:.2f} "
            f"stop=Rs{intent.stop_price:.2f}{mult_note} - {intent.reason_text}"
        )
        if settings.shadow_proposals_enabled():
            from src.approvals.propose import propose_entry as shadow_propose

            proposal = shadow_propose(
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                price=intent.price,
                stop_price=intent.stop_price,
                reason=intent.reason_text,
                strategy=intent.strategy,
                source="paper_shadow",
            )
            actions.append(
                f"  ↳ Shadow live proposal queued for review (id={proposal['id'][:8]}…)"
            )

    equity = portfolio_equity(portfolio, prices)
    unrealized = sum(
        (prices.get(sym, p.entry_price) - p.entry_price) * p.quantity * p.side
        for sym, p in portfolio.positions.items()
    )
    record_session_equity(
        equity=equity, cash=portfolio.cash, unrealized=unrealized, run_type="paper"
    )
    _save_state(portfolio)

    risk_text = format_risk_decision(plan.risk_decision)
    lines = [
        "=" * 60,
        f"PAPER TRADING SESSION - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        risk_text,
        "",
        f"Equity: Rs{equity:,.0f}  |  Cash: Rs{portfolio.cash:,.0f}",
        f"Open positions: {len(portfolio.positions)}  |  Total trades: {len(portfolio.trades)}",
        "",
    ]
    if actions:
        lines.append("Actions this run:")
        lines.extend(f"  * {a}" for a in actions)
    else:
        lines.append("No new actions - holding current positions.")
    if portfolio.positions:
        lines.extend(["", "Current positions:"])
        for sym, p in portfolio.positions.items():
            mark = prices.get(sym, p.entry_price)
            u_pnl = (mark - p.entry_price) * p.quantity * p.side
            lines.append(
                f"  {symbol_label(sym)} {'LONG' if p.side == 1 else 'SHORT'} "
                f"@ Rs{p.entry_price:.2f}  mark Rs{mark:.2f}  uP&L Rs{u_pnl:,.0f}"
            )
            if p.entry_reason:
                lines.append(f"    Entry reason: {p.entry_reason}")
    recent_tr = recent_trades(5)
    if recent_tr:
        lines.extend(["", "Recent Trades (DB):"])
        for t in recent_tr:
            lines.append(
                f"  {t['exit_time'][:16]} {symbol_label(t['symbol'])} {t['side'].upper()} "
                f"qty {t['quantity']:.1f} entry {t['entry_price']:.2f} exit {t['exit_price']:.2f} "
                f"P&L Rs {t['pnl']:,.2f} ({t['return_pct']:.2f}%)"
            )
            lines.append(f"    Reason: {t['reason']}")
    lines.append("=" * 60)

    return {
        "summary": "\n".join(lines),
        "actions": actions,
        "equity": equity,
        "cash": portfolio.cash,
        "unrealized_pnl": unrealized,
        "open_positions": len(portfolio.positions),
        "total_trades": len(portfolio.trades),
        "prices": prices,
        "data_as_of": data_as_of,
        "portfolio": portfolio,
        "risk_decision": plan.risk_decision,
        "governor_context": plan.governor_context,
    }


def reset_paper_account():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    from config import INITIAL_CAPITAL

    return f"Paper account reset to Rs{INITIAL_CAPITAL:,.0f}"
