"""Rule-based + LLM risk governor for paper trading entries."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from config import CORRELATION_GROUPS, INITIAL_CAPITAL, MARKETS
from src import settings
from src.db import all_trades, get_state, get_today_realized_pnl, set_state
from src.risk import Portfolio, portfolio_equity
from src.trade_reasons import entry_reason, symbol_label

ACTION_MULTIPLIERS = {
    "neutral": 1.0,
    "reduce_risk": 0.5,
    "increase_risk": 1.25,
    "block": 1.0,
}
MIN_MULTIPLIER = 0.25
MAX_MULTIPLIER = 1.25
VALID_ACTIONS = frozenset(ACTION_MULTIPLIERS)


@dataclass
class MarketSignal:
    symbol: str
    name: str
    strategy: str
    interval: str
    group: str
    bar_time: str
    price: float
    atr: float
    signal: int
    signal_label: str
    entry_reason_text: str
    has_position: bool
    position_side: str | None = None


@dataclass
class RiskDecision:
    action: str = "neutral"
    risk_multiplier: float = 1.0
    block_new_entries: bool = False
    reason: str = "Default neutral posture."
    confidence: str = "medium"
    source: str = "rules"
    rule_baseline: dict = field(default_factory=dict)
    llm_raw: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _signal_label(signal: int) -> str:
    if signal == 1:
        return "long"
    if signal == -1:
        return "short"
    return "flat"


def _consecutive_losses(trades: list[dict], n: int = 5) -> int:
    streak = 0
    for t in reversed(trades[-n:]):
        if float(t["pnl"]) < 0:
            streak += 1
        else:
            break
    return streak


def _losses_in_last_n(trades: list[dict], n: int = 5) -> int:
    return sum(1 for t in trades[-n:] if float(t["pnl"]) < 0)


def _peak_equity() -> float:
    raw = get_state("peak_equity", "")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return INITIAL_CAPITAL


def _update_peak_equity(equity: float) -> float:
    peak = max(_peak_equity(), equity)
    set_state("peak_equity", f"{peak:.2f}")
    return peak


def build_governor_context(
    portfolio: Portfolio,
    *,
    market_rows: list[dict],
    prices: dict[str, float],
) -> dict:
    equity = portfolio_equity(portfolio, prices)
    peak = _update_peak_equity(equity)
    drawdown_pct = ((equity / peak) - 1) * 100 if peak else 0.0

    db_trades = all_trades(run_type="paper")
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def period_pnl(start: date) -> float:
        total = 0.0
        for t in db_trades:
            exit_day = str(t["exit_time"])[:10]
            if start.isoformat() <= exit_day <= today.isoformat():
                total += float(t["pnl"])
        return total

    open_positions = []
    for sym, pos in portfolio.positions.items():
        mark = prices.get(sym, pos.entry_price)
        u_pnl = (mark - pos.entry_price) * pos.quantity * pos.side
        open_positions.append(
            {
                "symbol": sym,
                "name": symbol_label(sym),
                "side": "long" if pos.side == 1 else "short",
                "entry_price": pos.entry_price,
                "mark_price": mark,
                "quantity": pos.quantity,
                "unrealized_pnl": round(u_pnl, 2),
                "entry_reason": pos.entry_reason,
                "group": pos.group,
            }
        )

    vedanta_longs = [
        p for p in open_positions if p["symbol"] in CORRELATION_GROUPS.get("vedanta", [])
    ]

    signals = []
    for row in market_rows:
        sig = int(row.get("signal", 0) or 0)
        m = row["market"]
        signals.append(
            MarketSignal(
                symbol=m.symbol,
                name=m.name,
                strategy=m.strategy,
                interval=m.interval,
                group=m.group,
                bar_time=str(row["ts"]),
                price=float(row["price"]),
                atr=float(row.get("atr", 0) or 0),
                signal=sig,
                signal_label=_signal_label(sig),
                entry_reason_text=row.get("entry_reason_text", ""),
                has_position=m.symbol in portfolio.positions,
                position_side=(
                    "long"
                    if portfolio.positions[m.symbol].side == 1
                    else "short"
                )
                if m.symbol in portfolio.positions
                else None,
            )
        )

    pending_entries = [
        s for s in signals if s.signal != 0 and not s.has_position and s.atr > 0
    ]

    recent = db_trades[-15:]
    recent_payload = [
        {
            "symbol": symbol_label(t["symbol"]),
            "side": t["side"],
            "pnl": round(float(t["pnl"]), 2),
            "return_pct": round(float(t["return_pct"]), 2),
            "exit_time": str(t["exit_time"])[:16],
            "reason": t.get("reason", ""),
        }
        for t in recent
    ]

    return {
        "equity": round(equity, 2),
        "cash": round(portfolio.cash, 2),
        "initial_capital": INITIAL_CAPITAL,
        "unrealized_pnl": round(
            sum(p["unrealized_pnl"] for p in open_positions), 2
        ),
        "total_return_pct": round((equity / INITIAL_CAPITAL - 1) * 100, 2),
        "today_realized_pnl": round(get_today_realized_pnl(), 2),
        "week_realized_pnl": round(period_pnl(week_start), 2),
        "month_realized_pnl": round(period_pnl(month_start), 2),
        "drawdown_from_peak_pct": round(drawdown_pct, 2),
        "peak_equity": round(peak, 2),
        "open_position_count": len(open_positions),
        "vedanta_long_count": len(vedanta_longs),
        "consecutive_losses": _consecutive_losses(db_trades),
        "losses_in_last_5": _losses_in_last_n(db_trades, 5),
        "open_positions": open_positions,
        "signals": [asdict(s) for s in signals],
        "pending_entries": [asdict(s) for s in pending_entries],
        "recent_trades": recent_payload,
        "max_daily_loss": settings.max_daily_loss(),
    }


def apply_rule_baseline(context: dict) -> RiskDecision:
    """Hard safety rules that can force block or minimum reduction."""
    today_pnl = context["today_realized_pnl"]
    max_loss = context["max_daily_loss"]
    consecutive = context["consecutive_losses"]
    losses_5 = context["losses_in_last_5"]
    drawdown = context["drawdown_from_peak_pct"]
    pending = context["pending_entries"]

    if today_pnl <= -max_loss:
        return RiskDecision(
            action="block",
            risk_multiplier=1.0,
            block_new_entries=True,
            reason=(
                f"Daily loss limit reached (Rs {today_pnl:,.0f} vs "
                f"limit Rs {-max_loss:,.0f})."
            ),
            confidence="high",
            source="rules",
        )

    if today_pnl <= -max_loss * 0.75:
        return RiskDecision(
            action="reduce_risk",
            risk_multiplier=0.5,
            block_new_entries=False,
            reason=(
                f"Approaching daily loss limit (Rs {today_pnl:,.0f}); "
                "cutting new entry size in half."
            ),
            confidence="high",
            source="rules",
        )

    if drawdown <= -8:
        return RiskDecision(
            action="block",
            risk_multiplier=1.0,
            block_new_entries=True,
            reason=f"Drawdown from peak is {drawdown:.1f}% (>= 8% block threshold).",
            confidence="high",
            source="rules",
        )

    if drawdown <= -5:
        return RiskDecision(
            action="reduce_risk",
            risk_multiplier=0.5,
            block_new_entries=False,
            reason=f"Drawdown from peak is {drawdown:.1f}%; reducing new entry risk.",
            confidence="high",
            source="rules",
        )

    if consecutive >= 3:
        return RiskDecision(
            action="reduce_risk",
            risk_multiplier=0.5,
            block_new_entries=False,
            reason=f"{consecutive} consecutive losing trades; reducing risk.",
            confidence="high",
            source="rules",
        )

    if losses_5 >= 4:
        return RiskDecision(
            action="reduce_risk",
            risk_multiplier=0.75,
            block_new_entries=False,
            reason=f"{losses_5} losses in the last 5 trades; slight risk reduction.",
            confidence="medium",
            source="rules",
        )

    if context["vedanta_long_count"] >= 1 and len(
        [p for p in pending if p.get("group") == "vedanta"]
    ) >= 1:
        return RiskDecision(
            action="reduce_risk",
            risk_multiplier=0.75,
            block_new_entries=False,
            reason="Vedanta group exposure already on; cautious on new Vedanta entries.",
            confidence="medium",
            source="rules",
        )

    if not pending:
        return RiskDecision(
            action="neutral",
            risk_multiplier=1.0,
            block_new_entries=False,
            reason="No pending entry signals; neutral posture.",
            confidence="high",
            source="rules",
        )

    return RiskDecision(
        action="neutral",
        risk_multiplier=1.0,
        block_new_entries=False,
        reason="Risk metrics within normal bounds.",
        confidence="medium",
        source="rules",
    )


def _clamp_multiplier(value: float) -> float:
    return max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, value))


def _parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _normalize_llm_decision(payload: dict) -> RiskDecision:
    action = str(payload.get("action", "neutral")).lower().replace(" ", "_")
    if action not in VALID_ACTIONS:
        action = "neutral"

    multiplier = float(payload.get("risk_multiplier", ACTION_MULTIPLIERS[action]))
    multiplier = _clamp_multiplier(multiplier)

    block = bool(payload.get("block_new_entries", action == "block"))
    if action == "block":
        block = True

    if action == "reduce_risk":
        multiplier = min(multiplier, 0.75)
    elif action == "increase_risk":
        multiplier = max(multiplier, 1.0)
        multiplier = min(multiplier, MAX_MULTIPLIER)
    elif action == "neutral":
        multiplier = 1.0

    return RiskDecision(
        action=action,
        risk_multiplier=multiplier,
        block_new_entries=block,
        reason=str(payload.get("reason", "LLM risk assessment."))[:500],
        confidence=str(payload.get("confidence", "medium"))[:20],
        source="llm",
        llm_raw=payload,
    )


def call_groq_governor(context: dict, *, rule_baseline: RiskDecision) -> RiskDecision:
    from groq import Groq

    api_key = settings.groq_api_key()
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured")

    client = Groq(api_key=api_key)
    model = settings.groq_model()

    system_prompt = """You are a risk governor for an Indian NSE paper-trading bot.
