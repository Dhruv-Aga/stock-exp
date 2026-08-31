"""Tests for paper vs live-shadow A/B comparison."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.risk import Portfolio, Position
from src.trading.session_plan import EntryIntent, ExitIntent, SessionPlan
from src.trading.simulate import clone_portfolio, simulate_plan
from src.ab_compare import _compare_actions, simulate_plan_live_shadow


def _sample_plan() -> SessionPlan:
    plan = SessionPlan(prices={"VEDL.NS": 250.0})
    plan.entry_intents.append(
        EntryIntent(
            symbol="VEDL.NS",
            name="VEDL",
            side=1,
            quantity=12.7,
            price=250.0,
            stop_price=240.0,
            reason_text="test entry",
            strategy="momentum_breakout",
            ts="2026-08-31",
        )
    )
    return plan


def test_compare_actions_detects_divergence():
    paper = ["ENTER LONG VEDL qty=12.70"]
    live = ["ENTER LONG VEDL qty=12"]
    divergences = _compare_actions(paper, live)
    assert len(divergences) == 1


def test_compare_actions_no_divergence():
    actions = ["SKIP ONGC - correlation filter"]
    assert _compare_actions(actions, actions) == []


def test_live_shadow_rounds_quantity():
    portfolio = Portfolio(cash=100_000)
    plan = _sample_plan()
    result = simulate_plan_live_shadow(portfolio, plan)
    assert any("qty=12" in a or "qty=13" in a for a in result["actions"])


def test_same_plan_paper_vs_live_shadow_equity_close():
    portfolio = Portfolio(cash=100_000)
    plan = _sample_plan()
    paper = simulate_plan(clone_portfolio(portfolio), plan)
    live = simulate_plan_live_shadow(clone_portfolio(portfolio), plan)
    # Rounding difference should be small on a single entry
    assert abs(paper["equity"] - live["equity"]) < 500


def test_ab_compare_run_type_pnl_split(tmp_path, monkeypatch):
    monkeypatch.setattr("src.db.DB_PATH", tmp_path / "test.db")
    from src.db import init_db, update_daily_pnl, get_today_realized_pnl

    init_db()
    update_daily_pnl(realized_delta=-1000, run_type="paper")
    update_daily_pnl(realized_delta=-200, run_type="live")
    assert get_today_realized_pnl(run_type="paper") == -1000
    assert get_today_realized_pnl(run_type="live") == -200
