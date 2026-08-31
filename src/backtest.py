"""Backtest engine for multi-market Indian strategies."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from config import MARKETS, MAX_POSITIONS
from src.data_loader import load_market_data
from src.risk import (
    Position,
    Portfolio,
    calc_position_size,
    calc_stop,
    correlation_blocks_new_trade,
    portfolio_equity,
)
from src.strategies import mean_reversion, momentum_breakout, trend_following

STRATEGY_MAP = {
    "mean_reversion": mean_reversion.generate_signals,
    "momentum_breakout": momentum_breakout.generate_signals,
    "trend_following": trend_following.generate_signals,
}


def _open_position(
    portfolio: Portfolio,
    symbol: str,
    side: int,
    price: float,
    atr: float,
    group: str,
    ts,
) -> bool:
    if symbol in portfolio.positions:
        return False
    if len(portfolio.positions) >= MAX_POSITIONS:
        return False
    if correlation_blocks_new_trade(symbol, side, group, portfolio.positions):
        return False

    equity = portfolio_equity(portfolio, {symbol: price})
    qty = calc_position_size(equity, price, atr)
    if qty <= 0:
        return False

    cost = price * qty
    if side == 1 and portfolio.cash < cost:
        qty = portfolio.cash / price
        cost = price * qty
    if qty <= 0:
        return False

    stop = calc_stop(price, side, atr)
    if side == 1:
        portfolio.cash -= cost
    else:
        portfolio.cash += cost

    portfolio.positions[symbol] = Position(
        symbol=symbol,
        side=side,
        entry_price=price,
        quantity=qty,
        stop_price=stop,
        group=group,
        entry_time=ts,
    )
    return True


def _close_position(portfolio: Portfolio, symbol: str, price: float, ts, reason: str):
    pos = portfolio.positions.pop(symbol)
    if pos.side == 1:
        proceeds = price * pos.quantity
        portfolio.cash += proceeds
        pnl = (price - pos.entry_price) * pos.quantity
    else:
        cost = price * pos.quantity
        portfolio.cash -= cost
        pnl = (pos.entry_price - price) * pos.quantity

    portfolio.trades.append(
        {
            "symbol": symbol,
            "side": "long" if pos.side == 1 else "short",
            "entry_time": pos.entry_time,
            "exit_time": ts,
            "entry_price": pos.entry_price,
            "exit_price": price,
            "quantity": pos.quantity,
            "pnl": pnl,
            "reason": reason,
        }
    )


def _check_stops(portfolio: Portfolio, bar: pd.Series, symbol: str, ts):
    pos = portfolio.positions.get(symbol)
    if not pos:
        return
    if pos.side == 1 and bar["Low"] <= pos.stop_price:
        _close_position(portfolio, symbol, pos.stop_price, ts, "stop_loss")
    elif pos.side == -1 and bar["High"] >= pos.stop_price:
        _close_position(portfolio, symbol, pos.stop_price, ts, "stop_loss")


def run_backtest(*, refresh: bool = False) -> dict:
    """Run backtest across all configured Indian markets."""
    market_data: dict[str, pd.DataFrame] = {}
    market_meta: dict[str, object] = {}

    for m in MARKETS:
        df = load_market_data(m.symbol, m.interval, refresh=refresh)
        signals = STRATEGY_MAP[m.strategy](df)
        market_data[m.symbol] = signals
        market_meta[m.symbol] = m

    # Align on union of timestamps (each market runs on its own clock)
    portfolio = Portfolio()
    all_times = sorted(
        {ts for df in market_data.values() for ts in df.index}
    )

    for ts in all_times:
        prices = {}
        for symbol, df in market_data.items():
            if ts not in df.index:
                continue
            row = df.loc[ts]
            prices[symbol] = row["Close"]
            _check_stops(portfolio, row, symbol, ts)

            meta = market_meta[symbol]
            signal = int(row.get("signal", 0) or 0)
            atr = float(row.get("atr", 0) or 0)

            if symbol in portfolio.positions:
                pos = portfolio.positions[symbol]
                # Exit on opposite signal for mean reversion / breakout
                if meta.strategy in ("mean_reversion", "momentum_breakout"):
                    if signal != 0 and signal != pos.side:
                        _close_position(
                            portfolio, symbol, row["Close"], ts, "signal_exit"
                        )
                elif meta.strategy == "trend_following" and signal != pos.side:
                    _close_position(
                        portfolio, symbol, row["Close"], ts, "trend_exit"
                    )
            elif signal != 0 and atr > 0:
                _open_position(
                    portfolio,
                    symbol,
                    signal,
                    row["Close"],
                    atr,
                    meta.group,
                    ts,
                )

        eq = portfolio_equity(portfolio, prices)
        portfolio.equity_curve.append((ts, eq))

    final_equity = portfolio.equity_curve[-1][1] if portfolio.equity_curve else portfolio.cash
    return {
        "initial_capital": portfolio.cash if not portfolio.trades else __import__("config").INITIAL_CAPITAL,
        "final_equity": final_equity,
        "total_return_pct": (final_equity / __import__("config").INITIAL_CAPITAL - 1) * 100,
        "num_trades": len(portfolio.trades),
        "trades": portfolio.trades,
        "equity_curve": portfolio.equity_curve,
        "open_positions": [asdict(p) for p in portfolio.positions.values()],
    }


def summarize_results(results: dict) -> str:
    trades = results["trades"]
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    total_pnl = sum(t["pnl"] for t in trades)

    by_symbol: dict[str, list] = {}
    for t in trades:
        by_symbol.setdefault(t["symbol"], []).append(t["pnl"])

    lines = [
        "=" * 60,
        "INDIA PAPER TRADING - BACKTEST SUMMARY",
        "=" * 60,
        f"Initial capital : Rs {__import__('config').INITIAL_CAPITAL:,.0f}",
        f"Final equity    : Rs {results['final_equity']:,.0f}",
        f"Total return    : {results['total_return_pct']:.2f}%",
        f"Trades          : {results['num_trades']}",
        f"Win rate        : {win_rate:.1f}%",
        f"Realized P&L    : Rs {total_pnl:,.0f}",
        "",
        "Per symbol:",
    ]
    for sym, pnls in by_symbol.items():
        lines.append(f"  {sym:16s}  {len(pnls):3d} trades  Rs {sum(pnls):,.0f}")
    if results["open_positions"]:
        lines.extend(["", "Open positions:"])
        for p in results["open_positions"]:
            lines.append(f"  {p['symbol']} {p['side']} @ {p['entry_price']:.2f}")
    lines.append("=" * 60)
    return "\n".join(lines)
