"""Tests for risk management and strategy signals."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.risk import (  # noqa: E402
    Position,
    calc_position_size,
    calc_stop,
    correlation_blocks_new_trade,
    portfolio_equity,
)
from src.strategies.mean_reversion import generate_signals as mr_signals
from src.strategies.momentum_breakout import generate_signals as mo_signals
from src.strategies.trend_following import generate_signals as tf_signals


def _sample_ohlcv(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = close + rng.normal(0, 0.2, n)
    vol = rng.integers(100_000, 500_000, n)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_position_size_scales_with_atr():
  small = calc_position_size(100_000, 100, atr=1.0)
  large = calc_position_size(100_000, 100, atr=5.0)
  assert small > large


def test_stop_long_below_entry():
  stop = calc_stop(100, side=1, atr=2)
  assert stop == 98


def test_stop_short_above_entry():
  stop = calc_stop(100, side=-1, atr=2)
  assert stop == 102


def test_correlation_filter_blocks_second_vedanta_long():
    positions = {
        "VEDL.NS": Position("VEDL.NS", 1, 300, 1, 290, "vedanta"),
    }
    blocked = correlation_blocks_new_trade("VAML.NS", 1, "vedanta", positions)
    assert blocked is True


def test_correlation_filter_allows_different_direction():
    positions = {
        "VEDL.NS": Position("VEDL.NS", 1, 300, 1, 290, "vedanta"),
    }
    blocked = correlation_blocks_new_trade("VAML.NS", -1, "vedanta", positions)
    assert blocked is False


def test_portfolio_equity_long_position():
  from src.risk import Portfolio

  p = Portfolio(cash=90_000)
  p.positions["TEST"] = Position("TEST", 1, 100, 100, 95, "equity")
  eq = portfolio_equity(p, {"TEST": 110})
  assert eq == pytest.approx(101_000)


def test_mean_reversion_adds_signal_column():
  df = mr_signals(_sample_ohlcv())
  assert "signal" in df.columns
  assert set(df["signal"].dropna().unique()).issubset({-1, 0, 1})


def test_momentum_breakout_adds_signal_column():
  df = mo_signals(_sample_ohlcv())
  assert "signal" in df.columns


def test_trend_following_holds_position():
  df = _sample_ohlcv(200)
  out = tf_signals(df)
  # After warmup, position should be sustained (-1, 0, or 1)
  tail = out["signal"].iloc[60:]
  assert tail.isin([-1, 0, 1]).all()
