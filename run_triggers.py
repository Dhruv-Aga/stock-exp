#!/usr/bin/env python3
"""Run one portfolio trigger-monitoring cycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.email_report import load_env_file  # noqa: E402
from src.triggers import run_portfolio_checks  # noqa: E402


def main() -> int:
    load_env_file()
    result = run_portfolio_checks(auto_analyze=True)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
