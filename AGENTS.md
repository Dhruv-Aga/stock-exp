# Agent instructions

## Product model

Bharat Scout is a **portfolio automation product** with human-in-the-loop safety:

| Mode | Behavior |
|------|----------|
| **Paper trading** | Strategies run automatically on simulated capital. No Kite orders. |
| **Shadow proposals** | Paper entries also queue live-trade previews for your review (`SHADOW_LIVE_PROPOSALS=true`). |
| **Live trading** | Strategies may propose real Kite orders — **never auto-execute**. User must approve at `/approvals/`. |

```
Strategy signal → Paper trade (automatic)
                → Live proposal (queued)
                → User approves at /approvals/
                → Kite order executed
```

The assistant can **propose** trades and analyze portfolios. It **cannot approve** live trades.

## In-app trading assistant

- **UI:** `/assistant/`
- **API:** `run_agent_api.py` (port 8000)
- **Approvals:** `/approvals/` — user must click Approve before any live Kite order

### Required configuration

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | In-app LLM chat |
| `KITE_*` | Live portfolio tools + approved execution |
| `LIVE_TRADING=true` | Enable live mode (still requires per-trade approval) |
| `REQUIRE_TRADE_APPROVAL=true` | Gate all live orders behind `/approvals/` (default) |
| `AUTO_APPROVE_TRADES=true` | Auto-execute live proposals (audit trail kept; shadow/paper proposals still manual) |
| `SHADOW_LIVE_PROPOSALS=true` | Paper sessions queue shadow live proposals |

### Tools (20)

**Kite portfolio:** `get_profile`, `get_holdings`, `get_positions`, `get_margins`

**Strategies:** `run_mean_reversion_strategy`, `run_momentum_breakout_strategy`, `run_trend_following_strategy`, `get_all_strategy_signals`

**Tickers:** `get_ticker_quote`, `get_ticker_history`, `list_configured_tickers`

**Benchmarking:** `get_paper_portfolio_status`, `run_portfolio_backtest`, `get_rolling_benchmark`, `compare_portfolio_to_capital`

**Proposals (assistant cannot approve):** `propose_trade`, `list_trade_proposals`, `get_trade_proposal`

**Scripts:** `run_python_script`, `run_node_script` from `scripts/sandbox/`

## Web UI routes

| Route | Task |
|-------|------|
| `/` | Trading home — status, signals, setup checklist |
| `/portfolio/` | Monitor — overview + full paper dashboard |
| `/approvals/` | Review — approve/reject live trades |
| `/assistant/` | Ask — LLM chat with tools |
| `/screener/` | Research — stock screener |

Legacy `/tracker/` → `/portfolio/`. `/paper/` → `/portfolio/#details` when not embedded.

## User journey

1. **Monitor** — check paper performance at `/` and `/portfolio/`.
2. **Review** — approve proposals at `/approvals/` when ready for live.
3. **Ask** — use `/assistant/` for analysis (never auto-executes live trades).

## Local development

```bash
cp .env.example .env
./scripts/dev.sh setup
./scripts/dev.sh start
```

See `LOCAL.md` for full details. One `.env` file configures everything.
