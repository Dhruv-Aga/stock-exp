#!/usr/bin/env python3
"""Check that the trading bot is configured correctly."""

import os
import shutil
import subprocess
import sys
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


def main():
    print("=" * 60)
    print("INDIA TRADING BOT - SETUP CHECK")
    print("=" * 60)
    print()

    all_ok = True

    print(ok(f"Python {sys.version.split()[0]}"))

    for pkg in ("pandas", "yfinance", "ta", "kiteconnect"):
        try:
            __import__(pkg)
            print(ok(f"Package: {pkg}"))
        except ImportError:
            print(fail(f"Missing: {pkg}  ->  pip install -r requirements.txt"))
            all_ok = False

    env_path = ROOT / ".env"
    if env_path.exists():
        print(ok(".env file found"))
        settings.load_settings()
    else:
        print(fail(".env missing  ->  copy .env.example to .env"))
        all_ok = False

    if email_configured():
        print(ok(f"Email reports -> {os.environ.get('EMAIL_TO', '')}"))
    else:
        print(warn("Email not configured"))

    if settings.kite_configured():
        mode = "LIVE" if settings.live_trading_enabled() else "keys present, dry-run"
        print(ok(f"Zerodha Kite configured ({mode})"))
    else:
        missing = []
        if not settings.kite_api_key():
            missing.append("KITE_API_KEY")
        if not settings.kite_api_secret():
            missing.append("KITE_API_SECRET")
        if not settings.kite_access_token():
            missing.append("KITE_ACCESS_TOKEN")
        print(warn(f"Zerodha: add {', '.join(missing)} after paper review"))

    if settings.live_trading_enabled():
        print(warn("LIVE_TRADING=true  -- real orders enabled!"))
    else:
        print(ok("LIVE_TRADING=false  -- safe dry-run mode"))

    if settings.groq_api_key() and settings.llm_risk_governor_enabled():
        print(ok(f"LLM risk governor: Groq {settings.groq_model()}"))
    elif settings.llm_risk_governor_enabled():
        print(warn("LLM risk governor enabled but GROQ_API_KEY missing (rules-only)"))
    else:
        print(warn("LLM risk governor disabled (LLM_RISK_GOVERNOR=false)"))

    print(ok(f"Capital: Rs {INITIAL_CAPITAL:,.0f}  |  Markets: {len(MARKETS)}"))
    print(ok(f"Max daily loss: Rs {settings.max_daily_loss():,.0f}"))

    if shutil.which("schtasks"):
        tasks = ["IndiaTradingBot Morning Report", "IndiaTradingBot Evening Report"]
        found = sum(
            1
            for name in tasks
            if subprocess.run(
                ["schtasks", "/Query", "/TN", name], capture_output=True
            ).returncode
            == 0
        )
        if found == 2:
            print(ok("Scheduled emails: 09:15 + 21:15 daily"))
        else:
            print(warn(f"Scheduled emails: {found}/2 tasks found"))

    print()
    print("-" * 60)
    print("COMMANDS")
    print("  python run_paper.py                  # paper trade")
    print("  python run_daily_report.py --email   # paper session + daily report")
    print("  python run_monthly_analysis.py --email  # historical backtest report")
    print("  python run_live.py --force           # dry-run orders")
    print("  python run_kite_login.py             # after Kite keys added")
    print()
    print("YOUR PLAN")
    print("  Capital : Rs 1,00,000")
    print("  Target  : ~Rs 6,000/month (if pattern holds)")
    print("  Now     : 1 month paper review via email reports")
    print("  Later   : Add KITE_* keys, then LIVE_TRADING=true")
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
