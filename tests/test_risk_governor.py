"""Tests for LLM risk governor."""

from unittest.mock import MagicMock, patch

import pytest

from src.risk_governor import (
    RiskDecision,
    _normalize_llm_decision,
    apply_rule_baseline,
    merge_decisions,
)


def test_normalize_llm_block():
    d = _normalize_llm_decision(
        {
            "action": "block",
            "risk_multiplier": 1.0,
            "block_new_entries": True,
            "reason": "Too many losses.",
            "confidence": "high",
        }
    )
    assert d.action == "block"
    assert d.block_new_entries is True


def test_normalize_llm_increase_capped():
    d = _normalize_llm_decision(
        {
            "action": "increase_risk",
            "risk_multiplier": 2.0,
            "block_new_entries": False,
            "reason": "Strong trend.",
            "confidence": "medium",
        }
    )
    assert d.action == "increase_risk"
    assert d.risk_multiplier <= 1.25


def test_rule_baseline_blocks_on_daily_loss():
    ctx = {
        "today_realized_pnl": -2500,
        "max_daily_loss": 2000,
        "consecutive_losses": 0,
        "losses_in_last_5": 0,
        "drawdown_from_peak_pct": -1,
        "vedanta_long_count": 0,
        "pending_entries": [{"group": "vedanta"}],
    }
    d = apply_rule_baseline(ctx)
    assert d.block_new_entries is True
    assert d.action == "block"


def test_merge_rules_block_overrides_llm_increase():
    rule = RiskDecision(
        action="block",
        block_new_entries=True,
        reason="Daily loss limit",
    )
    llm = RiskDecision(
        action="increase_risk",
        risk_multiplier=1.25,
        block_new_entries=False,
        reason="Markets look good",
        llm_raw={"action": "increase_risk"},
    )
    merged = merge_decisions(rule, llm)
    assert merged.block_new_entries is True
    assert merged.action == "block"


def test_merge_llm_can_block_when_rules_neutral():
    rule = RiskDecision(action="neutral", risk_multiplier=1.0)
    llm = RiskDecision(
        action="block",
        block_new_entries=True,
        reason="Conflicting Vedanta signals",
        llm_raw={},
    )
    merged = merge_decisions(rule, llm)
    assert merged.block_new_entries is True


@patch("src.risk_governor.settings.groq_api_key", return_value="test-key")
@patch("src.risk_governor.settings.groq_model", return_value="llama-3.3-70b-versatile")
def test_call_groq_governor_parses_response(mock_model, mock_key):
    from src.risk_governor import call_groq_governor

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    '{"action":"reduce_risk","risk_multiplier":0.5,'
                    '"block_new_entries":false,"reason":"Recent losses",'
                    '"confidence":"high"}'
                )
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    rule = RiskDecision(action="neutral", risk_multiplier=1.0)
    context = {
        "equity": 100000,
        "cash": 50000,
        "total_return_pct": 0,
        "today_realized_pnl": -500,
        "week_realized_pnl": -500,
        "month_realized_pnl": -500,
        "drawdown_from_peak_pct": -1,
        "open_position_count": 1,
        "vedanta_long_count": 1,
        "consecutive_losses": 2,
        "losses_in_last_5": 2,
        "open_positions": [],
        "signals": [],
        "pending_entries": [],
        "recent_trades": [],
    }

    with patch("groq.Groq", return_value=mock_client):
        decision = call_groq_governor(context, rule_baseline=rule)

    assert decision.action == "reduce_risk"
    assert decision.risk_multiplier == 0.5
    assert "losses" in decision.reason.lower()
