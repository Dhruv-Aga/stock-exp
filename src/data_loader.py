"""Fetch and cache OHLCV data for Indian NSE symbols."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

# yfinance intraday history limits (approximate)
INTRADAY_LOOKBACK = {
    "15m": 59,
    "1h": 729,
    "4h": 729,
}


def _cache_path(symbol: str, interval: str) -> Path:
    safe = symbol.replace("^", "").replace(".", "_")
    return CACHE_DIR / f"{safe}_{interval}.csv"


def fetch_ohlcv(
    symbol: str,
    interval: str,
    *,
    use_cache: bool = True,
    refresh: bool = False,
) -> pd.DataFrame:
    """Download OHLCV bars for an Indian symbol."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(symbol, interval)

    if use_cache and cache_file.exists() and not refresh:
        df = pd.read_csv(cache_file, parse_dates=["Datetime"], index_col="Datetime")
        if not df.empty:
            return df

    days = INTRADAY_LOOKBACK.get(interval, 59)
    start = datetime.now() - timedelta(days=days)

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {symbol} at {interval}")

    df = df.rename(columns=str.title)
    df.index.name = "Datetime"
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.to_csv(cache_file)
    return df


def resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """Build 4h bars from 1h data when direct 4h fetch is unavailable."""
    ohlc = df.resample("4h").agg(
        {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
    )
    return ohlc.dropna()


def load_market_data(
    symbol: str,
    interval: str,
    *,
    refresh: bool = False,
    prefer_kite: bool = False,
    kite_client=None,
) -> pd.DataFrame:
    if prefer_kite and kite_client is not None:
        days = INTRADAY_LOOKBACK.get(interval, 59)
        kite_df = kite_client.historical_data(symbol, interval, days=days)
        if kite_df is not None and not kite_df.empty:
            if interval == "4h":
                return resample_to_4h(kite_df)
            return kite_df

    if interval == "4h":
        try:
            return fetch_ohlcv(symbol, "4h", refresh=refresh)
        except Exception:
            hourly = fetch_ohlcv(symbol, "1h", refresh=refresh)
            return resample_to_4h(hourly)
    return fetch_ohlcv(symbol, interval, refresh=refresh)
