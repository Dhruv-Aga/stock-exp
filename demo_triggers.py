#!/usr/bin/env python3
"""Demo: Trigger system in action.

This script demonstrates the trigger system detecting portfolio issues
and sending them for LLM analysis.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.risk import Portfolio, Position
from src.triggers.detectors import run_all_detectors
from src.triggers.alerts import create_alert, list_alerts
from src.triggers.analyzer import analyze_alert_with_llm


def demo():
    """Demonstrate trigger system."""
    print("=" * 70)
    print("TRIGGER SYSTEM DEMO: Portfolio Monitoring & LLM Analysis")
    print("=" * 70)

    # Create a problematic portfolio
    print("\n1. Creating test portfolio with risk issues...")
    portfolio = Portfolio(cash=30000)  # Low cash = high margin usage

    # Add concentrated positions
    portfolio.positions["INFY"] = Position(
        symbol="INFY",
        side=1,
        entry_price=1500,
        quantity=15,  # Large position
        stop_price=1450,
        group="nifty50",
    )
    portfolio.positions["TCS"] = Position(
        symbol="TCS",
        side=1,
        entry_price=3500,
        quantity=8,
        stop_price=3400,
        group="nifty50",
    )
    portfolio.positions["HDFC"] = Position(
        symbol="HDFC",
        side=1,
        entry_price=2000,
        quantity=6,
        stop_price=1950,
        group="nifty50",
    )

    # Add losing trades
    portfolio.trades = [
        {"symbol": "RELIANCE", "pnl": -1000, "exit_reason": "stop_loss", "exit_time": "2026-09-01 14:00"},
        {"symbol": "MARUTI", "pnl": -800, "exit_reason": "stop_loss", "exit_time": "2026-09-01 15:00"},
        {"symbol": "WIPRO", "pnl": -600, "exit_reason": "stop_loss", "exit_time": "2026-09-02 10:00"},
        {"symbol": "AXISBANK", "pnl": 500, "exit_reason": "profit_target", "exit_time": "2026-09-02 12:00"},
    ]

    portfolio_value = sum(p.entry_price * p.quantity for p in portfolio.positions.values()) + portfolio.cash
    print(f"\n   Portfolio Summary:")
    print(f"   - Cash: Rs {portfolio.cash:,.0f}")
    print(f"   - Open positions: {len(portfolio.positions)}")
    print(f"   - Total value: Rs {portfolio_value:,.0f}")
    print(f"   - Recent trades: {len(portfolio.trades)}")

    # Run detectors
    print("\n2. Running portfolio detectors...")
    detections = run_all_detectors(portfolio, initial_capital=100000)
    print(f"   Found {len(detections)} issues:")
    for detection in detections:
        print(f"   - [{detection.severity.upper()}] {detection.alert_type}")
        print(f"     {detection.description}")

    # Create alerts
    print("\n3. Creating alerts for detected issues...")
    alerts_created = []
    for detection in detections:
        alert = create_alert(
            alert_type=detection.alert_type,
            severity=detection.severity,
            description=detection.description,
            symbol=detection.symbol,
            portfolio_value=portfolio_value,
            metric_name=detection.metric_name,
            metric_value=detection.metric_value,
            threshold=detection.threshold,
            raw_data=detection.raw_data,
        )
        alerts_created.append(alert)
        print(f"   - Created alert: {alert['id'][:12]}... ({alert['alert_type']})")

    # Display alert status
    print("\n4. Alert Status:")
    all_alerts = list_alerts(status="pending_analysis", limit=50)
    print(f"   Total pending analysis: {len(all_alerts)}")
    for alert in all_alerts[:3]:  # Show first 3
        print(f"\n   Alert: {alert['alert_type']}")
        print(f"   Severity: {alert['severity']}")
        print(f"   Status: {alert['status']}")
        print(f"   Description: {alert['description']}")

    # Try LLM analysis if configured
    print("\n5. LLM Analysis (requires GROQ_API_KEY)...")
    from src import settings
    settings.load_settings()

    if not settings.groq_api_key():
        print("   GROQ_API_KEY not configured - skipping LLM analysis")
        print("   To enable: Set GROQ_API_KEY=your_key in .env")
    else:
        if alerts_created:
            alert_id = alerts_created[0]["id"]
            print(f"   Analyzing first alert ({alert_id[:12]}...)...")
            try:
                result = analyze_alert_with_llm(alert_id)
                print(f"\n   LLM Analysis Result:")
                print(f"   Status: {result['status']}")
                print("   Analysis: [LLM response received and stored]")
            except Exception as e:
                print(f"   Note: Analysis skipped ({str(e)[:50]})")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Check alerts: GET /api/triggers/alerts")
    print("2. Review specific alert: GET /api/triggers/alerts/{alert_id}")
    print("3. Mark as reviewed: POST /api/triggers/alerts/{alert_id}/review")
    print("\nSee TRIGGERS.md for full API documentation")


if __name__ == "__main__":
    demo()
