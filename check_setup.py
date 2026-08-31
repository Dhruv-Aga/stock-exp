#!/usr/bin/env python3
"""Check that the full local product stack is configured correctly."""

import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import INITIAL_CAPITAL, MARKETS  # noqa: E402
from src import settings  # noqa: E402
from src.email_report import email_configured  # noqa: E402


def ok(msg: str) -> str:
    return f"[OK]   {msg}"


def warn(msg: str) -> str:
    return f"[WARN] {msg}"


def fail(msg: str) -> str:
    return f"[FAIL] {msg}"


def check_url(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main():
    print("=" * 60)
    print("BHARAT SCOUT — LOCAL SETUP CHECK")
    print("=" * 60)
    print()

    all_ok = True
    agent_port = os.environ.get("AGENT_API_PORT", "8000")
    frontend_port = os.environ.get("FRONTEND_PORT", "8080")

    print(ok(f"Python {sys.version.split()[0]}"))

    for pkg in ("pandas", "yfinance", "ta", "kiteconnect", "fastapi", "uvicorn", "groq"):
        try:
            __import__(pkg)
            print(ok(f"Package: {pkg}"))
        except ImportError:
            print(fail(f"Missing: {pkg}  ->  pip install -r requirements.txt"))
            all_ok = False

    if shutil.which("node") and shutil.which("npm"):
        print(ok("Node.js + npm (Kite proxy)"))
    else:
        print(warn("Node.js not found — optional for live screener quotes"))

    env_path = ROOT / ".env"
    if env_path.exists():
        print(ok(".env found (single config file at repo root)"))
        settings.load_settings()
    else:
        print(fail(".env missing  ->  cp .env.example .env  &&  ./scripts/dev.sh setup"))
        all_ok = False

    if (ROOT / "server" / ".env").exists():
        print(ok("server/.env present (synced from root .env)"))
    else:
        print(warn("server/.env missing  ->  ./scripts/sync_env.sh"))

    print()
    print("--- Features ---")

    if settings.groq_api_key():
        print(ok(f"Assistant (Groq): {settings.groq_model()}"))
    else:
        print(warn("Assistant: add GROQ_API_KEY to .env"))

    if settings.kite_configured():
        mode = "LIVE" if settings.live_trading_enabled() else "keys present, paper/dry-run"
        print(ok(f"Kite portfolio: configured ({mode})"))
    else:
        print(warn("Kite: add KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN"))

    if settings.require_trade_approval():
        if settings.auto_approve_trades():
            print(warn("AUTO_APPROVE_TRADES=true — live proposals execute without manual review"))
        else:
            print(ok("Live trades: require approval at /approvals/"))
    else:
        print(warn("REQUIRE_TRADE_APPROVAL=false — live orders may auto-execute without proposals"))

    if settings.live_trading_enabled():
        print(warn("LIVE_TRADING=true — real orders possible after approval"))
    else:
        print(ok("LIVE_TRADING=false — paper mode (safe)"))

    if email_configured():
        print(ok(f"Email reports -> {os.environ.get('EMAIL_TO', '')}"))
    else:
        print(warn("Email not configured (optional)"))

    if (ROOT / "paper" / "analysis.json").exists():
        print(ok("Paper snapshot: paper/analysis.json"))
    else:
        print(warn("No paper snapshot  ->  ./scripts/dev.sh paper"))

    print()
    print("--- Running services (optional) ---")
    if check_url(f"http://localhost:{agent_port}/api/agent/health"):
        print(ok(f"Agent API running on :{agent_port}"))
    else:
        print(warn(f"Agent API not running  ->  ./scripts/dev.sh start"))

    if check_url(f"http://localhost:{frontend_port}/"):
        print(ok(f"Frontend running on :{frontend_port}"))
    else:
        print(warn(f"Frontend not running  ->  ./scripts/dev.sh start"))

    print()
    print(ok(f"Capital: Rs {INITIAL_CAPITAL:,.0f}  |  Markets: {len(MARKETS)}"))
    print()
    print("-" * 60)
    print("ONE COMMAND TO RUN EVERYTHING LOCALLY")
    print("  ./scripts/dev.sh setup    # first time only")
    print("  ./scripts/dev.sh start    # agent API + frontend")
    print("  ./scripts/dev.sh paper    # refresh paper portfolio")
    print("  ./scripts/dev.sh status   # check services")
    print("  ./scripts/dev.sh stop     # stop all")
    print()
    print("OPEN IN BROWSER (after start)")
    print(f"  http://localhost:{frontend_port}/")
    print(f"  http://localhost:{frontend_port}/portfolio/")
    print(f"  http://localhost:{frontend_port}/assistant/")
    print(f"  http://localhost:{frontend_port}/approvals/")
    print(f"  http://localhost:{frontend_port}/screener/")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