You do NOT pick stocks or directions. Strategy code already produced signals.
Your job: set portfolio risk posture for NEW entries only.

Respond with JSON only:
{
  "action": "reduce_risk" | "neutral" | "increase_risk" | "block",
  "risk_multiplier": number between 0.25 and 1.25,
  "block_new_entries": boolean,
  "reason": "one or two sentences",
  "confidence": "low" | "medium" | "high"
}

Guidelines:
- block: unsafe to open new positions (heavy losses, conflicting signals, extreme drawdown)
- reduce_risk: caution; use multiplier 0.5-0.75
- neutral: normal conditions; multiplier 1.0
- increase_risk: only when recent performance is stable and signals align; max multiplier 1.25
- Never recommend ignoring stops or exceeding risk limits
- Exits on open positions are handled separately; focus on new entries"""

    user_payload = {
        "portfolio": {
            "equity": context["equity"],
            "cash": context["cash"],
            "total_return_pct": context["total_return_pct"],
            "today_realized_pnl": context["today_realized_pnl"],
            "week_realized_pnl": context["week_realized_pnl"],
            "month_realized_pnl": context["month_realized_pnl"],
            "drawdown_from_peak_pct": context["drawdown_from_peak_pct"],
            "open_position_count": context["open_position_count"],
            "vedanta_long_count": context["vedanta_long_count"],
            "consecutive_losses": context["consecutive_losses"],
            "losses_in_last_5": context["losses_in_last_5"],
        },
        "open_positions": context["open_positions"],
        "signals": context["signals"],
        "pending_entries": context["pending_entries"],
        "recent_trades": context["recent_trades"],
        "rule_baseline": rule_baseline.to_dict(),
    }

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Assess risk for new entries given this state:\n"
                    + json.dumps(user_payload, indent=2)
                ),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = _parse_llm_json(content)
    decision = _normalize_llm_decision(payload)
    decision.rule_baseline = rule_baseline.to_dict()
    return decision


def merge_decisions(rule: RiskDecision, llm: RiskDecision) -> RiskDecision:
    """Rules can force block/reduction; LLM adjusts within safe bounds."""
    if rule.block_new_entries:
        merged = RiskDecision(
            action="block",
            risk_multiplier=rule.risk_multiplier,
            block_new_entries=True,
            reason=f"Rule override: {rule.reason}",
            confidence=rule.confidence,
            source="rules+llm",
            rule_baseline=rule.to_dict(),
            llm_raw=llm.llm_raw,
        )
        if llm.reason:
            merged.reason += f" LLM agreed: {llm.reason}"
        return merged

    if rule.action == "reduce_risk":
        multiplier = min(rule.risk_multiplier, llm.risk_multiplier)
        action = "reduce_risk" if multiplier < 1.0 else llm.action
        if llm.block_new_entries:
            return RiskDecision(
                action="block",
                risk_multiplier=multiplier,
                block_new_entries=True,
                reason=f"LLM block: {llm.reason} (rules: {rule.reason})",
                confidence=llm.confidence,
                source="rules+llm",
                rule_baseline=rule.to_dict(),
                llm_raw=llm.llm_raw,
            )
        return RiskDecision(
            action=action,
            risk_multiplier=_clamp_multiplier(multiplier),
            block_new_entries=False,
            reason=f"LLM: {llm.reason} | Rules: {rule.reason}",
            confidence=llm.confidence,
            source="rules+llm",
            rule_baseline=rule.to_dict(),
            llm_raw=llm.llm_raw,
        )

    if llm.block_new_entries:
        return RiskDecision(
            action="block",
            risk_multiplier=llm.risk_multiplier,
            block_new_entries=True,
            reason=llm.reason,
            confidence=llm.confidence,
            source="rules+llm",
            rule_baseline=rule.to_dict(),
            llm_raw=llm.llm_raw,
        )

    return RiskDecision(
        action=llm.action,
        risk_multiplier=_clamp_multiplier(llm.risk_multiplier),
        block_new_entries=False,
        reason=llm.reason,
        confidence=llm.confidence,
        source="rules+llm",
        rule_baseline=rule.to_dict(),
        llm_raw=llm.llm_raw,
    )


def evaluate_risk_governor(context: dict) -> RiskDecision:
    rule = apply_rule_baseline(context)
    rule.rule_baseline = rule.to_dict()

    if not settings.llm_risk_governor_enabled():
        record_risk_decision(rule)
        return rule

    if not settings.groq_api_key():
        rule.reason += " (LLM disabled: GROQ_API_KEY missing)"
        record_risk_decision(rule)
        return rule

    try:
        llm = call_groq_governor(context, rule_baseline=rule)
        final = merge_decisions(rule, llm)
        record_risk_decision(final)
        return final
    except Exception as exc:
        fallback = RiskDecision(
            action=rule.action,
            risk_multiplier=rule.risk_multiplier,
            block_new_entries=rule.block_new_entries,
            reason=f"{rule.reason} (LLM fallback: {exc})",
            confidence=rule.confidence,
            source="rules",
            rule_baseline=rule.to_dict(),
        )
        record_risk_decision(fallback)
        return fallback


def record_risk_decision(decision: RiskDecision) -> None:
    set_state("last_risk_decision", json.dumps(decision.to_dict()))


def load_last_risk_decision() -> dict | None:
    raw = get_state("last_risk_decision", "")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def format_risk_decision(decision: RiskDecision | dict) -> str:
    d = decision if isinstance(decision, dict) else decision.to_dict()
    lines = [
        "RISK GOVERNOR",
        "-" * 62,
        f"  Action         : {d.get('action', 'neutral')}",
        f"  Risk multiplier: {d.get('risk_multiplier', 1.0):.2f}x",
        f"  Block entries  : {'yes' if d.get('block_new_entries') else 'no'}",
        f"  Source         : {d.get('source', 'n/a')}",
        f"  Confidence     : {d.get('confidence', 'n/a')}",
        f"  Reason         : {d.get('reason', '')}",
    ]
    return "\n".join(lines)
