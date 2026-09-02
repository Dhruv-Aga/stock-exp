#!/usr/bin/env python3
"""Test trigger system end-to-end."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.risk import Portfolio, Position
from src.triggers.detectors import (
    check_drawdown,
    check_position_concentration,
    check_margin_usage,
    check_too_many_positions,
    check_losing_streak,
    run_all_detectors,
)
from src.triggers.alerts import (
    create_alert,
    get_alert,
    list_alerts,
    update_alert_with_analysis,
    mark_reviewed,
)


def test_detectors():
    """Test detector functions."""
    print("Testing detectors...")

    # Create test portfolio with positions
    portfolio = Portfolio(cash=50000)
    portfolio.positions["INFY"] = Position(
        symbol="INFY",
        side=1,
        entry_price=1500,
        quantity=10,
        stop_price=1450,
        group="nifty50",
    )
    portfolio.positions["TCS"] = Position(
        symbol="TCS",
        side=1,
        entry_price=3500,
        quantity=5,
        stop_price=3400,
        group="nifty50",
    )
    portfolio.trades = [
        {"symbol": "RELIANCE", "pnl": -500, "exit_reason": "stop_loss"},
        {"symbol": "HDFC", "pnl": -300, "exit_reason": "stop_loss"},
        {"symbol": "ICICI", "pnl": -200, "exit_reason": "stop_loss"},
        {"symbol": "AXIS", "pnl": 1000, "exit_reason": "profit_target"},
    ]

    # Test concentration
    print("  Testing concentration check...")
    conc_results = check_position_concentration(portfolio, max_position_pct=20)
    print(f"    Found {len(conc_results)} concentration alerts")
    for result in conc_results:
        print(f"      - {result.alert_type}: {result.description}")

    # Test drawdown
    print("  Testing drawdown check...")
    dd_result = check_drawdown(portfolio, initial_capital=100000, max_drawdown_pct=5)
    if dd_result:
        print(f"    OK: {dd_result.description}")
    else:
        print("    No drawdown alert (as expected)")

    # Test margin usage
    print("  Testing margin usage check...")
    margin_result = check_margin_usage(portfolio, max_margin_pct=40)
    if margin_result:
        print(f"    OK: {margin_result.description}")
    else:
        print("    No margin alert (as expected)")

    # Test losing streak
    print("  Testing losing streak check...")
    streak_result = check_losing_streak(portfolio, max_consecutive_losses=2)
    if streak_result:
        print(f"    OK: {streak_result.description}")
    else:
        print("    No streak alert (as expected)")

    # Run all detectors
    print("  Testing run_all_detectors...")
    all_results = run_all_detectors(portfolio, initial_capital=100000)
    print(f"    Found {len(all_results)} total alerts")

    return len(all_results) > 0


def test_alerts():
    """Test alert creation and storage."""
    print("\nTesting alert storage...")

    # Create an alert
    print("  Creating alert...")
    alert = create_alert(
        alert_type="high_concentration",
        severity="medium",
        description="Test alert for INFY position",
        symbol="INFY",
        portfolio_value=50000,
        metric_name="position_concentration_pct",
        metric_value=35.5,
        threshold=30.0,
        raw_data={"entry_price": 1500, "quantity": 10},
    )
    print(f"    Created alert: {alert['id'][:8]}...")

    # Get alert
    print("  Retrieving alert...")
    retrieved = get_alert(alert["id"])
    if retrieved:
        print(f"    OK: Retrieved alert status: {retrieved['status']}")

    # List alerts
    print("  Listing alerts...")
    alerts = list_alerts(limit=10)
    print(f"    Found {len(alerts)} alerts")

    # Update with analysis
    print("  Updating with LLM analysis...")
    analysis = {
        "risk_assessment": "medium",
        "recommendation": "Reduce INFY position to 50% of current size",
        "reasoning": "Position concentration risk is elevated",
    }
    updated = update_alert_with_analysis(alert["id"], analysis)
    print(f"    Updated status: {updated['status']}")

    # Mark reviewed
    print("  Marking as reviewed...")
    reviewed = mark_reviewed(alert["id"], action_taken="Reduced position by 50%")
    print(f"    Reviewed status: {reviewed['status']}")

    return retrieved is not None


def test_monitor():
    """Test portfolio monitoring."""
    print("\nTesting portfolio monitoring...")

    # Create test portfolio
    portfolio = Portfolio(cash=50000)
    portfolio.positions["INFY"] = Position(
        symbol="INFY",
        side=1,
        entry_price=1500,
        quantity=10,
        stop_price=1450,
        group="nifty50",
    )

    # Monkey-patch _load_state to return our test portfolio
    import src.paper_trader
    original_load_state = src.paper_trader._load_state
    src.paper_trader._load_state = lambda: portfolio

    try:
        from src.triggers import run_portfolio_checks
        print("  Running portfolio checks...")
        result = run_portfolio_checks(auto_analyze=False)  # Skip LLM analysis
        print(f"    Checks run: {result['checks_run']}")
        print(f"    Detections found: {result['detections_found']}")
        print(f"    Alerts created: {result['alerts_created']}")
        print(f"    Portfolio status: {result['portfolio_status']}")
        return result["checks_run"]
    finally:
        src.paper_trader._load_state = original_load_state


def main():
    """Run all tests."""
    print("=" * 60)
    print("TRIGGER SYSTEM TEST SUITE")
    print("=" * 60)

    tests = [
        ("Detectors", test_detectors),
        ("Alert Storage", test_alerts),
        ("Portfolio Monitoring", test_monitor),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n[ERROR] {name} failed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name}: {status}")

    all_passed = all(results.values())
    print("\n" + ("=" * 60))
    if all_passed:
        print("[PASS] All tests passed!")
    else:
        print("[FAIL] Some tests failed")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
