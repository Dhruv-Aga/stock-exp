"""LLM-based analysis of portfolio alerts for decision support."""

from __future__ import annotations

from typing import Any

from src import settings
from src.triggers.alerts import get_alert, update_alert_with_analysis


def analyze_alert_with_llm(alert_id: str) -> dict[str, Any]:
    """Send alert to LLM for analysis and recommendations."""
    settings.load_settings()

    alert = get_alert(alert_id)
    if not alert:
        raise ValueError(f"Alert {alert_id} not found")

    api_key = settings.groq_api_key()
    if not api_key:
        return {
            "error": "GROQ_API_KEY not configured",
            "alert_id": alert_id,
            "recommendation": "Assistant unavailable - configure GROQ_API_KEY",
        }

    from groq import Groq

    client = Groq(api_key=api_key)
    model = settings.groq_model()

    # Build analysis prompt
    prompt = _build_analysis_prompt(alert)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": """You are a portfolio risk analyst for Bharat Scout trading system.
Analyze the alert and provide:
1. Risk assessment (low/medium/high/critical)
2. Root cause analysis
3. Recommended action (e.g., reduce position, pause strategy, monitor, no action)
4. Reasoning for the recommendation

Be concise and data-driven. Only recommend actions that reduce risk or improve outcomes.""",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    analysis_text = response.choices[0].message.content

    analysis_result = {
        "raw_analysis": analysis_text,
        "alert_type": alert["alert_type"],
        "severity": alert["severity"],
        "timestamp": alert["created_at"],
    }

    # Update alert with analysis
    updated = update_alert_with_analysis(
        alert_id,
        analysis_result,
        new_status="analyzed",
    )

    return {
        "alert_id": alert_id,
        "analysis": analysis_result,
        "status": updated["status"],
    }


def _build_analysis_prompt(alert: dict[str, Any]) -> str:
    """Build the prompt for LLM alert analysis."""
    lines = [
        f"Alert Type: {alert['alert_type']}",
        f"Severity: {alert['severity']}",
        f"Description: {alert['description']}",
        "",
    ]

    if alert.get("symbol"):
        lines.append(f"Symbol: {alert['symbol']}")

    if alert.get("metric_name"):
        lines.append(f"Metric: {alert['metric_name']}")
        lines.append(f"Current Value: {alert['metric_value']:.2f}")
        lines.append(f"Threshold: {alert['threshold']:.2f}")

    if alert.get("portfolio_value"):
        lines.append(f"Portfolio Value: ${alert['portfolio_value']:.2f}")

    if alert.get("raw_data"):
        lines.append("")
        lines.append("Raw Data:")
        for key, val in alert["raw_data"].items():
            if isinstance(val, (int, float)):
                lines.append(f"  {key}: {val:.2f}")
            elif isinstance(val, list) and len(val) <= 5:
                lines.append(f"  {key}: {val}")
            elif isinstance(val, dict):
                lines.append(f"  {key}: (detailed data)")

    lines.append("")
    lines.append(
        "What action should the trader take to address this alert? "
        "Prioritize portfolio safety and risk reduction."
    )

    return "\n".join(lines)


def batch_analyze_pending_alerts(limit: int = 10) -> list[dict[str, Any]]:
    """Analyze up to N pending alerts with LLM."""
    from src.triggers.alerts import list_alerts

    alerts = list_alerts(status="pending_analysis", limit=limit)
    results = []

    for alert in alerts:
        try:
            result = analyze_alert_with_llm(alert["id"])
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "alert_id": alert["id"],
                    "error": str(e),
                    "status": "analysis_failed",
                }
            )

    return results
