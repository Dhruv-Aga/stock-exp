#!/usr/bin/env bash
# Install Bharat Scout as a per-user systemd service (Linux) — starts on login/boot.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_NAME="bharat-scout.service"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
TEMPLATE="${ROOT}/scripts/bharat-scout.service"
INSTALLED="${USER_UNIT_DIR}/${UNIT_NAME}"

mkdir -p "$USER_UNIT_DIR"
chmod +x "$ROOT/scripts/boot-preflight.sh" "$ROOT/scripts/dev.sh"

sed "s|%h/stock-exp|${ROOT}|g" "$TEMPLATE" >"$INSTALLED"

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"
systemctl --user start "$UNIT_NAME" || true

echo "Installed ${UNIT_NAME}"
echo "  status: systemctl --user status bharat-scout"
echo "  logs:   journalctl --user -u bharat-scout -f"
echo ""
echo "Optional: enable lingering so the service runs without an active login session:"
echo "  sudo loginctl enable-linger \$USER"
