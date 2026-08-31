"""Portfolio benchmarking tools."""

from __future__ import annotations

from typing import Any

from config import INITIAL_CAPITAL, MARKETS
from src import settings
from src.agent.tools import kite_tools
from src.backtest import run_backtest
from src.paper_report import build_paper_analysis
from src.rolling_analysis import calendar_month_pnl, rolling_30day_windows, run_full_analysis


def get_paper_portfolio_status(_args: dict[str, Any]) -> dict[str, Any]:
    analysis = build_paper_analysis()
    return {
        "equity": analysis["equity"],
        "cash": analysis["cash"],
        "unrealized_pnl": analysis["unrealized_pnl"],
        "total_return_pct": analysis["total_return_pct"],
        "today_pnl": analysis["today_pnl"],
        "week_pnl": analysis["week_pnl"],
        "month_pnl": analysis["month_pnl"],
        "open_positions": analysis["open_positions"],
        "recent_trades": analysis["recent_trades"][:10],
        "total_closed_trades": analysis["total_closed_trades"],
        "generated_at": str(analysis["generated_at"]),
        "source": "paper",
    }


def run_portfolio_backtest(args: dict[str, Any]) -> dict[str, Any]:
    refresh = args.get("refresh", False)
    result = run_backtest(refresh=refresh)
    equity_curve = result.get("equity_curve", [])
    trades = result.get("trades", [])
    final_equity = equity_curve[-1][1] if equity_curve else INITIAL_CAPITAL
    total_return_pct = (final_equity / INITIAL_CAPITAL - 1) * 100

    return {
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "total_pnl": round(final_equity - INITIAL_CAPITAL, 2),
        "trades_closed": len(trades),
        "winning_trades": sum(1 for t in trades if float(t.get("pnl", 0)) > 0),
        "markets": [m.symbol for m in MARKETS],
        "source": "backtest",
    }


def get_rolling_benchmark(args: dict[str, Any]) -> dict[str, Any]:
    refresh = args.get("refresh", False)
    analysis = run_full_analysis(refresh=refresh)
    backtest = analysis.get("backtest", {})
    equity_curve = backtest.get("equity_curve", [])
    trades = backtest.get("trades", [])

    rolling = analysis.get("rolling_30d")
    monthly = analysis.get("monthly_pnl")
    if rolling is None:
        rolling = rolling_30day_windows(equity_curve)
    if monthly is None:
        monthly = calendar_month_pnl(equity_curve, trades)

    rolling_rows = rolling.tail(5).to_dict(orient="records") if not rolling.empty else []
    monthly_rows = monthly.tail(6).to_dict(orient="records") if not monthly.empty else []

    return {
        "rolling_30d_windows": rolling_rows,
        "monthly_pnl": monthly_rows,
        "data_start": analysis.get("data_start"),
        "data_end": analysis.get("data_end"),
        "backtest_summary": {
            "final_equity": backtest.get("final_equity"),
            "total_return_pct": backtest.get("total_return_pct"),
            "num_trades": backtest.get("num_trades"),
        },
        "source": "rolling_analysis",
    }


def compare_portfolio_to_capital(args: dict[str, Any]) -> dict[str, Any]:
    source = args.get("source", "paper")

    if source == "kite":
        settings.load_settings()
        margins = kite_tools.get_margins({})
        equity_data = margins.get("margins", {}).get("equity", {})
        net = float(equity_data.get("net", 0) or 0)
        current_equity = net if net > 0 else float(equity_data.get("available", {}).get("live_balance", 0) or 0)
        portfolio_source = "kite"
    else:
        paper = get_paper_portfolio_status({})
        current_equity = float(paper["equity"])
        portfolio_source = "paper"

    total_return_pct = (current_equity / INITIAL_CAPITAL - 1) * 100
    return {
        "benchmark_capital": INITIAL_CAPITAL,
        "current_equity": round(current_equity, 2),
        "total_pnl": round(current_equity - INITIAL_CAPITAL, 2),
        "total_return_pct": round(total_return_pct, 2),
        "outperforms_benchmark": current_equity > INITIAL_CAPITAL,
        "source": portfolio_source,
    }
