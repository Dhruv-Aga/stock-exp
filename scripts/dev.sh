#!/usr/bin/env bash
# Unified local dev launcher — one command to configure and run the full product.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEV_DIR="$ROOT/.dev"
AGENT_PID="$DEV_DIR/agent.pid"
FRONTEND_PID="$DEV_DIR/frontend.pid"
KITE_PID="$DEV_DIR/kite.pid"
HOST_BIND="${HOST_BIND:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
AGENT_PORT="${AGENT_API_PORT:-8000}"
KITE_PORT="${KITE_PROXY_PORT:-3000}"

banner() {
  echo ""
  echo "============================================================"
  echo "  Bharat Scout / India Trading Bot — local dev"
  echo "============================================================"
}

stop_pid() {
  local pidfile="$1"
  local name="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "Stopped $name (pid $pid)"
    fi
    rm -f "$pidfile"
  fi
}

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti :"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      kill $pids 2>/dev/null || true
    fi
  fi
}

cmd_setup() {
  banner
  echo "Installing dependencies..."
  bash "$ROOT/.cursor/install.sh"
  python3 "$ROOT/scripts/ensure_local_secrets.py"
  bash "$ROOT/scripts/sync_env.sh"
  echo ""
  echo "Running setup check..."
  python3 "$ROOT/check_setup.py" || true
  echo ""
  echo "Generating paper portfolio snapshot (if possible)..."
  python3 "$ROOT/scripts/generate_dashboard.py" --no-refresh 2>/dev/null || \
    echo "  (skipped — run again after .env is configured)"
  echo ""
  echo "Setup complete. Run: ./scripts/dev.sh start"
}

cmd_start() {
  banner
  mkdir -p "$DEV_DIR"

  python3 "$ROOT/scripts/ensure_local_secrets.py"
  bash "$ROOT/scripts/sync_env.sh"

  if python3 -c "import sys; sys.path.insert(0,'$ROOT'); from src import settings; settings.load_settings(); raise SystemExit(0 if settings.zerodha_auto_login_configured() else 1)" 2>/dev/null; then
    echo "Refreshing Kite token (TOTP auto-login)..."
    python3 "$ROOT/run_kite_auto_login.py" || echo "  (Kite auto-login failed — check ZERODHA_* in .env)"
  fi

  # Stop any previous dev processes we started
  cmd_stop 2>/dev/null || true
  kill_port "$AGENT_PORT"
  kill_port "$FRONTEND_PORT"
  if [ "${START_KITE_PROXY:-0}" = "1" ]; then
    kill_port "$KITE_PORT"
  fi
  sleep 1

  export HOST_BIND
  echo "Starting agent API on $HOST_BIND:$AGENT_PORT ..."
  nohup env HOST_BIND="$HOST_BIND" python3 "$ROOT/run_agent_api.py" >"$DEV_DIR/agent.log" 2>&1 &
  echo $! >"$AGENT_PID"

  echo "Starting frontend on $HOST_BIND:$FRONTEND_PORT (restricted static server) ..."
  nohup env HOST_BIND="$HOST_BIND" FRONTEND_PORT="$FRONTEND_PORT" \
    python3 "$ROOT/scripts/static_server.py" --bind "$HOST_BIND" --port "$FRONTEND_PORT" \
    >"$DEV_DIR/frontend.log" 2>&1 &
  echo $! >"$FRONTEND_PID"

  if [ "${START_KITE_PROXY:-0}" = "1" ]; then
    echo "Starting Kite quote proxy on :$KITE_PORT ..."
    (cd "$ROOT/server" && nohup npm start >"$DEV_DIR/kite.log" 2>&1 & echo $! >"$KITE_PID")
  fi

  sleep 2
  cmd_status

  echo ""
  echo "Open in browser:"
  echo "  http://localhost:$FRONTEND_PORT/              Trading home"
  echo "  http://localhost:$FRONTEND_PORT/portfolio/    Portfolio"
  echo "  http://localhost:$FRONTEND_PORT/assistant/    Ask assistant"
  echo "  http://localhost:$FRONTEND_PORT/approvals/   Review live trades"
  echo "  http://localhost:$FRONTEND_PORT/compare/     Paper vs live A/B"
  echo "  http://localhost:$FRONTEND_PORT/screener/    Stock screener"
  if [ "$HOST_BIND" = "0.0.0.0" ] || [ "$HOST_BIND" = "::" ]; then
    echo ""
    echo "  WARNING: LAN mode — set BHARAT_SCOUT_API_KEY in .env and enter it in the browser when prompted."
    for ip in $(hostname -I 2>/dev/null || ipconfig getifaddr 2>/dev/null || true); do
      if printf '%s' "$ip" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        echo "  http://$ip:$FRONTEND_PORT/                   Home network"
      fi
    done
  fi
  echo ""
  echo "Logs: $DEV_DIR/*.log"
  echo "Stop: ./scripts/dev.sh stop"
}

