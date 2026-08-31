"""Indian market configuration for paper trading and backtests."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketConfig:
    symbol: str
    name: str
    strategy: str
    interval: str
    group: str
    kite_symbol: str
    kite_exchange: str = "NSE"
    kite_product: str = "CNC"  # CNC delivery equity/ETF; use MIS for intraday
    allow_short: bool = False  # requires F&O when True


# NSE equities via yfinance (.NS suffix)
MARKETS: list[MarketConfig] = [
    MarketConfig(
        "VAML.NS", "Vedanta Aluminium", "mean_reversion", "15m", "vedanta",
        kite_symbol="VAML", kite_product="CNC", allow_short=False,
    ),
    MarketConfig(
        "VEDL.NS", "Vedanta", "momentum_breakout", "1h", "vedanta",
        kite_symbol="VEDL", kite_product="CNC", allow_short=False,
    ),
    MarketConfig(
        "VEDPOWER.NS", "Vedanta Power", "momentum_breakout", "1h", "vedanta",
        kite_symbol="VEDPOWER", kite_product="CNC", allow_short=False,
    ),
    MarketConfig(
        "VISL.NS", "Vedanta Iron & Steel", "trend_following", "4h", "vedanta",
        kite_symbol="VISL", kite_product="CNC", allow_short=False,
    ),
    MarketConfig(
        "BHEL.NS", "BHEL", "trend_following", "4h", "industrial",
        kite_symbol="BHEL", kite_product="CNC", allow_short=False,
    ),
]

INITIAL_CAPITAL = 100_000.0  # INR
RISK_PER_TRADE = 0.01  # 1% hard stop risk per trade
MAX_POSITIONS = 5
CORRELATION_GROUPS = {
    # Avoid stacking long exposure across demerged Vedanta entities
    "vedanta": ["VAML.NS", "VEDL.NS", "VEDPOWER.NS", "VISL.NS"],
}

# Strategy parameters
MEAN_REVERSION = {
    "bb_period": 20,
    "bb_std": 2.0,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
}

MOMENTUM_BREAKOUT = {
    "lookback": 20,
    "volume_mult": 1.5,
    "atr_period": 14,
}

TREND_FOLLOWING = {
    "ema_fast": 20,
    "ema_slow": 50,
    "atr_period": 14,
}

# Kite candle interval mapping
KITE_INTERVAL_MAP = {
    "15m": "15minute",
    "1h": "60minute",
    "4h": "60minute",  # resampled from 60minute
}

# NSE market hours (IST) - bot should not place orders outside these windows
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30
