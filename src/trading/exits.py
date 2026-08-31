"""Shared exit decision logic for paper and live sessions."""

from __future__ import annotations


def should_exit_position(*, strategy: str, signal: int, position_side: int) -> tuple[bool, str]:
    """
    Return whether to close an open position and the exit reason code.

    Matches paper trading behaviour (including trend-following flat-signal exits).
    """
    if strategy == "trend_following":
        if signal != position_side:
            return True, "trend_exit"
        return False, ""

    # mean_reversion, momentum_breakout
    if signal != 0 and signal != position_side:
        return True, "signal_exit"
    return False, ""


def stop_loss_hit(*, position_side: int, stop_price: float, bar_low: float, bar_high: float) -> bool:
    if position_side == 1:
        return bar_low <= stop_price
    if position_side == -1:
        return bar_high >= stop_price
    return False
