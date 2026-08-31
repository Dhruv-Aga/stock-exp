"""Tests for shared trading exit logic."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.trading.exits import should_exit_position, stop_loss_hit


def test_trend_following_exits_on_flat_signal():
    should, code = should_exit_position(
        strategy="trend_following", signal=0, position_side=1
    )
    assert should is True
    assert code == "trend_exit"


def test_trend_following_holds_on_same_side():
    should, code = should_exit_position(
        strategy="trend_following", signal=1, position_side=1
    )
    assert should is False
    assert code == ""


def test_mean_reversion_exits_on_opposite_signal():
    should, code = should_exit_position(
        strategy="mean_reversion", signal=-1, position_side=1
    )
    assert should is True
    assert code == "signal_exit"


def test_mean_reversion_holds_on_flat_signal():
    should, code = should_exit_position(
        strategy="mean_reversion", signal=0, position_side=1
    )
    assert should is False


def test_stop_loss_long():
    assert stop_loss_hit(position_side=1, stop_price=100, bar_low=99, bar_high=105)


def test_stop_loss_short():
    assert stop_loss_hit(position_side=-1, stop_price=100, bar_low=95, bar_high=101)
