# Bharat Scout

Bharat Scout is a responsive NSE watchlist and value screener that can be hosted as a static site on GitHub Pages. It runs in two modes:

Paper trading and portfolio refreshes are **local-only**. Use `./scripts/dev.sh paper` (or `./scripts/dev.ps1 paper`) or a local cron job. Do not run paper sessions in GitHub Actions (including manual `workflow_dispatch`).

- **Demo mode:** no backend required; useful for UI checks and GitHub Pages previews.
- **Kite live mode:** the frontend calls a private Node/Express proxy, and the proxy calls Zerodha Kite with credentials stored in backend environment variables.

> Never put a Zerodha API key or access token in frontend code. GitHub Pages is public static hosting, so every secret shipped to the browser is exposed.

## Site routes

| Route | Page |
|-------|------|
| `/` | **Trading home** — status, signals, quick actions |
| `/portfolio/` | **Monitor** — portfolio overview + full dashboard |
| `/approvals/` | **Review** — approve/reject live trades |
| `/assistant/` | **Ask** — LLM chat with tools |
| `/screener/` | **Research** — NSE watchlist screener |

Legacy `/tracker/` redirects to `/portfolio/`. `/paper/` redirects to `/portfolio/#details` when opened directly.

## User journey

1. **Monitor** — open `/`, check paper equity and signals; drill into `/portfolio/` if needed.
2. **Review** — approve shadow or live proposals at `/approvals/` when ready.
3. **Ask** — use `/assistant/` for analysis; it never auto-executes live trades.

## Project structure

```text
index.html                    Trading home (site root)
screener/index.html           Stock screener
portfolio/                    Unified portfolio (overview + details tabs)
src/shell/                    Shared nav, status strip, onboarding
style.css                     Shared responsive UI
assistant/                    In-app LLM trading assistant (chat UI)
src/agent/                    Agent tool registry, handlers, Groq chat loop
run_agent_api.py              FastAPI agent server (port 8000)
scripts/dev.sh                One-command local setup and launcher
scripts/sandbox/              Custom Python/Node scripts for assistant
paper/                        Generated paper dashboard + analysis.json
src/app.js                    Screener UI state, filters, watchlist
src/api.js                    Demo quotes and backend quote client
scripts/generate_dashboard.py Builds paper/ artifacts from trading bot (local)
server/server.js              Optional secure Kite proxy
.github/workflows/pages.yml   Manual static GitHub Pages deploy (no paper session)
.cursor/mcp.json              Kite MCP configuration for agents
AGENTS.md                     Agent instructions for portfolio checks
LOCAL.md                      Local dev quick start
```

## Product requirements

See [`docs/PRD.md`](docs/PRD.md) for the complete product requirements document.

## Run locally (one command)

See **[LOCAL.md](LOCAL.md)** for the full guide. Quick start:

```bash
cp .env.example .env
./scripts/dev.sh setup
./scripts/dev.sh start
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
./scripts/dev.ps1 setup
./scripts/dev.ps1 start
```

This starts the **agent API** (`:8000`) and **frontend** (`:8080`) together. One `.env` file configures everything.

| Command | What it does |
|---------|----------------|
| `./scripts/dev.sh setup` | Install deps, sync config, health check |
| `./scripts/dev.sh start` | Run agent API + frontend |
| `./scripts/dev.sh paper` | Paper trade session + refresh dashboard |
| `./scripts/dev.sh status` | Show running services |
| `./scripts/dev.sh stop` | Stop all |

Then open:

- <http://localhost:8080/> — trading home
- <http://localhost:8080/portfolio/> — monitor portfolio
- <http://localhost:8080/approvals/> — review live trades
- <http://localhost:8080/assistant/> — ask the assistant
- <http://localhost:8080/screener/> — research stocks

## Product: paper first, live with approval

1. **Paper trading** — strategies run automatically on simulated Rs 1,00,000 capital.
2. **Shadow proposals** — each paper entry can queue a preview of what live would do.
3. **Live trading** — when `LIVE_TRADING=true`, automation creates proposals; **you approve at `/approvals/`** before any real Kite order (unless `AUTO_APPROVE_TRADES=true`).

The assistant can analyze your portfolio and propose trades. It **cannot** approve or execute live orders for you.

## In-app trading assistant

Configured via `GROQ_API_KEY` in `.env`. Started automatically by `./scripts/dev.sh start`.

See [`AGENTS.md`](AGENTS.md) for the full tool list.

## Kite MCP (Cursor IDE)

[`.cursor/mcp.json`](.cursor/mcp.json) configures hosted Kite MCP for Cursor-native agents. The in-app assistant uses equivalent Kite Connect tools.

## Deploy to GitHub Pages

1. Push this repository to GitHub.
2. In GitHub, open **Settings → Pages**.
3. Set **Source** to **GitHub Actions**.
4. Refresh the paper trading snapshot **locally** (`./scripts/dev.sh paper` or a local cron job). GitHub Actions does not run paper sessions.
5. For a one-off manual deploy of the committed static site, run **Deploy static frontend to GitHub Pages**.

**Live URL:** GitHub Pages project sites are served at `https://<user>.github.io/<repo>/` (for this repo: `https://dhruv-aga.github.io/stock-exp/`). Navigation links are base-path aware, so `/portfolio/` resolves correctly under the repo prefix — not at `https://<user>.github.io/portfolio/`.

No frontend build step is required. The agent API (`run_agent_api.py`) runs locally or on a backend host — it is not deployed to GitHub Pages.

## Deploy the Kite proxy

GitHub Pages cannot safely call Zerodha Kite directly because credentials would be exposed and browser CORS can block direct API calls. Deploy `server/` to a backend host such as Render, Railway, Fly.io, or a VPS.

1. Copy `server/.env.example` to environment variables on your host.
2. Set `KITE_API_KEY` and the daily `KITE_ACCESS_TOKEN` on the backend only.
3. Set `ALLOWED_ORIGINS` to your GitHub Pages URL and any local development URLs.
4. Deploy and verify `/api/health` returns `{ "ok": true }`.
5. Paste the backend URL into Bharat Scout's **Backend proxy URL** field and click **Save Backend**.

## Notes

- Kite access tokens expire and must be refreshed according to Zerodha's authentication flow.
- The sample fundamentals are static seed data. Extend `src/data.js` or add backend endpoints if you need richer fundamentals.
- The watchlist and backend URL are persisted in the browser with LocalStorage.
- Portfolio snapshots are generated locally by `scripts/generate_dashboard.py` (via `./scripts/dev.sh paper`). Do not run paper trading in GitHub Actions.
