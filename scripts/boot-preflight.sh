#!/usr/bin/env bash
# Pre-start checks for systemd / boot: refresh Kite token when TOTP is configured.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 "$ROOT/scripts/ensure_local_secrets.py"

if python3 -c "import sys; sys.path.insert(0,'$ROOT'); from src import settings; settings.load_settings(); raise SystemExit(0 if settings.zerodha_auto_login_configured() else 1)" 2>/dev/null; then
  python3 "$ROOT/run_kite_auto_login.py" || true
fi
