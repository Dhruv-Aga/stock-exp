# Local development

Run the **entire product locally** with one config file and one launcher script.

## Quick start

```bash
cp .env.example .env          # edit: add GROQ_API_KEY, optional KITE_*
./scripts/dev.sh setup        # install deps, sync config, health check
./scripts/dev.sh start        # agent API + frontend
```

Open:

| URL | What |
|-----|------|
| http://localhost:8080/ | Trading home (status + quick actions) |
| http://localhost:8080/portfolio/ | Portfolio (overview + full dashboard) |
| http://localhost:8080/assistant/ | Ask the assistant |
| http://localhost:8080/approvals/ | Approve live trades |
| http://localhost:8080/screener/ | Stock screener |

```bash
./scripts/dev.sh paper        # run paper session + refresh dashboard
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
| `FRONTEND_PORT` / `AGENT_API_PORT` | `dev.sh` ports |

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
