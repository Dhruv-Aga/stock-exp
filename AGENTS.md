# Agent instructions

## In-app trading assistant

The application includes an **in-app LLM assistant** at `/assistant/` that uses Groq tool-calling to answer portfolio and strategy questions. It is **not** limited to Cursor IDE — it runs as part of the app.

### Architecture

```
Browser (/assistant/)  →  POST /api/agent/chat  →  Groq LLM + tool loop
                                                      ↓
                                              src/agent/tools/*
                                              (Kite, strategies, tickers, benchmark, scripts)
```

Start the agent API:

```bash
python3 run_agent_api.py   # port 8000
python3 -m http.server 8080
```

Open `http://localhost:8080/assistant/`.

### Required configuration

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Powers the in-app LLM (required for chat) |
| `GROQ_MODEL` | Optional, default `llama-3.3-70b-versatile` |
| `KITE_API_KEY` | Live portfolio tools via Kite Connect |
| `KITE_API_SECRET` | Kite OAuth |
| `KITE_ACCESS_TOKEN` | Daily token from `python run_kite_login.py` |

### Available tools (17)

**Kite portfolio** (mirrors Kite MCP surface via Kite Connect):
- `get_profile`, `get_holdings`, `get_positions`, `get_margins`

**Trading strategies** (one tool per strategy):
- `run_mean_reversion_strategy`
- `run_momentum_breakout_strategy`
- `run_trend_following_strategy`
- `get_all_strategy_signals`

**Tickers:**
- `get_ticker_quote`, `get_ticker_history`, `list_configured_tickers`

**Portfolio benchmarking:**
- `get_paper_portfolio_status`
- `run_portfolio_backtest`
- `get_rolling_benchmark`
- `compare_portfolio_to_capital`

**Script runner:**
- `run_python_script` — runs `.py` files from `scripts/sandbox/`
- `run_node_script` — runs `.js` files from `scripts/sandbox/`

### Example queries

- "What's my Kite portfolio P&L?" → `get_positions`, `get_holdings`
- "Run mean reversion on VEDL" → `run_mean_reversion_strategy`
- "How is paper trading doing vs Rs 1 lakh?" → `compare_portfolio_to_capital`
- "Show all strategy signals" → `get_all_strategy_signals`
- "Run list_tickers.py" → `run_python_script`

### Cursor IDE Kite MCP

[`.cursor/mcp.json`](.cursor/mcp.json) also points to hosted Kite MCP (`https://mcp.kite.trade/mcp`) for Cursor-native agents. The in-app assistant uses Kite Connect tools with the same tool names for consistency.

## Web UI routes

| Route | Page |
|-------|------|
| `/` | Bharat Scout screener |
| `/tracker/` | Portfolio tracker (paper snapshot) |
| `/paper/` | Full paper trading dashboard |
| `/assistant/` | In-app LLM trading assistant |
