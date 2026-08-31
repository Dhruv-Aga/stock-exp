#!/usr/bin/env python3
"""Run historical backtest on Indian market strategies."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.backtest import run_backtest, summarize_results  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Backtest Indian trading strategies")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download market data from yfinance",
    )
    args = parser.parse_args()

    print("Fetching Indian market data and running backtest...")
    print("Markets: VAML, VEDL, VEDPOWER, VISL, BHEL\n")
    results = run_backtest(refresh=args.refresh)
    print(summarize_results(results))


if __name__ == "__main__":
    main()
