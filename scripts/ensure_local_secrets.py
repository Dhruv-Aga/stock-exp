#!/usr/bin/env python3
"""Ensure .env has BHARAT_SCOUT_API_KEY and Zerodha auto-login placeholders."""

from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def _ensure_key(lines: list[str], key: str, value: str | None = None) -> list[str]:
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            if value and not line[len(prefix) :].strip():
                lines[i] = f"{key}={value}"
            return lines
    if value:
        lines.append(f"{key}={value}")
    else:
        lines.append(f"{key}=")
    return lines


def main() -> None:
    if not ENV.exists():
        if EXAMPLE.exists():
            ENV.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
            print("Created .env from .env.example")
        else:
            ENV.write_text("", encoding="utf-8")

    lines = ENV.read_text(encoding="utf-8").splitlines()
    api_key = None
    for line in lines:
        if line.startswith("BHARAT_SCOUT_API_KEY=") and line.split("=", 1)[1].strip():
            api_key = line.split("=", 1)[1].strip()
            break
    if not api_key:
        api_key = secrets.token_urlsafe(32)
        lines = _ensure_key(lines, "BHARAT_SCOUT_API_KEY", api_key)
        print(f"Generated BHARAT_SCOUT_API_KEY (also in .env)")

    for key in ("ZERODHA_USER_ID", "ZERODHA_PASSWORD", "ZERODHA_TOTP_SECRET"):
        lines = _ensure_key(lines, key)

    ENV.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    try:
        ENV.chmod(0o600)
    except OSError:
        pass


if __name__ == "__main__":
    main()
