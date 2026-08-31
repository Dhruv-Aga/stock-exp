"""Trend following: ride EMA crossovers on slower 4h waves (gold / oil proxies)."""

from __future__ import annotations

import pandas as pd
import ta

from config import TREND_FOLLOWING


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cfg = TREND_FOLLOWING

    out["ema_fast"] = ta.trend.EMAIndicator(
        out["Close"], window=cfg["ema_fast"]
    ).ema_indicator()
    out["ema_slow"] = ta.trend.EMAIndicator(
        out["Close"], window=cfg["ema_slow"]
    ).ema_indicator()
    out["atr"] = ta.volatility.AverageTrueRange(
        out["High"], out["Low"], out["Close"], window=cfg["atr_period"]
    ).average_true_range()

    out["signal"] = 0
    cross_up = (out["ema_fast"] > out["ema_slow"]) & (
        out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)
    )
    cross_down = (out["ema_fast"] < out["ema_slow"]) & (
        out["ema_fast"].shift(1) >= out["ema_slow"].shift(1)
    )
    out.loc[cross_up, "signal"] = 1
    out.loc[cross_down, "signal"] = -1

    # Hold trend until opposite cross
    position = 0
    positions = []
    for sig in out["signal"]:
        if sig != 0:
            position = sig
        positions.append(position)
    out["signal"] = positions
    return out
