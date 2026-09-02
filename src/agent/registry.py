"""Tool schemas and dispatch for the in-app trading assistant."""

from __future__ import annotations

import json
from typing import Any, Callable

from src.agent.tools import benchmark, kite_tools, proposals, scripts, strategies, tickers

ToolHandler = Callable[[dict[str, Any]], Any]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    # Kite portfolio (mirrors Kite MCP tool names)
    "get_profile": kite_tools.get_profile,
    "get_holdings": kite_tools.get_holdings,
    "get_positions": kite_tools.get_positions,
    "get_margins": kite_tools.get_margins,
    # Strategy tools (one per strategy)
    "run_mean_reversion_strategy": strategies.run_mean_reversion_strategy,
    "run_momentum_breakout_strategy": strategies.run_momentum_breakout_strategy,
    "run_trend_following_strategy": strategies.run_trend_following_strategy,
    "get_all_strategy_signals": strategies.get_all_strategy_signals,
    "get_screener_snapshot": strategies.get_screener_snapshot,
    "create_strategy_from_prompt": strategies.create_strategy_from_prompt,
    "list_saved_strategies": strategies.list_saved_strategies,
    # Ticker tools
    "get_ticker_quote": tickers.get_ticker_quote,
    "get_ticker_history": tickers.get_ticker_history,
    "list_configured_tickers": tickers.list_configured_tickers,
    # Portfolio benchmarking
    "get_paper_portfolio_status": benchmark.get_paper_portfolio_status,
    "run_portfolio_backtest": benchmark.run_portfolio_backtest,
    "get_rolling_benchmark": benchmark.get_rolling_benchmark,
    "compare_portfolio_to_capital": benchmark.compare_portfolio_to_capital,
    # Trade proposals (human approval required before live execution)
    "propose_trade": proposals.propose_trade,
    "list_trade_proposals": proposals.list_trade_proposals,
    "get_trade_proposal": proposals.get_trade_proposal,
    # Script runner
    "run_python_script": scripts.run_python_script,
    "run_node_script": scripts.run_node_script,
}


def tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-compatible tool definitions for Groq function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_profile",
                "description": "Get Zerodha Kite user profile (name, email, broker). Requires Kite credentials in .env.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_holdings",
                "description": "Get long-term portfolio holdings from Kite (CNC/delivery positions).",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_positions",
                "description": "Get current day and net trading positions from Kite with unrealized P&L.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_margins",
                "description": "Get Kite account margins: available cash, collateral, and utilization.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_mean_reversion_strategy",
                "description": "Run mean-reversion strategy (Bollinger + RSI) on a ticker and return latest signal.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "NSE symbol e.g. VAML.NS or VEDL.NS",
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Refresh market data cache",
                            "default": False,
                        },
                    },
                    "required": ["symbol"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_momentum_breakout_strategy",
                "description": "Run momentum breakout strategy (range breakout + volume) on a ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["symbol"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_trend_following_strategy",
                "description": "Run trend-following strategy (EMA crossover) on a ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["symbol"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_all_strategy_signals",
                "description": "Run each configured market's assigned strategy and return all latest signals.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "refresh": {"type": "boolean", "default": False},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_screener_snapshot",
                "description": "Read the screener's current watchlist and company fundamentals so the agent can analyze opportunities and design strategies from real market context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of symbols to inspect; defaults to the screener watchlist.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_strategy_from_prompt",
                "description": "Create a saved custom strategy from a pasted strategy prompt so it can be used in the next paper trading session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Friendly name for the strategy"},
                        "strategy": {"type": "string", "description": "Natural-language strategy prompt describing the logic"},
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional symbols this strategy should apply to",
                        },
                    },
                    "required": ["strategy"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_saved_strategies",
                "description": "List the custom strategies saved by the agent so you can review, enable, or reuse them.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_ticker_quote",
                "description": "Get latest quote (LTP, change) for an NSE ticker via yfinance or Kite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "use_kite": {"type": "boolean", "default": False},
                    },
                    "required": ["symbol"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_ticker_history",
                "description": "Get recent OHLCV bars for a ticker at a given interval (15m, 1h, 4h).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "interval": {
                            "type": "string",
                            "enum": ["15m", "1h", "4h"],
                            "default": "1h",
                        },
                        "bars": {"type": "integer", "default": 20, "minimum": 5, "maximum": 100},
                        "refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["symbol"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_configured_tickers",
                "description": "List all tickers configured in the trading bot with strategy and interval.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_paper_portfolio_status",
                "description": "Get paper-trading portfolio snapshot: equity, P&L, open positions, recent trades.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_portfolio_backtest",
                "description": "Run historical backtest across all configured markets and return summary metrics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "refresh": {"type": "boolean", "default": False},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_rolling_benchmark",
                "description": "Rolling 30-day backtest benchmark windows and monthly P&L breakdown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "refresh": {"type": "boolean", "default": False},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_portfolio_to_capital",
                "description": "Compare current paper or Kite portfolio equity against initial capital benchmark.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "enum": ["paper", "kite"],
                            "default": "paper",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_trade",
                "description": "Queue a live trade for user approval. Does NOT execute on Kite. User must approve at /approvals/.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["enter", "exit"]},
                        "symbol": {"type": "string"},
                        "side": {"type": "string", "enum": ["long", "short"]},
                        "quantity": {"type": "number"},
                        "price": {"type": "number"},
                        "stop_price": {"type": "number"},
                        "reason": {"type": "string"},
                        "strategy": {"type": "string"},
                    },
                    "required": ["action", "symbol", "side", "quantity"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_trade_proposals",
                "description": "List trade proposals awaiting or past user approval. Assistant cannot approve trades.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "approved", "rejected", "executed", "expired", "all"],
                            "default": "pending",
                        },
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_trade_proposal",
                "description": "Get details of a single trade proposal by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "proposal_id": {"type": "string"},
                    },
                    "required": ["proposal_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_python_script",
                "description": "Run a Python script from scripts/sandbox/. Returns stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Script filename e.g. my_analysis.py",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional CLI arguments",
                        },
                    },
                    "required": ["filename"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_node_script",
                "description": "Run a Node.js script from scripts/sandbox/. Returns stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "args": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["filename"],
                },
            },
        },
    ]


def execute_tool(name: str, arguments: dict[str, Any] | str | None) -> str:
    """Run a tool and return JSON string result."""
    if name not in TOOL_HANDLERS:
        return json.dumps({"error": f"Unknown tool: {name}"})

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            arguments = {}

    arguments = arguments or {}

    try:
        result = TOOL_HANDLERS[name](arguments)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": name})
