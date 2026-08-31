#!/usr/bin/env python3
"""Reset paper state and run weekly backtest report with optional email."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import email_configured, load_env_file, send_report  # noqa: E402
from src.execution.engine import reset_live_state  # noqa: E402
from src.paper_trader import reset_paper_account  # noqa: E402
from src.rolling_analysis import format_weekly_report, run_weekly_analysis  # noqa: E402

REPORT_DIR = ROOT / "data" / "reports"


def main():
    parser = argparse.ArgumentParser(description="Weekly paper backtest report")
    parser.add_argument("--refresh", action="store_true", help="Refresh market data")
    parser.add_argument("--email", action="store_true", help="Email the report")
    parser.add_argument("--days", type=int, default=7, help="Lookback days (default 7)")
    parser.add_argument("--no-reset", action="store_true", help="Skip paper state reset")
    args = parser.parse_args()

    load_env_file()

    if not args.no_reset:
        print(reset_paper_account())
        print(reset_live_state())
        print()

    print(f"Running weekly backtest (last {args.days} days)...\n")
    analysis = run_weekly_analysis(refresh=args.refresh, days=args.days)
    report = format_weekly_report(analysis)
    print(report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"weekly_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    report_file.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_file}")

    if args.email:
        if not email_configured():
            print("\nEmail not configured. Add SMTP settings to .env")
            sys.exit(1)
        subject = (
            f"India Trading Bot - Weekly Report "
            f"({analysis['week_start']} to {analysis['week_end']})"
        )
        print(send_report(subject, report))


if __name__ == "__main__":
    main()
