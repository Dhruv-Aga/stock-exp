#!/usr/bin/env python3
"""Run one paper-trading evaluation cycle."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import load_env_file  # noqa: E402
from src.paper_trader import reset_paper_account, run_paper_session  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Indian paper trading session")
    parser.add_argument(
        "--refresh",
        action="store_true",
        default=True,
        help="Refresh market data (default: on)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset paper account to initial capital",
    )
    args = parser.parse_args()
    load_env_file()

    if args.reset:
        print(reset_paper_account())
        return

    print(run_paper_session(refresh=args.refresh)["summary"])


if __name__ == "__main__":
    main()
