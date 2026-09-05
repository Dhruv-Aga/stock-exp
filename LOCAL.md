# Local development

Run the **entire product locally** with one config file and one launcher script.

## Quick start

```bash
cp .env.example .env          # edit: add GROQ_API_KEY, optional KITE_*
./scripts/dev.sh setup        # install deps, sync config, health check
./scripts/dev.sh start        # agent API + frontend
```

Windows PowerShell users can run the same launcher without bash:

```powershell
Copy-Item .env.example .env
./scripts/dev.ps1 setup
./scripts/dev.ps1 start
```

Open:

| URL | What |
|-----|------|
| http://localhost:8080/ | Trading home (status + quick actions) |
| http://localhost:8080/portfolio/ | Portfolio (overview + full dashboard) |
| http://localhost:8080/assistant/ | Ask the assistant |
| http://localhost:8080/approvals/ | Approve live trades |
| http://localhost:8080/compare/ | Paper vs live A/B parity |
| http://localhost:8080/screener/ | Stock screener |

```bash
./scripts/dev.sh paper        # run paper session + refresh dashboard
./scripts/dev.sh ab           # paper vs live-shadow A/B comparison
./scripts/dev.sh status       # see what's running
./scripts/dev.sh stop         # stop all services
```

## One config file

Everything reads from **`.env` at the repo root**:

| Variable | Used by |
|----------|---------|
| `GROQ_API_KEY` | Assistant chat (`run_agent_api.py`) |
| `KITE_*` | Live portfolio tools + synced to `server/.env` for quote proxy |
| `LIVE_TRADING` | Enable live mode (still requires approval per trade) |
| `REQUIRE_TRADE_APPROVAL` | Gate live orders behind `/approvals/` |
| `AUTO_APPROVE_TRADES` | Execute live proposals immediately (keeps audit trail) |
| `BHARAT_SCOUT_API_KEY` | Protects agent API on LAN (auto-generated at setup) |
| `ZERODHA_*` | TOTP auto-login — see `docs/SECURITY.md` |
| `HOST_BIND` | Default `127.0.0.1`; use `0.0.0.0` only on trusted Wi‑Fi |

You do **not** need to configure each page separately. `scripts/sync_env.sh` copies Kite keys into `server/.env` automatically.

## Optional: Kite quote proxy

For live screener quotes (not required for paper trading):

```bash
START_KITE_PROXY=1 ./scripts/dev.sh start
```

Then set **Backend proxy URL** in the screener to `http://localhost:3000`.

## What runs when you `dev.sh start`

```
./scripts/dev.sh start
        │
        ├── python3 run_agent_api.py     → :8000  (assistant, approvals, tools)
        └── python3 -m http.server 8080  → :8080  (all UI pages)
```

Optional with `START_KITE_PROXY=1`:

```
        └── cd server && npm start       → :3000  (Kite quotes for screener)
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Assistant says "agent offline" | `./scripts/dev.sh start` |
| Approvals page empty | Normal if no proposals; run `./scripts/dev.sh paper` |
| Kite tools fail | Add `KITE_*` to `.env`, run `python run_kite_login.py` |
| Assistant no reply | Add `GROQ_API_KEY` to `.env` |
| Port in use | `FRONTEND_PORT=8081 ./scripts/dev.sh start` |

Run `./scripts/dev.sh setup` or `python3 check_setup.py` anytime for a full diagnostic.

## Paper trading is local-only

Paper sessions, dashboard refreshes, and daily report emails run on your machine. GitHub Actions only deploys already-committed static files (manual **Deploy static frontend to GitHub Pages**).

```bash
./scripts/dev.sh paper                 # one session + dashboard refresh
python run_daily_report.py --email     # session + optional SMTP email
```

Optional local cron (example: weekdays 09:20 IST after the open):

```cron
20 9 * * 1-5 cd /path/to/stock-exp && ./scripts/dev.sh paper
```

Do not add a GitHub Actions schedule or `workflow_dispatch` job that calls `run_paper.py`, `run_daily_report.py`, or `scripts/generate_dashboard.py`.
