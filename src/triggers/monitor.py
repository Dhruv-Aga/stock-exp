"""Continuous portfolio monitoring with trigger detection and alert queueing."""

from __future__ import annotations

from typing import Any

from config import INITIAL_CAPITAL
from src.paper_trader import _load_state
from src.triggers.alerts import create_alert
from src.triggers.analyzer import batch_analyze_pending_alerts
from src.triggers.detectors import run_all_detectors


def run_portfolio_checks(
    thresholds: dict | None = None,
    auto_analyze: bool = True,
) -> dict[str, Any]:
    """
    Run all portfolio checks and queue alerts for LLM analysis.

    Args:
        thresholds: Custom detection thresholds
        auto_analyze: Whether to immediately run LLM analysis on new alerts

    Returns:
        Summary of checks run, alerts created, and analyses performed
    """
    # Load current paper portfolio state
    portfolio = _load_state()

    # Run all detectors
    detection_results = run_all_detectors(
        portfolio,
        initial_capital=INITIAL_CAPITAL,
        thresholds=thresholds or {},
    )

    # Create alerts for triggered detections
    alerts_created = []
    for detection in detection_results:
        alert = create_alert(
            alert_type=detection.alert_type,
            severity=detection.severity,
            description=detection.description,
            symbol=detection.symbol,
            portfolio_value=sum(
                p.entry_price * p.quantity for p in portfolio.positions.values()
            ),
            metric_name=detection.metric_name,
            metric_value=detection.metric_value,
            threshold=detection.threshold,
            raw_data=detection.raw_data,
        )
        alerts_created.append(alert)

    # Auto-analyze pending alerts if enabled
    analyses = []
    if auto_analyze and alerts_created:
        analyses = batch_analyze_pending_alerts(limit=len(alerts_created))

    return {
        "checks_run": True,
        "detections_found": len(detection_results),
        "alerts_created": len(alerts_created),
        "alerts": alerts_created,
        "analyses_run": len(analyses) if auto_analyze else 0,
        "analysis_results": analyses if auto_analyze else [],
        "portfolio_status": {
            "cash": portfolio.cash,
            "positions": len(portfolio.positions),
            "trades": len(portfolio.trades),
        },
    }
