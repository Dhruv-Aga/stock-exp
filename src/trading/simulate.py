"""Apply session plans to portfolios (paper simulation)."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

from config import INITIAL_CAPITAL, MARKETS
from src.risk import Portfolio, Position, portfolio_equity
from src.trading.session_plan import EntryIntent, ExitIntent, SessionPlan


def clone_portfolio(portfolio: Portfolio) -> Portfolio:
    cloned = Portfolio(cash=portfolio.cash)
    cloned.positions = {sym: copy.copy(pos) for sym, pos in portfolio.positions.items()}
    cloned.trades = list(portfolio.trades)
    cloned.equity_curve = list(portfolio.equity_curve)
    return cloned


def load_portfolio_from_json(path: Path, *, default_cash: float = INITIAL_CAPITAL) -> Portfolio:
    if not path.exists():
        return Portfolio(cash=default_cash)
    raw = json.loads(path.read_text())
    portfolio = Portfolio(cash=raw.get("cash", default_cash))
    for sym, p in raw.get("positions", {}).items():
        portfolio.positions[sym] = Position(**p)
    portfolio.trades = raw.get("trades", [])
    return portfolio


def apply_exit_paper(portfolio: Portfolio, intent: ExitIntent) -> float:
    pos = portfolio.positions.pop(intent.symbol)
    if pos.side == 1:
        pnl = (intent.price - pos.entry_price) * pos.quantity
        portfolio.cash += intent.price * pos.quantity
    else:
        pnl = (pos.entry_price - intent.price) * pos.quantity
        portfolio.cash -= intent.price * pos.quantity
    return pnl


def apply_entry_paper(portfolio: Portfolio, intent: EntryIntent) -> None:
    cost = intent.price * intent.quantity
    if intent.side == 1:
        portfolio.cash -= cost
    else:
        portfolio.cash += cost
    market = next(m for m in MARKETS if m.symbol == intent.symbol)
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


def simulate_plan(portfolio: Portfolio, plan: SessionPlan) -> dict:
    """Apply plan to a cloned portfolio without persisting. Returns action log."""
    sim = clone_portfolio(portfolio)
    actions: list[str] = []

    for intent in plan.exit_intents:
        if intent.symbol not in sim.positions:
            actions.append(f"SKIP EXIT {intent.name} - not in portfolio")
            continue
        pnl = apply_exit_paper(sim, intent)
        side = "LONG" if intent.side == 1 else "SHORT"
        actions.append(
            f"EXIT {side} {intent.name} @ Rs{intent.price:.2f} (P&L Rs{pnl:,.0f}) - {intent.reason_code}"
        )

    for msg in plan.skip_messages:
        actions.append(msg)

    for intent in plan.entry_intents:
        apply_entry_paper(sim, intent)
        side = "LONG" if intent.side == 1 else "SHORT"
        actions.append(
            f"ENTER {side} {intent.name} @ Rs{intent.price:.2f} qty={intent.quantity:.2f} "
            f"stop=Rs{intent.stop_price:.2f} - {intent.reason_text}"
        )

    equity = portfolio_equity(sim, plan.prices)
    return {
        "actions": actions,
        "equity": equity,
        "cash": sim.cash,
        "open_positions": len(sim.positions),
        "positions": {
            sym: {
                "side": p.side,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "stop_price": p.stop_price,
            }
            for sym, p in sim.positions.items()
        },
    }


def plan_to_dict(plan: SessionPlan) -> dict:
    return {
        "exit_intents": [asdict(x) for x in plan.exit_intents],
        "entry_intents": [asdict(x) for x in plan.entry_intents],
        "skip_messages": plan.skip_messages,
        "risk_decision": plan.risk_decision,
        "prices": plan.prices,
        "data_as_of": plan.data_as_of,
    }
