"""Groq-powered agent chat loop with tool calling."""

from __future__ import annotations

import json
from typing import Any

from src import settings
from src.agent.registry import execute_tool, tool_schemas

SYSTEM_PROMPT = """You are Bharat Scout's in-app trading assistant for Indian equities.

## Product model
- **Paper trading** runs automatically to validate strategies on simulated capital.
- **Live trading** on Zerodha Kite NEVER happens without explicit user approval.
- You can analyze portfolios, run strategies, benchmark performance, and **propose** trades.
- You CANNOT approve or execute live trades. The user must approve at /approvals/.

## Tools
- Kite portfolio: get_profile, get_holdings, get_positions, get_margins
- Strategies: run_mean_reversion_strategy, run_momentum_breakout_strategy, run_trend_following_strategy, get_all_strategy_signals
- Tickers: get_ticker_quote, get_ticker_history, list_configured_tickers
- Benchmarking: get_paper_portfolio_status, run_portfolio_backtest, get_rolling_benchmark, compare_portfolio_to_capital
- Proposals: propose_trade (queues for approval), list_trade_proposals, get_trade_proposal
- Scripts: run_python_script, run_node_script (from scripts/sandbox/)

## Rules
1. Never claim a live trade was executed unless the user approved it at /approvals/.
2. When a strategy suggests action, explain it and use propose_trade if the user wants to go live.
3. Prefer paper portfolio tools for simulated performance; Kite tools for real holdings.
4. Be concise, cite numbers from tool results, and explain risks."""


def _serialize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return messages


def run_agent_chat(
    messages: list[dict[str, Any]],
    *,
    max_tool_rounds: int = 6,
) -> dict[str, Any]:
    """Run agent chat with tool calling. Returns assistant reply and tool trace."""
    settings.load_settings()
    api_key = settings.groq_api_key()
    if not api_key:
        return {
            "reply": (
                "GROQ_API_KEY is not configured. Add it to .env to enable the in-app assistant. "
                "Tools are available but the LLM cannot run without an API key."
            ),
            "tools_used": [],
            "error": "missing_groq_key",
        }

    from groq import Groq

    client = Groq(api_key=api_key)
    model = settings.groq_model()
    tools = tool_schemas()
    tools_used: list[dict[str, Any]] = []

    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    for _ in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = response.choices[0]
        assistant_message = choice.message

        if assistant_message.tool_calls:
            chat_messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_message.tool_calls
                    ],
                }
            )

            for tool_call in assistant_message.tool_calls:
                name = tool_call.function.name
                args_raw = tool_call.function.arguments or "{}"
                result = execute_tool(name, args_raw)
                entry: dict[str, Any] = {
                    "tool": name,
                    "arguments": args_raw,
                    "result_preview": result[:500],
                }
                if name in ("propose_trade", "list_trade_proposals", "get_trade_proposal"):
                    try:
                        entry["result"] = json.loads(result)
                    except json.JSONDecodeError:
                        pass
                tools_used.append(entry)
                chat_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
            continue

        reply = assistant_message.content or ""
        return {"reply": reply, "tools_used": tools_used, "model": model}

    return {
        "reply": "I reached the maximum number of tool calls. Please ask a simpler question.",
        "tools_used": tools_used,
        "model": model,
    }


def list_available_tools() -> list[dict[str, str]]:
    return [
        {"name": t["function"]["name"], "description": t["function"]["description"]}
        for t in tool_schemas()
    ]
