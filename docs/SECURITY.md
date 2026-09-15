# Security guide — local and home-network deployment

This document describes how Bharat Scout protects your data when you run it on your own PC or home Wi‑Fi. It is written for operators, not attackers.

## Threat model

You run Bharat Scout on a machine that may be reachable by **any device on your Wi‑Fi** (phones, guests, IoT). Goals:

- Prevent neighbours or guests from **approving live trades**, reading **`.env` secrets**, or calling the **assistant API** without your key.
- Keep **GitHub Pages** (if used) limited to static UI — no secrets, no live backend.
- Automate **daily Kite login** without pasting tokens manually (Zerodha still requires a fresh session each trading day).

## What we implemented

| Control | Purpose |
|---------|---------|
| **`BHARAT_SCOUT_API_KEY`** | Required header (`X-Bharat-Scout-Key`) on agent API routes when set in `.env` |
| **Default `HOST_BIND=127.0.0.1`** | Services listen on localhost only unless you opt into LAN mode |
| **Restricted static server** | Frontend no longer serves `.env`, `data/`, `server/`, or source trees |
| **TOTP auto-login** | `run_kite_auto_login.py` refreshes Kite tokens using `ZERODHA_*` credentials |
| **Boot service installers** | `install-boot-service.sh` (Linux) / `.ps1` (Windows) restart stack after reboot |
| **Safer Pages deploy** | `build_pages_dist.py` publishes UI-only `dist-pages/` |

## First-time setup

```bash
cp .env.example .env
./scripts/dev.sh setup          # generates BHARAT_SCOUT_API_KEY
```

Add Zerodha **Personal (free)** API keys and TOTP auto-login fields:

```env
KITE_API_KEY=...
KITE_API_SECRET=...

ZERODHA_USER_ID=AB1234
ZERODHA_PASSWORD=your_zerodha_password
ZERODHA_TOTP_SECRET=BASE32_SECRET_FROM_AUTHENTICATOR_SETUP

BHARAT_SCOUT_API_KEY=...        # auto-generated; enter in browser when prompted
HOST_BIND=127.0.0.1             # keep this unless you need phone access on Wi‑Fi
```

**TOTP secret:** When you enable 2FA on Zerodha, save the **setup key** (base32), not just the QR code. Store it only in `.env` on your PC.

Test auto-login:

```bash
./scripts/dev.sh login
```

## LAN access (optional)

To open the UI from your phone on the same Wi‑Fi:

```bash
HOST_BIND=0.0.0.0 ./scripts/dev.sh start
```

You **must** use `BHARAT_SCOUT_API_KEY`. The browser will prompt once per session; the key is kept in `sessionStorage` (cleared when you close the tab).

**Never** expose ports 8000/8080 to the public internet without a VPN or reverse proxy with TLS.

## Auto-start after reboot / power loss

**Linux (systemd user service):**

```bash
chmod +x scripts/install-boot-service.sh scripts/boot-preflight.sh
./scripts/install-boot-service.sh
```

**Windows:**

```powershell
./scripts/install-boot-service.ps1
```

**Daily Kite token (before 9:15 IST):** add a cron job — see `scripts/kite-login.cron`. Auto-login also runs when you `./scripts/dev.sh start`.

## GitHub Pages

The deploy workflow builds **`dist-pages/`** only (static UI). It does **not** ship `.env`, Python backends, or `data/trading.db`.

If your Pages site is public:

- Do **not** commit real `paper/analysis.json` with live positions.
- Use demo/sanitized snapshots, or keep Pages private.

## Credential storage

| File | Contents | Permissions |
|------|----------|-------------|
| `.env` | API keys, Zerodha password, TOTP secret | `chmod 600` recommended |
| `data/kite_token.json` | Daily Kite access token cache | gitignored, `chmod 600` |
| `data/trading.db` | Chat + proposals | gitignored |

**Do not** commit `.env`, `data/kite_token.json`, or `data/trading.db`.

## Kite MCP vs Kite Connect

- **Kite MCP** (`mcp.kite.trade`) — for AI tools in Cursor; read-only on hosted tier.
- **Kite Connect Personal (free)** — what Bharat Scout uses for orders; still needs a daily token (automated via TOTP).

## Operational checklist

- [ ] `BHARAT_SCOUT_API_KEY` set and not shared on Wi‑Fi
- [ ] `HOST_BIND=127.0.0.1` unless you understand LAN risk
- [ ] `AUTO_APPROVE_TRADES=false` for manual review
- [ ] `REQUIRE_TRADE_APPROVAL=true`
- [ ] Zerodha TOTP auto-login tested (`./scripts/dev.sh login`)
- [ ] Boot service installed if you need recovery after power loss
- [ ] GitHub Pages uses `dist-pages` only; no real portfolio JSON in git

## Reporting issues

If you find a security problem in this repo, fix it locally first (this is a personal deployment). Do not publish exploit details in public issues; describe impact and steps to reproduce privately.
