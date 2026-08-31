#!/usr/bin/env python3
"""Run paper trading session and email the daily dashboard report."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import email_configured, load_env_file, send_report  # noqa: E402
from src.paper_report import build_paper_analysis, format_paper_report  # noqa: E402
from src.paper_trader import run_paper_session  # noqa: E402

REPORT_DIR = ROOT / "data" / "reports"


def main():
    parser = argparse.ArgumentParser(
        description="Daily paper trading session + dashboard email"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        default=True,
        help="Refresh market data before trading (default: on)",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use cached market data",
    )
    parser.add_argument("--email", action="store_true", help="Send report via SMTP")
    args = parser.parse_args()

    refresh = args.refresh and not args.no_refresh
    load_env_file()

    print("Running paper trading session...\n")
    session = run_paper_session(refresh=refresh)
    print(session["summary"])
    print()

    analysis = build_paper_analysis(session=session)
    report = format_paper_report(analysis)
    print(report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"daily_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    report_file.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_file}")

    if args.email:
        if not email_configured():
            print(
                "\nEmail skipped - not configured.\n"
                "Create D:\\work\\india-trading-bot\\.env with SMTP settings."
            )
            sys.exit(1)
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"India Trading Bot - Daily Paper Report ({today})"
        msg = send_report(subject, report)
        print(msg)


if __name__ == "__main__":
    main()
