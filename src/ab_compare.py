"""A/B comparison between paper and live-shadow execution on the same session plan."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config import INITIAL_CAPITAL
from src import settings
from src.broker.kite_client import KiteClient
from src.broker.symbol_map import round_quantity
from src.risk import portfolio_equity
from src.trading.session_plan import build_session_plan
from src.trading.simulate import (
    clone_portfolio,
    load_portfolio_from_json,
    plan_to_dict,
    simulate_plan,
)

ROOT = Path(__file__).resolve().parent.parent
PAPER_STATE = ROOT / "data" / "paper_state.json"
LIVE_STATE = ROOT / "data" / "live_state.json"
AB_OUTPUT = ROOT / "data" / "ab_compare.json"


def _normalize_action(action: str) -> str:
    return " ".join(action.split())


def _compare_actions(paper_actions: list[str], live_actions: list[str]) -> list[dict]:
    divergences: list[dict] = []
    max_len = max(len(paper_actions), len(live_actions))
    for idx in range(max_len):
        paper = paper_actions[idx] if idx < len(paper_actions) else None
        live = live_actions[idx] if idx < len(live_actions) else None
        if _normalize_action(paper or "") != _normalize_action(live or ""):
            divergences.append(
                {
                    "index": idx,
                    "paper": paper,
                    "live_shadow": live,
                }
            )
    return divergences


def simulate_plan_live_shadow(portfolio, plan) -> dict:
    """Same plan as paper but with live constraints (whole-share qty)."""
    from src.trading.session_plan import EntryIntent, ExitIntent

    sim = clone_portfolio(portfolio)
    actions: list[str] = []

    for intent in plan.exit_intents:
        qty = round_quantity(intent.symbol, intent.quantity)
        if intent.symbol not in sim.positions:
            actions.append(f"SKIP EXIT {intent.name} - not in portfolio")
            continue
        live_intent = ExitIntent(
            symbol=intent.symbol,
            name=intent.name,
            side=intent.side,
            quantity=qty,
            price=intent.price,
            stop_price=intent.stop_price,
            reason_code=intent.reason_code,
            strategy=intent.strategy,
            ts=intent.ts,
        )
        from src.trading.simulate import apply_exit_paper

        pnl = apply_exit_paper(sim, live_intent)
        side = "LONG" if intent.side == 1 else "SHORT"
        actions.append(
            f"EXIT {side} {intent.name} @ Rs{intent.price:.2f} (P&L Rs{pnl:,.0f}) - {intent.reason_code}"
        )

    for msg in plan.skip_messages:
        actions.append(msg)

    for intent in plan.entry_intents:
        qty = float(round_quantity(intent.symbol, intent.quantity))
        if qty <= 0:
            actions.append(f"SKIP {intent.name} - rounded quantity is zero")
            continue
        live_intent = EntryIntent(
            symbol=intent.symbol,
            name=intent.name,
            side=intent.side,
            quantity=qty,
            price=intent.price,
            stop_price=intent.stop_price,
            reason_text=intent.reason_text,
            strategy=intent.strategy,
            ts=intent.ts,
        )
        from src.trading.simulate import apply_entry_paper

        apply_entry_paper(sim, live_intent)
        side = "LONG" if intent.side == 1 else "SHORT"
        actions.append(
            f"ENTER {side} {intent.name} @ Rs{intent.price:.2f} qty={qty:.0f} "
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


def run_ab_comparison(*, refresh: bool = True, save: bool = True) -> dict:
    """
    Build one shared session plan and project paper vs live-shadow outcomes.

    Uses paper portfolio as the decision baseline; live-shadow applies whole-share
    rounding on the same intents.
    """
    settings.load_settings()
    paper_portfolio = load_portfolio_from_json(PAPER_STATE)
    live_portfolio = load_portfolio_from_json(LIVE_STATE)

    client = KiteClient()
    prefer_kite = client.is_live
    if client.is_live:
        client.load_instruments()

    plan = build_session_plan(
        paper_portfolio,
        refresh=refresh,
        prefer_kite=prefer_kite,
        kite_client=client if client.is_live else None,
    )

    paper_projection = simulate_plan(paper_portfolio, plan)
    live_projection = simulate_plan_live_shadow(live_portfolio, plan)

    # Same starting book comparison (decision parity)
    same_book_paper = simulate_plan(clone_portfolio(paper_portfolio), plan)
    same_book_live = simulate_plan_live_shadow(clone_portfolio(paper_portfolio), plan)

    divergences = _compare_actions(
        same_book_paper["actions"],
        same_book_live["actions"],
    )

    total_actions = max(len(same_book_paper["actions"]), 1)
    parity_score = round(1 - len(divergences) / total_actions, 3)

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "refresh": refresh,
        "data_source": "kite" if prefer_kite else "yfinance",
        "plan": plan_to_dict(plan),
        "paper_state": {
            "equity_before": portfolio_equity(paper_portfolio, plan.prices),
            "cash": paper_portfolio.cash,
            "open_positions": len(paper_portfolio.positions),
        },
        "live_state": {
            "equity_before": portfolio_equity(live_portfolio, plan.prices),
            "cash": live_portfolio.cash,
            "open_positions": len(live_portfolio.positions),
        },
        "paper_projection": paper_projection,
        "live_projection": live_projection,
        "same_book_comparison": {
            "paper": same_book_paper,
            "live_shadow": same_book_live,
            "divergences": divergences,
            "parity_score": parity_score,
        },
        "summary": {
            "exit_intents": len(plan.exit_intents),
            "entry_intents": len(plan.entry_intents),
            "skips": len(plan.skip_messages),
            "parity_score": parity_score,
            "equity_delta_same_book": round(
                same_book_live["equity"] - same_book_paper["equity"], 2
            ),
        },
    }

    if save:
        AB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        AB_OUTPUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    return result


def load_ab_comparison() -> dict | None:
    if not AB_OUTPUT.exists():
        return None
    try:
        return json.loads(AB_OUTPUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
