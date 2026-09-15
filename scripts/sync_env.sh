#!/usr/bin/env bash
# Sync Kite credentials from root .env into server/.env for the quote proxy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your keys before live features work."
fi

# Ensure server/.env exists with proxy defaults
if [ ! -f server/.env ]; then
  cp server/.env.example server/.env
fi

# Pull KITE_* and PORT from root .env into server/.env (preserve ALLOWED_ORIGINS)
python3 - <<'PY'
import re
from pathlib import Path

root = Path(".env")
server_env = Path("server/.env")
keys = ("KITE_API_KEY", "KITE_ACCESS_TOKEN", "PORT")

values = {}
if root.exists():
    for line in root.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k in keys:
            values[k] = v

if not server_env.exists():
    server_env.write_text("")

lines = server_env.read_text().splitlines()
out = []
seen = set()
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in values:
            out.append(f"{k}={values[k]}")
            seen.add(k)
            continue
    out.append(line)

for k in keys:
    if k in values and k not in seen:
        out.append(f"{k}={values[k]}")

if "ALLOWED_ORIGINS" not in "\n".join(out):
    out.append("ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080")

server_env.write_text("\n".join(out).rstrip() + "\n")
print("Synced Kite settings to server/.env")
PY
