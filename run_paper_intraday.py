#!/usr/bin/env python3
"""Run one paper trading session during market hours (for scheduled intraday runs)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def main() -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Intraday paper trading tick")
    parser.add_argument("--force", action="store_true", help="Run even when market is closed")
    parser.add_argument("--refresh", action="store_true", default=True, help="Refresh market data")
    parser.add_argument("--no-refresh", action="store_true", help="Use cached bars")
    args = parser.parse_args()

    from src.email_report import load_env_file
    from src.intraday import (
        bars_changed_since_last_run,
        record_session_bars,
        session_stamp,
        should_run_intraday_session,
    )
    from src.paper_trader import run_paper_session

    load_env_file()
    ok, reason = should_run_intraday_session(force=args.force)
    if not ok:
        print(f"[{session_stamp()}] Skipped intraday paper: {reason}")
        return 0

    refresh = args.refresh and not args.no_refresh
    session = run_paper_session(refresh=refresh)
    data_as_of = session.get("data_as_of") or {}
    actions = session.get("actions") or []
    changed = bars_changed_since_last_run(data_as_of)
    record_session_bars(data_as_of)

    if actions or changed:
        print(session["summary"])
    else:
        print(
            f"[{session_stamp()}] Paper tick — no new bars, no actions "
            f"(equity Rs{session.get('equity', 0):,.0f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
