"""Mean reversion: fade extremes on 15m candles."""

from __future__ import annotations

import pandas as pd
import ta

from config import MEAN_REVERSION


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cfg = MEAN_REVERSION

    bb = ta.volatility.BollingerBands(
        out["Close"], window=cfg["bb_period"], window_dev=cfg["bb_std"]
    )
    out["bb_upper"] = bb.bollinger_hband()
    out["bb_lower"] = bb.bollinger_lband()
    out["bb_mid"] = bb.bollinger_mavg()
    out["rsi"] = ta.momentum.RSIIndicator(out["Close"], window=cfg["rsi_period"]).rsi()
    out["atr"] = ta.volatility.AverageTrueRange(
        out["High"], out["Low"], out["Close"], window=14
    ).average_true_range()

    out["signal"] = 0
    long_mask = (out["Close"] < out["bb_lower"]) & (out["rsi"] < cfg["rsi_oversold"])
    short_mask = (out["Close"] > out["bb_upper"]) & (out["rsi"] > cfg["rsi_overbought"])
    out.loc[long_mask, "signal"] = 1
    out.loc[short_mask, "signal"] = -1
    return out
