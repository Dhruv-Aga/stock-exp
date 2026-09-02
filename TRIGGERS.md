# Portfolio Trigger System Documentation

## Overview

The portfolio trigger system continuously monitors your paper trading portfolio for outliers and risk conditions. When issues are detected, they're automatically sent to the LLM for analysis and queued as alerts for your review.

## How It Works

```
Paper Portfolio State
    ↓
[Continuous Detectors]
  • High drawdown (>10%)
  • Position concentration (>30%)
  • Margin usage (>80%)
  • Too many positions (>5)
  • Losing streak (3+ consecutive losses)
    ↓
[Alert Queue]
    ↓
[LLM Analysis]
  • Risk assessment
  • Root cause analysis
  • Recommended action
    ↓
[Reviewed by User]
  • Accept recommendation
  • Modify/reject
  • Mark as reviewed
```

## Key Features

### 1. Automated Detection
- **High Drawdown**: Detects portfolio drawdown exceeding configured threshold (default: 10%)
- **Position Concentration**: Flags when a single position exceeds max % of portfolio (default: 30%)
- **Margin Usage**: Detects when margin usage is too high (default: 80%)
- **Position Count**: Alerts when open positions exceed limit (default: 5)
- **Losing Streak**: Triggers on consecutive losses (default: 3+)

### 2. LLM-Powered Analysis
Each alert is sent to Groq LLM (configured in GROQ_API_KEY) for:
- Risk assessment (low/medium/high/critical)
- Root cause analysis
- Recommended actions (e.g., "Reduce INFY position by 50%")
- Detailed reasoning

### 3. User Review
All alerts are stored and can be reviewed at any time:
- View pending alerts
- Read LLM analysis
- Mark as reviewed with action notes
- Track historical alerts

## API Endpoints

### Check Portfolio
```
POST /api/triggers/check
Query params:
  - auto_analyze (bool, default=true): Run LLM analysis on new alerts

Response:
{
  "checks_run": true,
  "detections_found": 2,
  "alerts_created": 2,
  "alerts": [...],
  "analyses_run": 2,
  "analysis_results": [...],
  "portfolio_status": {
    "cash": 50000,
    "positions": 3,
    "trades": 15
  }
}
```

### List Alerts
```
GET /api/triggers/alerts
Query params:
  - status (string): "pending_analysis", "analyzed", "reviewed", "expired"
  - symbol (string): Filter by symbol
  - limit (int, default=50): Max results

Response:
{
  "alerts": [
    {
      "id": "uuid",
      "alert_type": "high_concentration",
      "severity": "medium",
      "symbol": "INFY",
      "description": "Position INFY represents 35.5% of portfolio",
      "metric_name": "position_concentration_pct",
      "metric_value": 35.5,
      "threshold": 30.0,
      "status": "pending_analysis",
      "created_at": "2026-09-02T13:17:00",
      "llm_analysis": null,
      "reviewed_at": null
    }
  ],
  "count": 1,
  "total_pending": 1
}
```

### Get Alert Details
```
GET /api/triggers/alerts/{alert_id}

Response:
{
  "id": "uuid",
  "alert_type": "high_concentration",
  "severity": "medium",
  ...full alert details...
}
```

### Analyze Alert with LLM
```
POST /api/triggers/alerts/{alert_id}/analyze

Response:
{
  "alert_id": "uuid",
  "analysis": {
    "raw_analysis": "Based on the alert...",
    "alert_type": "high_concentration",
    "severity": "medium",
    "timestamp": "2026-09-02T13:17:00"
  },
  "status": "analyzed"
}
```

### Analyze All Pending Alerts
```
POST /api/triggers/analyze-pending
Query params:
  - limit (int, default=10): Max alerts to analyze

Response:
{
  "analyses_run": 2,
  "results": [
    {
      "alert_id": "uuid",
      "analysis": {...},
      "status": "analyzed"
    }
  ]
}
```

### Mark Alert as Reviewed
```
POST /api/triggers/alerts/{alert_id}/review
Body:
{
  "action_taken": "Reduced INFY position by 50%"
}

Response:
{
  "id": "uuid",
  "status": "reviewed",
  "action_taken": "Reduced INFY position by 50%",
  "reviewed_at": "2026-09-02T13:17:00"
}
```

## Integration with Paper Trading

The trigger system is automatically integrated into the paper trading cycle:

1. Each time `run_paper_session()` runs, it executes `run_portfolio_checks()` at the end
2. Only runs if there are open positions in the portfolio
3. Automatically triggers LLM analysis on new alerts
4. Summary of alerts is included in paper session output

To run paper trading with trigger monitoring:
```bash
python run_paper.py
```

Check the session output for alert summaries, then review at `/api/triggers/alerts`.

## Configuration

Customize detection thresholds by calling the check endpoint:

```python
from src.triggers import run_portfolio_checks

result = run_portfolio_checks(
    thresholds={
        "max_drawdown_pct": 15.0,  # 15% instead of 10%
        "max_position_pct": 40.0,  # 40% instead of 30%
        "max_margin_pct": 70.0,    # 70% instead of 80%
        "max_positions": 8,        # 8 instead of 5
        "max_consecutive_losses": 5,  # 5 instead of 3
    },
    auto_analyze=True,
)
```

## Alert Lifecycle

1. **pending_analysis** → Alert created, awaiting LLM analysis
2. **analyzed** → LLM analysis complete, awaiting review
3. **reviewed** → User has reviewed and optionally taken action
4. **expired** → Alert expired after 72 hours without action

## Example Usage

### Check portfolio for issues:
```bash
curl -X POST http://localhost:8000/api/triggers/check
```

### List all analyzed alerts:
```bash
curl http://localhost:8000/api/triggers/alerts?status=analyzed
```

### Get LLM recommendation for a specific alert:
```bash
curl http://localhost:8000/api/triggers/alerts/{alert_id}
```

### Mark an alert as reviewed:
```bash
curl -X POST http://localhost:8000/api/triggers/alerts/{alert_id}/review \
  -H "Content-Type: application/json" \
  -d '{"action_taken": "Reduced position as recommended"}'
```

## Troubleshooting

### No alerts appearing
- Check if portfolio has open positions (`/api/triggers/alerts` only runs if positions exist)
- Run `POST /api/triggers/check` manually to trigger detection

### LLM analysis not working
- Verify `GROQ_API_KEY` is set in `.env`
- Check `/api/agent/health` to confirm Groq is configured
- Run analysis manually with `POST /api/triggers/alerts/{alert_id}/analyze`

### Alerts expiring
- Alerts expire after 72 hours without action
- Review and mark as reviewed to preserve history

## Safety Design

✓ **No auto-execution** - All triggers are for information only
✓ **LLM as advisor** - Recommendations require human judgment
✓ **Audit trail** - All alerts stored with analysis and action
✓ **Human control** - User must explicitly approve any actions
✓ **Paper-first** - Triggers run on paper portfolio before live
