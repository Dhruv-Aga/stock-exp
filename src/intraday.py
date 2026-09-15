"""Intraday paper session scheduling helpers (NSE IST)."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.db import get_state, set_state
from src.safety import is_market_open

IST = ZoneInfo("Asia/Kolkata")
STATE_KEY = "paper_intraday_last_bars"


def should_run_intraday_session(*, force: bool = False) -> tuple[bool, str]:
    if force:
        return True, "forced"
    if not is_market_open():
        return False, "market closed (NSE Mon-Fri 09:15-15:30 IST)"
    return True, "market open"


def record_session_bars(data_as_of: dict[str, str]) -> None:
    if not data_as_of:
        return
    set_state(STATE_KEY, json.dumps(data_as_of, sort_keys=True))


def bars_changed_since_last_run(data_as_of: dict[str, str]) -> bool:
    if not data_as_of:
        return True
    raw = get_state(STATE_KEY, "")
    if not raw:
        return True
    try:
        previous = json.loads(raw)
    except json.JSONDecodeError:
        return True
    return previous != data_as_of


def session_stamp() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
