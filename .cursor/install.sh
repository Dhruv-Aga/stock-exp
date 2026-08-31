#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Python trading bot dependencies
python3 -m pip install --user -r requirements.txt

# Bharat Scout Kite proxy (Node/Express)
cd server
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
cd ..

# Local config from examples when missing (secrets added via dashboard)
if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ ! -f server/.env ]; then
  cp server/.env.example server/.env
fi

# Keep server proxy in sync with root .env
bash "$(dirname "$0")/../scripts/sync_env.sh"
