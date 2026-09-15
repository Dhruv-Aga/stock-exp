#!/usr/bin/env python3
"""Run one safe intraday paper session and refresh the dashboard.

This entry point never places live orders. It is intended to be called by a
local Windows scheduled task or cron while the market is open.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import load_env_file  # noqa: E402
from src.paper_trader import run_paper_session  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one intraday paper session")
    parser.add_argument("--no-refresh", action="store_true", help="Use cached market data")
    args = parser.parse_args()

    load_env_file()
    now = datetime.now()
    print(f"[{now:%Y-%m-%d %H:%M:%S}] Running intraday paper session...")
    session = run_paper_session(refresh=not args.no_refresh)
    print(session["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
