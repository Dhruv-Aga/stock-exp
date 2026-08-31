#!/usr/bin/env python3
"""Run daily/monthly rolling analysis and optionally email results."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import email_configured, load_env_file, send_report  # noqa: E402
from src.rolling_analysis import format_analysis_report, run_full_analysis  # noqa: E402

REPORT_DIR = ROOT / "data" / "reports"


def main():
    parser = argparse.ArgumentParser(
        description="Daily & rolling 30-day P&L analysis for Indian trading bot"
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh market data")
    parser.add_argument("--email", action="store_true", help="Send report via SMTP")
    args = parser.parse_args()

    load_env_file()
    print("Running rolling daily/monthly analysis...\n")
    analysis = run_full_analysis(refresh=args.refresh)
    report = format_analysis_report(analysis)
    print(report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    report_file = REPORT_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    report_file.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_file}")

    if args.email:
        if not email_configured():
            print(
                "\nEmail skipped - not configured.\n"
                "Create D:\\work\\india-trading-bot\\.env with:\n"
                "  SMTP_HOST=smtp.gmail.com\n"
                "  SMTP_PORT=587\n"
                "  SMTP_USER=your@gmail.com\n"
                "  SMTP_PASSWORD=your-app-password\n"
                "  EMAIL_FROM=your@gmail.com\n"
                "  EMAIL_TO=your@gmail.com\n"
                "Then run: python run_monthly_analysis.py --email"
            )
            sys.exit(1)
        subject = "India Trading Bot - Daily & Monthly P&L Report"
        msg = send_report(subject, report)
        print(msg)


if __name__ == "__main__":
    main()
