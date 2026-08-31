"""Tests for Zerodha live trading infrastructure."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.broker.kite_client import KiteClient
from src.broker.order_manager import OrderManager, TradeIntent
from src.broker.symbol_map import can_trade_side, kite_tradingsymbol, round_quantity
from src.db import init_db, recent_orders, record_order, record_trade, recent_trades
from src.safety import is_market_open, kill_switch_active
from src.settings import auto_approve_trades, dry_run_mode, load_settings


def test_dry_run_mode_default():
    load_settings()
    assert dry_run_mode() is True


def test_auto_approve_trades_default(monkeypatch):
    monkeypatch.delenv("AUTO_APPROVE_TRADES", raising=False)
    load_settings()
    assert auto_approve_trades() is False


def test_auto_approve_trades_enabled(monkeypatch):
    monkeypatch.setenv("AUTO_APPROVE_TRADES", "true")
    load_settings()
    assert auto_approve_trades() is True


def test_paper_shadow_skips_auto_execute(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTO_APPROVE_TRADES", "true")
    monkeypatch.setenv("LIVE_TRADING", "true")
    monkeypatch.setattr("src.db.DB_PATH", tmp_path / "test.db")
    load_settings()
    from src.approvals.propose import propose_entry

    proposal = propose_entry(
        symbol="VEDL.NS",
        side=1,
        quantity=1,
        price=100,
        stop_price=95,
        reason="shadow test",
        source="paper_shadow",
    )
    assert proposal["status"] == "pending"


def test_symbol_mapping():
    assert kite_tradingsymbol("VAML.NS") == "VAML"
    assert kite_tradingsymbol("VEDL.NS") == "VEDL"
    assert kite_tradingsymbol("VEDPOWER.NS") == "VEDPOWER"


def test_cash_only_blocks_short():
    assert can_trade_side("VAML.NS", 1, cash_only=True) is True
    assert can_trade_side("VAML.NS", -1, cash_only=True) is False


def test_round_quantity_equity():
    assert round_quantity("VEDL.NS", 12.7) == 12


def test_dry_run_place_order():
    client = KiteClient(dry_run=True)
    result = client.place_order(
        symbol="VEDL.NS",
        transaction_type="BUY",
        quantity=1,
        order_type="MARKET",
    )
    assert result.dry_run is True
    assert result.status == "DRY_RUN"
    assert result.order_id.startswith("DRY-")


def test_order_manager_records_db(tmp_path, monkeypatch):
    monkeypatch.setattr("src.db.DB_PATH", tmp_path / "test.db")
    init_db()
    client = KiteClient(dry_run=True)
    mgr = OrderManager(client)
    intent = TradeIntent(
        symbol="VEDL.NS",
        side=1,
        quantity=10,
        price=2500,
        stop_price=2450,
        reason="test",
    )
    result = mgr.enter(intent)
    assert result.status == "DRY_RUN"
    orders = recent_orders(1)
    assert len(orders) == 1
    assert orders[0]["symbol"] == "VEDL.NS"


def test_record_order_db(tmp_path, monkeypatch):
    monkeypatch.setattr("src.db.DB_PATH", tmp_path / "test.db")
    init_db()
    record_order(
        order_id="TEST-1",
        symbol="ONGC.NS",
        side="BUY",
        quantity=5,
        order_type="MARKET",
        status="DRY_RUN",
        dry_run=True,
        reason="unit_test",
        price=250,
        stop_price=240,
    )
    orders = recent_orders(1)
    assert orders[0]["order_id"] == "TEST-1"


def test_record_trade_db(tmp_path, monkeypatch):
    monkeypatch.setattr("src.db.DB_PATH", tmp_path / "test.db")
    init_db()
    record_trade(
        symbol="VEDL.NS",
        side="long",
        quantity=10,
        entry_time="2026-06-25T10:00:00",
        entry_price=250.0,
        exit_time="2026-06-25T11:00:00",
        exit_price=260.0,
        pnl=100.0,
        reason="test_exit",
        run_type="paper",
        dry_run=True,
    )
    trades = recent_trades(1)
    assert len(trades) == 1
    assert trades[0]["symbol"] == "VEDL.NS"
    assert trades[0]["side"] == "long"
    assert trades[0]["quantity"] == 10
    assert trades[0]["entry_time"] == "2026-06-25T10:00:00"
    assert trades[0]["entry_price"] == 250.0
    assert trades[0]["exit_time"] == "2026-06-25T11:00:00"
    assert trades[0]["exit_price"] == 260.0
    assert trades[0]["pnl"] == 100.0
    assert trades[0]["return_pct"] == 4.0
    assert trades[0]["reason"] == "test_exit"
    assert trades[0]["run_type"] == "paper"
    assert trades[0]["dry_run"] == 1
