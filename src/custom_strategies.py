"""User-defined strategy registry and evaluator used by paper sessions."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pandas as pd
import ta

from src.data import FUNDAMENTALS
from src.data_loader import load_market_data
from src.db import list_custom_strategies, save_custom_strategy


STOP_WORDS = {
    "EMA",
    "RSI",
    "BOLLINGER",
    "VOLUME",
    "MA",
    "MOVING",
    "AVERAGE",
    "TREND",
    "BREAKOUT",
    "MEAN",
    "REVERSION",
    "STRATEGY",
    "SIGNAL",
    "ENTRY",
    "EXIT",
    "BUY",
    "SELL",
    "LONG",
    "SHORT",
    "WHEN",
    "AND",
    "OR",
    "THEN",
    "USE",
    "WITH",
    "FOR",
}


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper().replace(" ", "")
    if not symbol:
        return symbol
    if symbol.endswith(".NS"):
        return symbol
    return f"{symbol}.NS" if len(symbol) <= 10 else symbol


def extract_symbols(text: str | None, fallback: list[str] | None = None) -> list[str]:
    candidates = []
    if text:
        raw = re.findall(r"\b[A-Z]{2,10}(?:\.[A-Z]{2})?\b", text.upper())
        for token in raw:
            if token in STOP_WORDS:
                continue
            if token == "NS":
                continue
            if token.endswith(".NS"):
                candidates.append(token)
            else:
                candidates.append(token)
    if fallback:
        for item in fallback:
            if item not in candidates:
                candidates.append(item)
    unique = []
    seen = set()
    for sym in candidates:
        key = sym.upper()
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique[:10]


def _coerce_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_strategy_prompt(prompt: str, *, name: str | None = None, symbols: list[str] | None = None) -> dict:
    text = (prompt or "").strip()
    config = {
        "strategy_type": "custom",
        "fast_ema": 20,
        "slow_ema": 50,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bb_period": 20,
        "bb_std": 2.0,
        "volume_mult": 1.5,
        "interval": "1h",
    }
    lower = text.lower()
    if any(word in lower for word in ("trend", "ema crossover", "moving average")):
        config["strategy_type"] = "trend_following"
    elif any(word in lower for word in ("mean reversion", "bollinger", "oversold", "overbought")):
        config["strategy_type"] = "mean_reversion"
    elif any(word in lower for word in ("breakout", "volume spike", "momentum")):
        config["strategy_type"] = "momentum_breakout"
    
    ema_match = re.findall(r"ema\s*(?:fast\s*)?(\d+)\s*(?:/|,|and|to)?\s*(\d+)?", text, flags=re.I)
    if ema_match:
        first, second = ema_match[0]
        config["fast_ema"] = _coerce_int(first, config["fast_ema"])
        if second:
            config["slow_ema"] = _coerce_int(second, config["slow_ema"])
    rsi_match = re.search(r"rsi\s*(\d+)", text, flags=re.I)
    if rsi_match:
        config["rsi_period"] = _coerce_int(rsi_match.group(1), config["rsi_period"])
    oversold_match = re.search(r"oversold\s*(\d+)", text, flags=re.I)
    if oversold_match:
        config["rsi_oversold"] = _coerce_int(oversold_match.group(1), config["rsi_oversold"])
    overbought_match = re.search(r"overbought\s*(\d+)", text, flags=re.I)
    if overbought_match:
        config["rsi_overbought"] = _coerce_int(overbought_match.group(1), config["rsi_overbought"])
    bg_match = re.search(r"bollinger\s*(?:band\s*)?(\d+)", text, flags=re.I)
    if bg_match:
        config["bb_period"] = _coerce_int(bg_match.group(1), config["bb_period"])
    vol_match = re.search(r"volume\s*(?:surge|spike|mult|x)?\s*(\d+(?:\.\d+)?)", text, flags=re.I)
    if vol_match:
        config["volume_mult"] = float(vol_match.group(1))
    interval_match = re.search(r"(15m|1h|4h)", text, flags=re.I)
    if interval_match:
        config["interval"] = interval_match.group(1).lower()

    extracted = extract_symbols(text, fallback=symbols or [])
    result = {
        "name": (name or "Custom Strategy").strip() or "Custom Strategy",
        "description": text,
        "symbols": [normalize_symbol(sym) for sym in extracted if sym and sym != ""],
        "config": config,
        "enabled": True,
    }
    if not result["symbols"]:
        result["symbols"] = [normalize_symbol(sym) for sym in (list(FUNDAMENTALS.keys())[:5] or [])]
    return result


def _rsi_signal(series: pd.Series, period: int, oversold: int, overbought: int) -> float:
    if series.empty:
        return 0.0
    rsi = ta.momentum.RSIIndicator(series, window=period).rsi()
    last = float(rsi.iloc[-1])
    if last < oversold:
        return 1.0
    if last > overbought:
        return -1.0
    return 0.0


def evaluate_custom_strategy(df: pd.DataFrame, config: dict | None = None) -> tuple[int, str]:
    if df is None or df.empty:
        return 0, "No data"
    cfg = config or {}
    strategy_type = cfg.get("strategy_type", "custom")
    close = pd.to_numeric(df["Close"], errors="coerce")
    volume = pd.to_numeric(df.get("Volume", pd.Series(1, index=df.index)), errors="coerce")
    fast_ema = cfg.get("fast_ema", 20)
    slow_ema = cfg.get("slow_ema", 50)
    rsi_period = cfg.get("rsi_period", 14)
    rsi_oversold = cfg.get("rsi_oversold", 30)
    rsi_overbought = cfg.get("rsi_overbought", 70)
    bb_period = cfg.get("bb_period", 20)
    bb_std = float(cfg.get("bb_std", 2.0) or 2.0)
    volume_mult = float(cfg.get("volume_mult", 1.5) or 1.5)

    fast = close.ewm(span=fast_ema, adjust=False).mean()
    slow = close.ewm(span=slow_ema, adjust=False).mean()
    bb = ta.volatility.BollingerBands(close, window=bb_period, window_dev=bb_std)
    upper_band = bb.bollinger_hband()
    lower_band = bb.bollinger_lband()
    volume_avg = volume.rolling(window=max(5, int(bb_period / 2))).mean()
    rsi = ta.momentum.RSIIndicator(close, window=rsi_period).rsi()
    latest_close = float(close.iloc[-1])
    latest_fast = float(fast.iloc[-1])
    latest_slow = float(slow.iloc[-1])
    latest_rsi = float(rsi.iloc[-1])
    latest_upper = float(upper_band.iloc[-1])
    latest_lower = float(lower_band.iloc[-1])
    latest_vol = float(volume.iloc[-1])
    latest_vol_avg = float(volume_avg.iloc[-1])

    if strategy_type == "trend_following":
        if latest_fast > latest_slow:
            return 1, f"EMA {fast_ema} crossed above EMA {slow_ema}"
        if latest_fast < latest_slow:
            return -1, f"EMA {fast_ema} crossed below EMA {slow_ema}"
        return 0, "EMA trend neutral"

    if strategy_type == "mean_reversion":
        if latest_close > latest_upper and latest_rsi > rsi_overbought:
            return -1, "Price above upper band with RSI overbought"
        if latest_close < latest_lower and latest_rsi < rsi_oversold:
            return 1, "Price below lower band with RSI oversold"
        return 0, "Mean-reversion conditions not met"

    if strategy_type == "momentum_breakout":
        breakout = close > close.rolling(window=max(10, fast_ema)).max().shift(1)
        volume_signal = latest_vol > (latest_vol_avg * volume_mult)
        if breakout.iloc[-1] and volume_signal:
            return 1, "Breakout above recent high with strong volume"
        if (close < close.rolling(window=max(10, fast_ema)).min().shift(1)) and volume_signal:
            return -1, "Breakdown below recent low with strong volume"
        return 0, "Breakout conditions not met"

    if strategy_type == "custom":
        long_flag = latest_fast > latest_slow and latest_rsi < rsi_overbought
        short_flag = latest_fast < latest_slow and latest_rsi > rsi_oversold
        if long_flag:
            return 1, f"Custom signal: EMA {fast_ema} > EMA {slow_ema} and RSI not stretched"
        if short_flag:
            return -1, f"Custom signal: EMA {fast_ema} < EMA {slow_ema} and RSI stretched"
        return 0, "Custom signal neutral"

    return 0, "Unsupported strategy type"


def create_saved_strategy_from_prompt(prompt: str, *, name: str | None = None, symbols: list[str] | None = None) -> dict:
    payload = parse_strategy_prompt(prompt, name=name, symbols=symbols)
    return save_custom_strategy(
        name=payload["name"],
        description=payload["description"],
        symbols=payload["symbols"],
        config=payload["config"],
        enabled=payload["enabled"],
        author="agent",
    )


def active_custom_strategies() -> list[dict]:
    return list_custom_strategies(enabled_only=True)


def iter_custom_session_bars(*, refresh: bool = False):
    bars = []
    for strategy in active_custom_strategies():
        symbols = strategy.get("symbols") or []
        if not symbols:
            continue
        cfg = strategy.get("config") or {}
        interval = cfg.get("interval", "1h")
        for sym in symbols:
            try:
                symbol = normalize_symbol(sym)
                df = load_market_data(symbol, interval, refresh=refresh)
                if df.empty:
                    continue
                signal, reason = evaluate_custom_strategy(df, cfg)
                if signal == 0:
                    continue
                latest = df.iloc[-1]
                bars.append(
                    SimpleNamespace(
                        market=SimpleNamespace(
                            symbol=symbol,
                            name=str(strategy.get("name") or symbol),
                            strategy=strategy.get("name") or "custom_strategy",
                            group="custom",
                            interval=interval,
                        ),
                        row=latest,
                        ts=df.index[-1],
                        price=float(latest["Close"]),
                        atr=float(latest.get("atr", 0) or 0),
                        signal=signal,
                        entry_reason_text=reason,
                    )
                )
            except Exception:
                continue
    return bars
