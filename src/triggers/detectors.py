"""Outlier detection rules for portfolio monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.risk import Portfolio, Position


def _calc_portfolio_equity(
    portfolio: Portfolio,
    prices: dict[str, float] | None = None,
) -> float:
    """Calculate portfolio equity using prices or entry prices as fallback."""
    if prices is None:
        prices = {}

    equity = portfolio.cash
    for sym, pos in portfolio.positions.items():
        price = prices.get(sym, pos.entry_price)
        if pos.side == 1:
            equity += pos.quantity * price
        else:
            equity -= pos.quantity * price
    return equity


@dataclass
class DetectionResult:
    triggered: bool
    alert_type: str
    severity: str  # "low", "medium", "high", "critical"
    metric_name: str
    metric_value: float
    threshold: float
    description: str
    symbol: str | None = None
    raw_data: dict | None = None


def check_drawdown(
    portfolio: Portfolio,
    initial_capital: float,
    max_drawdown_pct: float = 10.0,
) -> DetectionResult | None:
    """Detect if paper portfolio has exceeded max drawdown."""
    current_equity = _calc_portfolio_equity(portfolio)
    max_equity = initial_capital

    for trade in portfolio.trades:
        cumulative = initial_capital + sum(t.get("pnl", 0) for t in portfolio.trades[:portfolio.trades.index(trade) + 1])
        if cumulative > max_equity:
            max_equity = cumulative

    if max_equity == 0:
        return None

    drawdown = ((max_equity - current_equity) / max_equity) * 100

    if drawdown > max_drawdown_pct:
        return DetectionResult(
            triggered=True,
            alert_type="high_drawdown",
            severity="high" if drawdown > 20 else "medium",
            metric_name="drawdown_pct",
            metric_value=drawdown,
            threshold=max_drawdown_pct,
            description=f"Portfolio drawdown {drawdown:.2f}% exceeds threshold {max_drawdown_pct}%",
            raw_data={
                "current_equity": current_equity,
                "max_equity": max_equity,
                "initial_capital": initial_capital,
            },
        )

    return None


def check_position_concentration(
    portfolio: Portfolio,
    max_position_pct: float = 30.0,
) -> list[DetectionResult]:
    """Detect if any single position is too concentrated."""
    current_equity = _calc_portfolio_equity(portfolio)
    results = []

    if current_equity <= 0:
        return results

    for symbol, position in portfolio.positions.items():
        position_value = position.entry_price * position.quantity
        position_pct = (position_value / current_equity) * 100

        if position_pct > max_position_pct:
            results.append(
                DetectionResult(
                    triggered=True,
                    alert_type="high_concentration",
                    severity="high" if position_pct > 50 else "medium",
                    metric_name="position_concentration_pct",
                    metric_value=position_pct,
                    threshold=max_position_pct,
                    description=f"Position {symbol} represents {position_pct:.2f}% of portfolio",
                    symbol=symbol,
                    raw_data={
                        "position_value": position_value,
                        "portfolio_equity": current_equity,
                        "entry_price": position.entry_price,
                        "quantity": position.quantity,
                    },
                )
            )

    return results


def check_margin_usage(
    portfolio: Portfolio,
    max_margin_pct: float = 80.0,
) -> DetectionResult | None:
    """Detect if margin usage is too high (approximated by cash ratio)."""
    current_equity = _calc_portfolio_equity(portfolio)

    if current_equity <= 0:
        return None

    cash_ratio = (portfolio.cash / current_equity) * 100
    margin_usage = 100 - cash_ratio

    if margin_usage > max_margin_pct:
        return DetectionResult(
            triggered=True,
            alert_type="high_margin_usage",
            severity="critical" if margin_usage > 95 else "high",
            metric_name="margin_usage_pct",
            metric_value=margin_usage,
            threshold=max_margin_pct,
            description=f"Margin usage {margin_usage:.2f}% exceeds safe threshold {max_margin_pct}%",
            raw_data={
                "cash": portfolio.cash,
                "portfolio_equity": current_equity,
                "cash_ratio": cash_ratio,
            },
        )

    return None


def check_too_many_positions(
    portfolio: Portfolio,
    max_positions: int = 5,
) -> DetectionResult | None:
    """Detect if portfolio has too many open positions."""
    num_positions = len(portfolio.positions)

    if num_positions > max_positions:
        return DetectionResult(
            triggered=True,
            alert_type="too_many_positions",
            severity="medium",
            metric_name="num_open_positions",
            metric_value=float(num_positions),
            threshold=float(max_positions),
            description=f"Portfolio has {num_positions} open positions, exceeds recommended {max_positions}",
            raw_data={
                "symbols": list(portfolio.positions.keys()),
            },
        )

    return None


def check_losing_streak(
    portfolio: Portfolio,
    max_consecutive_losses: int = 3,
) -> DetectionResult | None:
    """Detect if there's a losing streak in recent trades."""
    if not portfolio.trades:
        return None

    recent_trades = portfolio.trades[-10:]  # Check last 10 trades
    consecutive_losses = 0
    max_streak = 0

    for trade in recent_trades:
        if trade.get("pnl", 0) < 0:
            consecutive_losses += 1
            max_streak = max(max_streak, consecutive_losses)
        else:
            consecutive_losses = 0

    if max_streak >= max_consecutive_losses:
        return DetectionResult(
            triggered=True,
            alert_type="losing_streak",
            severity="high",
            metric_name="consecutive_losses",
            metric_value=float(max_streak),
            threshold=float(max_consecutive_losses),
            description=f"Detected {max_streak} consecutive losing trades",
            raw_data={
                "recent_trades": [
                    {
                        "symbol": t.get("symbol"),
                        "pnl": t.get("pnl"),
                        "exit_reason": t.get("exit_reason"),
                    }
                    for t in recent_trades
                ],
            },
        )

    return None


def run_all_detectors(
    portfolio: Portfolio,
    initial_capital: float,
    thresholds: dict | None = None,
) -> list[DetectionResult]:
    """Run all detectors and return triggered alerts."""
    if thresholds is None:
        thresholds = {}

    alerts = []

    # Check drawdown
    dd_result = check_drawdown(
        portfolio,
        initial_capital,
        max_drawdown_pct=thresholds.get("max_drawdown_pct", 10.0),
    )
    if dd_result:
        alerts.append(dd_result)

    # Check concentration
    alerts.extend(
        check_position_concentration(
            portfolio,
            max_position_pct=thresholds.get("max_position_pct", 30.0),
        )
    )

    # Check margin usage
    margin_result = check_margin_usage(
        portfolio,
        max_margin_pct=thresholds.get("max_margin_pct", 80.0),
    )
    if margin_result:
        alerts.append(margin_result)

    # Check position count
    pos_result = check_too_many_positions(
        portfolio,
        max_positions=thresholds.get("max_positions", 5),
    )
    if pos_result:
        alerts.append(pos_result)

    # Check losing streak
    streak_result = check_losing_streak(
        portfolio,
        max_consecutive_losses=thresholds.get("max_consecutive_losses", 3),
    )
    if streak_result:
        alerts.append(streak_result)

    return alerts
