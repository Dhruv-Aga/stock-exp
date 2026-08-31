"""Kill switch, daily loss limits, and market hours checks."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from config import MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE
from src import settings
from src.db import get_state, get_today_realized_pnl, set_state

IST = ZoneInfo("Asia/Kolkata")


class SafetyHalt(Exception):
    pass


def is_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(IST)
    if now.weekday() >= 5:
        return False
    open_t = time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
    close_t = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    return open_t <= now.time() <= close_t


def enable_kill_switch(reason: str = "manual") -> None:
    set_state("kill_switch", "on")
    set_state("kill_switch_reason", reason)


def disable_kill_switch() -> None:
    set_state("kill_switch", "off")
    set_state("kill_switch_reason", "")


def kill_switch_active() -> bool:
    if settings.kill_switch_enabled():
        return True
    return get_state("kill_switch", "off") == "on"


def check_can_trade(*, require_market_open: bool = True) -> None:
    if kill_switch_active():
        reason = get_state("kill_switch_reason", "kill switch enabled")
        raise SafetyHalt(f"Trading halted: {reason}")

    today_pnl = get_today_realized_pnl()
    max_loss = settings.max_daily_loss()
    if today_pnl <= -max_loss:
        raise SafetyHalt(
            f"Daily loss limit hit: Rs {today_pnl:,.0f} (limit Rs {max_loss:,.0f})"
        )

    if require_market_open and not is_market_open():
        raise SafetyHalt("Market is closed (NSE 09:15-15:30 IST, Mon-Fri)")
