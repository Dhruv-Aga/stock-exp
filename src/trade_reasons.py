"""Human-readable trade entry and exit reasons."""

from __future__ import annotations

from config import MARKETS, MEAN_REVERSION, MOMENTUM_BREAKOUT, TREND_FOLLOWING

SYMBOL_NAMES = {m.symbol: m.name for m in MARKETS}
STRATEGY_BY_SYMBOL = {m.symbol: m.strategy for m in MARKETS}

EXIT_LABELS = {
    "stop_loss": "Stop loss hit (1 ATR hard stop)",
    "signal_exit": "Opposite strategy signal (mean reversion / momentum)",
    "trend_exit": "Trend reversed (EMA crossover)",
}


def exit_reason_label(code: str) -> str:
    return EXIT_LABELS.get(code, code.replace("_", " ").title())


def entry_reason(strategy: str, side: int, row) -> str:
    """Describe why a new position was opened on the latest bar."""
    direction = "Long" if side == 1 else "Short"

    if strategy == "mean_reversion":
        cfg = MEAN_REVERSION
        if side == 1:
            return (
                f"{direction}: price below lower Bollinger Band "
                f"and RSI < {cfg['rsi_oversold']} (mean reversion buy)"
            )
        return (
            f"{direction}: price above upper Bollinger Band "
            f"and RSI > {cfg['rsi_overbought']} (mean reversion sell)"
        )

    if strategy == "momentum_breakout":
        lookback = MOMENTUM_BREAKOUT["lookback"]
        vol_mult = MOMENTUM_BREAKOUT["volume_mult"]
        if side == 1:
            return (
                f"{direction}: close broke above {lookback}-bar high "
                f"with volume > {vol_mult}x average (momentum breakout)"
            )
        return (
            f"{direction}: close broke below {lookback}-bar low "
            f"with volume > {vol_mult}x average (momentum breakdown)"
        )

    if strategy == "trend_following":
        cfg = TREND_FOLLOWING
        if side == 1:
            return (
                f"{direction}: fast EMA({cfg['ema_fast']}) crossed above "
                f"slow EMA({cfg['ema_slow']}) (trend following)"
            )
        return (
            f"{direction}: fast EMA({cfg['ema_fast']}) crossed below "
            f"slow EMA({cfg['ema_slow']}) (trend following)"
        )

    return f"{direction}: strategy signal on latest bar"


def trade_reason_summary(*, entry_reason: str, exit_reason: str) -> str:
    return f"Entry: {entry_reason} | Exit: {exit_reason_label(exit_reason)}"


def symbol_label(symbol: str) -> str:
    return SYMBOL_NAMES.get(symbol, symbol)
