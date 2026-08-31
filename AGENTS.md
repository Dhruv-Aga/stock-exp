# Agent instructions

## Kite MCP setup

This project uses Zerodha's hosted **Kite MCP** server so agents can check live portfolio status, positions, margins, and market data from a connected Kite account.

### Configuration

Project-level config lives in [`.cursor/mcp.json`](.cursor/mcp.json):

```json
{
  "mcpServers": {
    "kite": {
      "url": "https://mcp.kite.trade/mcp"
    }
  }
}
```

No API keys are required in `mcp.json` for the hosted server. Restart Cursor after changing MCP configuration.

### First-time authorization

1. Open Cursor **Settings → Tools & MCP** and confirm the `kite` server is enabled.
2. In Agent chat, invoke a Kite MCP tool (for example `get_profile` or `get_holdings`).
3. Follow the Zerodha authorization prompt to link your Kite account.

Hosted Kite MCP excludes destructive trading operations. For full API access, self-host [zerodha/kite-mcp-server](https://github.com/zerodha/kite-mcp-server) with your own `KITE_API_KEY` and `KITE_API_SECRET`.

## Checking portfolio status and performance

### Live Kite account (via Kite MCP)

When asked about **live** portfolio status or performance, use Kite MCP tools:

| Tool | Use for |
|------|---------|
| `get_profile` | Account identity and basic profile |
| `get_margins` | Available cash, collateral, and margin utilization |
| `get_holdings` | Long-term portfolio holdings |
| `get_positions` | Intraday and overnight open positions with P&L |
| `get_mf_holdings` | Mutual fund investments |

Combine `get_positions` and `get_holdings` for a full portfolio snapshot. Use `get_margins` for available capital.

### Paper trading (via committed snapshots)

For **paper trading** performance (India Trading Bot), read these files from the repo:

| File | Contents |
|------|----------|
| [`paper/analysis.json`](paper/analysis.json) | Latest KPIs: equity, cash, unrealized P&L, total return %, today/week/month realized P&L, open positions, recent trades, daily equity history, `generated_at` |
| [`data/trades.json`](data/trades.json) | Full closed-trade history exported from SQLite |
| [`data/paper_state.json`](data/paper_state.json) | Raw paper portfolio state (committed by CI when changed) |

### Key fields in `paper/analysis.json`

- `equity`, `cash`, `unrealized_pnl`, `total_return_pct`
- `today_pnl`, `week_pnl`, `month_pnl`
- `open_positions` — symbol, side, quantity, entry_price, mark_price, unrealized_pnl
- `recent_trades` — last closed trades
- `daily_equity` — equity snapshots for charting
- `generated_at` — when the snapshot was last built

## Web UI routes

| Route | Page |
|-------|------|
| `/` | Bharat Scout screener |
| `/tracker/` | Portfolio tracker (loads `paper/analysis.json`) |
| `/paper/` | Full paper trading dashboard |

## Local development

```bash
# Install dependencies
./.cursor/install.sh

# Generate paper dashboard + analysis snapshot
python3 scripts/generate_dashboard.py --no-refresh

# Serve static site
python3 -m http.server 8080
```

Open `http://localhost:8080`, `http://localhost:8080/tracker/`, and `http://localhost:8080/paper/`.
