"""Groq-powered agent chat loop with tool calling."""

from __future__ import annotations

import json
from typing import Any

from src import settings
from src.agent.registry import execute_tool, tool_schemas

SYSTEM_PROMPT = """You are Bharat Scout's in-app trading assistant for Indian equities.

You have tools to:
- Read live Kite portfolio (holdings, positions, margins, profile) — same surface as Kite MCP
- Run trading strategies (mean reversion, momentum breakout, trend following) on configured tickers
- Fetch ticker quotes and OHLCV history
- Benchmark paper portfolio and run backtests
- Execute custom Python/Node scripts from scripts/sandbox/

When answering portfolio questions:
1. Use Kite tools for live Zerodha account data
2. Use get_paper_portfolio_status for paper-trading portfolio
3. Use strategy tools to analyze signals before recommending actions
4. Use benchmark tools for performance comparisons vs initial capital

Be concise, cite numbers from tool results, and explain risks. Never invent portfolio data."""


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
                tools_used.append({"tool": name, "arguments": args_raw, "result_preview": result[:500]})
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
