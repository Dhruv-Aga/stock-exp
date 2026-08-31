"""Tests for paper trading dashboard report."""

from datetime import date

from src.paper_report import _period_realized_pnl, _split_reason, format_paper_report


def test_split_reason_parses_entry_and_exit():
    reason = (
        "Entry: Long: fast EMA crossed above slow EMA | "
        "Exit: Stop loss hit (1 ATR hard stop)"
    )
    entry, exit_r = _split_reason(reason)
    assert "EMA" in entry
    assert "Stop loss" in exit_r


def test_period_realized_pnl_filters_by_date():
    trades = [
        {"exit_time": "2026-08-18 15:00:00", "pnl": 100.0},
        {"exit_time": "2026-08-19 15:00:00", "pnl": -50.0},
        {"exit_time": "2026-08-20 15:00:00", "pnl": 200.0},
    ]
    assert _period_realized_pnl(trades, date(2026, 8, 20), date(2026, 8, 20)) == 200.0
    assert _period_realized_pnl(trades, date(2026, 8, 18), date(2026, 8, 20)) == 250.0


def test_format_paper_report_includes_sections():
    analysis = {
        "generated_at": __import__("datetime").datetime(2026, 8, 20, 9, 15),
        "state_updated": "2026-08-20T09:15:00",
        "session_actions": ["ENTER LONG BHEL - trend signal"],
        "data_as_of": {"BHEL.NS": "2026-08-20 13:15:00+05:30"},
        "equity": 105000.0,
        "cash": 50000.0,
        "unrealized_pnl": 5000.0,
        "realized_pnl_all": 0.0,
        "total_pnl": 5000.0,
        "total_return_pct": 5.0,
        "today_pnl": 0.0,
        "week_pnl": 0.0,
        "month_pnl": 0.0,
        "week_start": date(2026, 8, 18),
        "month_start": date(2026, 8, 1),
        "today_trades": [],
        "recent_trades": [],
        "open_positions": [
            {
                "name": "BHEL",
                "side": "LONG",
                "quantity": 10.0,
                "entry_price": 400.0,
                "mark_price": 410.0,
                "unrealized_pnl": 100.0,
                "entry_reason": "Uptrend EMA crossover",
                "stop_price": 390.0,
            }
        ],
        "daily_equity": [],
        "total_closed_trades": 0,
        "markets": ["BHEL"],
    }
    report = format_paper_report(analysis)
    assert "DAILY PAPER TRADING REPORT" in report
    assert "SESSION ACTIONS" in report
    assert "OPEN POSITIONS" in report
    assert "Uptrend EMA crossover" in report
    assert "P&L SUMMARY" in report
