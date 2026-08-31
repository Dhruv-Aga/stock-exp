"""Momentum breakout: trade 1h range breaks with volume confirmation."""

from __future__ import annotations

import pandas as pd
import ta

from config import MOMENTUM_BREAKOUT


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cfg = MOMENTUM_BREAKOUT
    lookback = cfg["lookback"]

    out["high_n"] = out["High"].rolling(lookback).max().shift(1)
    out["low_n"] = out["Low"].rolling(lookback).min().shift(1)
    out["vol_avg"] = out["Volume"].rolling(lookback).mean()
    out["atr"] = ta.volatility.AverageTrueRange(
        out["High"], out["Low"], out["Close"], window=cfg["atr_period"]
    ).average_true_range()

    vol_ok = out["Volume"] > (out["vol_avg"] * cfg["volume_mult"])
    out["signal"] = 0
    out.loc[(out["Close"] > out["high_n"]) & vol_ok, "signal"] = 1
    out.loc[(out["Close"] < out["low_n"]) & vol_ok, "signal"] = -1
    return out
