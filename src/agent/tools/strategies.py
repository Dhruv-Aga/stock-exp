"""Trading strategy tools — one tool per strategy plus combined signal scan."""

from __future__ import annotations

from typing import Any

from config import MARKETS
from src.backtest import STRATEGY_MAP
from src.data_loader import load_market_data
from src.trade_reasons import entry_reason, symbol_label


def _market_for_symbol(symbol: str):
    sym = symbol.upper().strip()
    if not sym.endswith(".NS"):
        sym = f"{sym}.NS"
    for market in MARKETS:
        if market.symbol.upper() == sym:
            return market
    return None


def _latest_signal(symbol: str, strategy_key: str, *, refresh: bool = False) -> dict[str, Any]:
    market = _market_for_symbol(symbol)
    if market is None:
        raise ValueError(f"Symbol {symbol} is not in configured MARKETS")

    if market.strategy != strategy_key:
        raise ValueError(
            f"{symbol} uses strategy '{market.strategy}', not '{strategy_key}'. "
            f"Use the matching strategy tool or get_all_strategy_signals."
        )

    df = load_market_data(market.symbol, market.interval, refresh=refresh)
    if df.empty:
        raise ValueError(f"No market data for {market.symbol}")

    signals_df = STRATEGY_MAP[strategy_key](df)
    latest = signals_df.iloc[-1]
    bar_time = str(signals_df.index[-1])
    signal = int(latest.get("signal", 0))
    price = float(latest["Close"])
    atr = float(latest.get("atr", 0) or 0)

    labels = {1: "LONG", -1: "SHORT", 0: "FLAT"}
    return {
        "symbol": market.symbol,
        "name": market.name,
        "strategy": strategy_key,
        "interval": market.interval,
        "bar_time": bar_time,
        "price": round(price, 2),
        "atr": round(atr, 4),
        "signal": signal,
        "signal_label": labels.get(signal, "FLAT"),
        "entry_reason": entry_reason(strategy_key, signal, latest) if signal != 0 else None,
    }


def run_mean_reversion_strategy(args: dict[str, Any]) -> dict[str, Any]:
    return _latest_signal(args["symbol"], "mean_reversion", refresh=args.get("refresh", False))


def run_momentum_breakout_strategy(args: dict[str, Any]) -> dict[str, Any]:
    return _latest_signal(args["symbol"], "momentum_breakout", refresh=args.get("refresh", False))


def run_trend_following_strategy(args: dict[str, Any]) -> dict[str, Any]:
    return _latest_signal(args["symbol"], "trend_following", refresh=args.get("refresh", False))


def get_all_strategy_signals(args: dict[str, Any]) -> dict[str, Any]:
    refresh = args.get("refresh", False)
    signals = []
    errors = []

    for market in MARKETS:
        try:
            df = load_market_data(market.symbol, market.interval, refresh=refresh)
            if df.empty:
                errors.append({"symbol": market.symbol, "error": "no data"})
                continue
            signals_df = STRATEGY_MAP[market.strategy](df)
            latest = signals_df.iloc[-1]
            signal = int(latest.get("signal", 0))
            labels = {1: "LONG", -1: "SHORT", 0: "FLAT"}
            signals.append(
                {
                    "symbol": market.symbol,
                    "name": symbol_label(market.symbol),
                    "strategy": market.strategy,
                    "interval": market.interval,
                    "bar_time": str(signals_df.index[-1]),
                    "price": round(float(latest["Close"]), 2),
                    "signal": signal,
                    "signal_label": labels.get(signal, "FLAT"),
                    "entry_reason": entry_reason(market.strategy, signal, latest) if signal != 0 else None,
                }
            )
        except Exception as exc:
            errors.append({"symbol": market.symbol, "error": str(exc)})

    return {"signals": signals, "errors": errors, "count": len(signals)}
