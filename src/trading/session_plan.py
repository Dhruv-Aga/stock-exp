"""Build a trading session plan shared by paper, live, and A/B comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import MARKETS
from src import settings
from src.backtest import STRATEGY_MAP
from src.broker.symbol_map import can_trade_side
from src.data_loader import load_market_data
from src.risk import (
    Portfolio,
    calc_position_size,
    calc_stop,
    correlation_blocks_new_trade,
    portfolio_equity,
)
from src.risk_governor import build_governor_context, evaluate_risk_governor
from src.trade_reasons import entry_reason
from src.trading.exits import should_exit_position, stop_loss_hit


@dataclass
class MarketBar:
    market: Any
    row: Any
    ts: Any
    price: float
    atr: float
    signal: int
    entry_reason_text: str


@dataclass
class ExitIntent:
    symbol: str
    name: str
    side: int
    quantity: float
    price: float
    stop_price: float
    reason_code: str
    strategy: str
    ts: Any


@dataclass
class EntryIntent:
    symbol: str
    name: str
    side: int
    quantity: float
    price: float
    stop_price: float
    reason_text: str
    strategy: str
    ts: Any


@dataclass
class SessionPlan:
    market_bars: list[MarketBar] = field(default_factory=list)
    exit_intents: list[ExitIntent] = field(default_factory=list)
    entry_intents: list[EntryIntent] = field(default_factory=list)
    skip_messages: list[str] = field(default_factory=list)
    risk_decision: dict = field(default_factory=dict)
    governor_context: dict = field(default_factory=dict)
    prices: dict[str, float] = field(default_factory=dict)
    data_as_of: dict[str, str] = field(default_factory=dict)


def _load_market_bars(
    *,
    refresh: bool,
    prefer_kite: bool = False,
    kite_client=None,
) -> list[MarketBar]:
    bars: list[MarketBar] = []
    for m in MARKETS:
        df = load_market_data(
            m.symbol,
            m.interval,
            refresh=refresh,
            prefer_kite=prefer_kite,
            kite_client=kite_client,
        )
        signals = STRATEGY_MAP[m.strategy](df)
        if signals.empty:
            continue

        row = signals.iloc[-1]
        ts = signals.index[-1]
        price = float(row["Close"])
        atr = float(row.get("atr", 0) or 0)
        signal = int(row.get("signal", 0) or 0)
        reason_text = (
            entry_reason(m.strategy, signal, row) if signal != 0 else "No entry signal"
        )
        bars.append(
            MarketBar(
                market=m,
                row=row,
                ts=ts,
                price=price,
                atr=atr,
                signal=signal,
                entry_reason_text=reason_text,
            )
        )
    return bars


def build_session_plan(
    portfolio: Portfolio,
    *,
    refresh: bool = True,
    prefer_kite: bool = False,
    kite_client=None,
    cash_only: bool | None = None,
) -> SessionPlan:
    """Phase 1: exits. Phase 2: governor + entries. Same rules for paper and live."""
    if cash_only is None:
        cash_only = settings.cash_only_mode()

    plan = SessionPlan()
    bars = _load_market_bars(
        refresh=refresh,
        prefer_kite=prefer_kite,
        kite_client=kite_client,
    )
    plan.market_bars = bars

    for bar in bars:
        m = bar.market
        plan.prices[m.symbol] = bar.price
        plan.data_as_of[m.symbol] = str(bar.ts)

        pos = portfolio.positions.get(m.symbol)
        if not pos:
            continue

        if stop_loss_hit(
            position_side=pos.side,
            stop_price=pos.stop_price,
            bar_low=float(bar.row["Low"]),
            bar_high=float(bar.row["High"]),
        ):
            plan.exit_intents.append(
                ExitIntent(
                    symbol=m.symbol,
                    name=m.name,
                    side=pos.side,
                    quantity=pos.quantity,
                    price=pos.stop_price,
                    stop_price=pos.stop_price,
                    reason_code="stop_loss",
                    strategy=m.strategy,
                    ts=bar.ts,
                )
            )
            continue

        should_exit, exit_code = should_exit_position(
            strategy=m.strategy,
            signal=bar.signal,
            position_side=pos.side,
        )
        if should_exit:
            plan.exit_intents.append(
                ExitIntent(
                    symbol=m.symbol,
                    name=m.name,
                    side=pos.side,
                    quantity=pos.quantity,
                    price=bar.price,
                    stop_price=pos.stop_price,
                    reason_code=exit_code,
                    strategy=m.strategy,
                    ts=bar.ts,
                )
            )

    market_rows = [
        {
            "market": bar.market,
            "row": bar.row,
            "ts": bar.ts,
            "price": bar.price,
            "atr": bar.atr,
            "signal": bar.signal,
            "entry_reason_text": bar.entry_reason_text,
        }
        for bar in bars
    ]
    governor_context = build_governor_context(
        portfolio, market_rows=market_rows, prices=plan.prices
    )
    risk_decision = evaluate_risk_governor(governor_context)
    plan.risk_decision = risk_decision.to_dict()
    plan.governor_context = governor_context

    exit_symbols = {intent.symbol for intent in plan.exit_intents}

    for bar in bars:
        m = bar.market
        if m.symbol in portfolio.positions and m.symbol not in exit_symbols:
            continue
        if m.symbol in exit_symbols:
            continue
        if bar.signal == 0 or bar.atr <= 0:
            continue

        if risk_decision.block_new_entries:
            plan.skip_messages.append(
                f"SKIP {m.name} - risk governor blocked new entries ({risk_decision.action})"
            )
            continue

        if not can_trade_side(m.symbol, bar.signal, cash_only=cash_only):
            plan.skip_messages.append(f"SKIP {m.name} - short not allowed in cash-only mode")
            continue

        if correlation_blocks_new_trade(m.symbol, bar.signal, m.group, portfolio.positions):
            plan.skip_messages.append(
                f"SKIP {m.name} - correlation filter (already long another {m.group} symbol)"
            )
            continue

        equity = portfolio_equity(portfolio, plan.prices)
        qty = calc_position_size(equity, bar.price, bar.atr) * risk_decision.risk_multiplier
        if qty <= 0:
            continue

        if bar.signal == 1 and portfolio.cash < bar.price * qty:
            qty = portfolio.cash / bar.price
        if qty <= 0:
            plan.skip_messages.append(f"SKIP {m.name} - insufficient cash")
            continue

        stop = calc_stop(bar.price, bar.signal, bar.atr)
        plan.entry_intents.append(
            EntryIntent(
                symbol=m.symbol,
                name=m.name,
                side=bar.signal,
                quantity=qty,
                price=bar.price,
                stop_price=stop,
                reason_text=bar.entry_reason_text,
                strategy=m.strategy,
                ts=bar.ts,
            )
        )

    return plan
