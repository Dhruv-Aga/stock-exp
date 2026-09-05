#!/usr/bin/env python3
"""Refresh Zerodha Kite access token via TOTP (no browser)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import settings  # noqa: E402
from src.kite_auto_login import KiteAutoLoginError, ensure_kite_token, is_cached_token_valid  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated Kite Connect login using TOTP (Personal/free tier)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh even if cached token is still valid",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if a valid cached token exists, 1 otherwise",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.load_settings()

    if args.check:
        sys.exit(0 if is_cached_token_valid() else 1)

    try:
        result_token = ensure_kite_token(force=args.force)
        print("Kite access token ready.")
        print(f"Token prefix: {result_token[:8]}...")
        print("Cached at data/kite_token.json and synced to .env")
    except KiteAutoLoginError as exc:
        print(f"Auto-login failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
