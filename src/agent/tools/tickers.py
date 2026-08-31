"""Ticker data tools."""

from __future__ import annotations

from typing import Any

from config import MARKETS
from src import settings
from src.broker.kite_client import KiteClient
from src.data_loader import load_market_data


def list_configured_tickers(_args: dict[str, Any]) -> dict[str, Any]:
    tickers = [
        {
            "symbol": m.symbol,
            "name": m.name,
            "strategy": m.strategy,
            "interval": m.interval,
            "group": m.group,
            "kite_symbol": m.kite_symbol,
        }
        for m in MARKETS
    ]
    return {"tickers": tickers, "count": len(tickers)}


def _normalize_symbol(symbol: str) -> str:
    sym = symbol.upper().strip()
    if not sym.endswith(".NS"):
        sym = f"{sym}.NS"
    return sym


def get_ticker_quote(args: dict[str, Any]) -> dict[str, Any]:
    symbol = _normalize_symbol(args["symbol"])
    use_kite = args.get("use_kite", False)

    if use_kite:
        settings.load_settings()
        if settings.kite_configured():
            client = KiteClient(dry_run=False)
            quote = client.quote(symbol)
            if quote:
                ohlc = quote.get("ohlc", {})
                return {
                    "symbol": symbol,
                    "ltp": quote.get("last_price"),
                    "change": quote.get("change"),
                    "change_pct": quote.get("change_percent"),
                    "ohlc": ohlc,
                    "source": "kite",
                }

    df = load_market_data(symbol, "1h", refresh=False)
    if df.empty:
        raise ValueError(f"No quote data for {symbol}")

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    ltp = float(latest["Close"])
    change_pct = ((ltp / float(prev["Close"])) - 1) * 100 if float(prev["Close"]) else 0

    return {
        "symbol": symbol,
        "ltp": round(ltp, 2),
        "change_pct": round(change_pct, 2),
        "bar_time": str(df.index[-1]),
        "source": "yfinance",
    }


def get_ticker_history(args: dict[str, Any]) -> dict[str, Any]:
    symbol = _normalize_symbol(args["symbol"])
    interval = args.get("interval", "1h")
    bars = int(args.get("bars", 20))
    refresh = args.get("refresh", False)

    df = load_market_data(symbol, interval, refresh=refresh)
    tail = df.tail(bars)
    rows = [
        {
            "time": str(idx),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        for idx, row in tail.iterrows()
    ]
    return {"symbol": symbol, "interval": interval, "bars": rows, "count": len(rows)}
