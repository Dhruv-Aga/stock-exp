#!/usr/bin/env python3
"""Run Zerodha live or dry-run execution session."""

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.execution.engine import reset_live_state, run_live_session  # noqa: E402
from src import settings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Execute trades via Zerodha Kite (dry-run by default)"
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh market data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when market is closed (still respects kill switch)",
    )
    parser.add_argument("--reset", action="store_true", help="Reset live/dry-run state")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (requires KITE_* credentials and LIVE_TRADING=true)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.load_settings()

    if args.reset:
        print(reset_live_state())
        return

    if args.live and settings.dry_run_mode():
        print(
            "Live flag passed but LIVE_TRADING is not true in .env.\n"
            "Set LIVE_TRADING=true only after paper-trading review and adding Kite credentials."
        )
        sys.exit(1)

    mode = "LIVE" if not settings.dry_run_mode() else "DRY RUN"
    print(f"Starting Zerodha execution ({mode})...\n")
    print(run_live_session(refresh=args.refresh, force=args.force))


if __name__ == "__main__":
    main()