cmd_stop() {
  banner
  stop_pid "$AGENT_PID" "agent API"
  stop_pid "$FRONTEND_PID" "frontend"
  stop_pid "$KITE_PID" "Kite proxy"
  echo "All dev services stopped."
}

cmd_status() {
  echo ""
  echo "Service status:"
  status_one "Agent API" "$AGENT_PID" "$AGENT_PORT"
  status_one "Frontend" "$FRONTEND_PID" "$FRONTEND_PORT"
  status_one "Kite proxy" "$KITE_PID" "$KITE_PORT"

  if curl -sf "http://localhost:$AGENT_PORT/api/agent/health" >/dev/null 2>&1; then
    echo ""
    echo "Agent health:"
    curl -s "http://localhost:$AGENT_PORT/api/agent/health" | python3 -m json.tool 2>/dev/null || true
  fi
}

status_one() {
  local name="$1" pidfile="$2" port="$3"
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  [running] $name — http://localhost:$port (pid $(cat "$pidfile"))"
  else
    echo "  [stopped] $name"
  fi
}

cmd_paper() {
  banner
  echo "Running paper session and refreshing dashboard..."
  python3 "$ROOT/scripts/generate_dashboard.py" --refresh
  echo "Done. View at http://localhost:$FRONTEND_PORT/portfolio/"
}

cmd_ab() {
  banner
  echo "Running paper vs live-shadow A/B comparison..."
  python3 "$ROOT/scripts/run_ab_compare.py"
  echo "View at http://localhost:$FRONTEND_PORT/compare/"
}

cmd_login() {
  banner
  python3 "$ROOT/run_kite_auto_login.py" "$@"
}

usage() {
  banner
  echo ""
  echo "Usage: ./scripts/dev.sh <command>"
  echo ""
  echo "Commands:"
  echo "  setup     Install deps, sync .env, run checks (run once)"
  echo "  start     Start agent API + frontend (+ Kite proxy if START_KITE_PROXY=1)"
  echo "  stop      Stop all dev services"
  echo "  status    Show what's running"
  echo "  paper     Run paper trading session and refresh dashboard"
  echo "  login     Refresh Kite token via TOTP (run_kite_auto_login.py)"
  echo ""
  echo "Environment (optional):"
  echo "  HOST_BIND=0.0.0.0    LAN access (requires BHARAT_SCOUT_API_KEY)"
  echo "  FRONTEND_PORT=8080   AGENT_API_PORT=8000   KITE_PROXY_PORT=3000"
  echo "  START_KITE_PROXY=1   Also start server/ quote proxy"
  echo ""
  echo "Config: single .env at repo root (see .env.example)"
  echo "  GROQ_API_KEY     — assistant chat"
  echo "  ZERODHA_*          — TOTP auto-login (see docs/SECURITY.md)"
}

case "${1:-}" in
  login) cmd_login "${@:2}" ;;
  setup) cmd_setup ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  paper) cmd_paper ;;
  ab) cmd_ab ;;
  *) usage ;;
esac
