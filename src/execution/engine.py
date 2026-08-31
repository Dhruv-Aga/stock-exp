"""Live / dry-run execution engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from config import INITIAL_CAPITAL, MARKETS
from src import settings
from src.backtest import STRATEGY_MAP
from src.broker.kite_client import KiteClient
from src.broker.order_manager import OrderManager, TradeIntent
from src.broker.symbol_map import can_trade_side
from src.data_loader import load_market_data
from src.db import init_db, recent_orders, update_daily_pnl, record_trade, recent_trades
from src.risk import (
    Position,
    Portfolio,
    calc_position_size,
    calc_stop,
    correlation_blocks_new_trade,
    portfolio_equity,
)
from src.safety import SafetyHalt, check_can_trade, is_market_open
from src.approvals.propose import propose_entry, propose_exit, proposal_action_suffix

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "live_state.json"


def _load_state() -> Portfolio:
    if not STATE_FILE.exists():
        return Portfolio()
    raw = json.loads(STATE_FILE.read_text())
    portfolio = Portfolio(cash=raw.get("cash", INITIAL_CAPITAL))
    for sym, p in raw.get("positions", {}).items():
        portfolio.positions[sym] = Position(**p)
    portfolio.trades = raw.get("trades", [])
    return portfolio


def _save_state(portfolio: Portfolio) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cash": portfolio.cash,
        "positions": {
            sym: {
                "symbol": p.symbol,
                "side": p.side,
                "entry_price": p.entry_price,
                "quantity": p.quantity,
                "stop_price": p.stop_price,
                "group": p.group,
                "entry_time": str(p.entry_time) if p.entry_time else None,
            }
            for sym, p in portfolio.positions.items()
        },
        "trades": portfolio.trades,
        "updated_at": datetime.now().isoformat(),
        "mode": "dry_run" if settings.dry_run_mode() else "live",
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2))


def _sync_broker_positions(client: KiteClient, portfolio: Portfolio) -> None:
    if not client.is_live:
        return
    holdings = {h["tradingsymbol"]: h for h in client.holdings()}
    symbol_by_kite = {m.kite_symbol: m.symbol for m in MARKETS}
    for kite_sym, row in holdings.items():
        strat_sym = symbol_by_kite.get(kite_sym)
        if not strat_sym:
            continue
        qty = int(row.get("quantity", 0) or 0)
        if qty <= 0:
            continue
        if strat_sym not in portfolio.positions:
            avg = float(row.get("average_price", 0) or 0)
            portfolio.positions[strat_sym] = Position(
                symbol=strat_sym,
                side=1,
                entry_price=avg,
                quantity=qty,
                stop_price=avg * 0.99,
                group=next(m.group for m in MARKETS if m.symbol == strat_sym),
            )


def run_live_session(*, refresh: bool = True, force: bool = False) -> str:
    """
    Evaluate signals and route orders through Zerodha (or dry-run log).

    force=True skips market-hours check (useful for testing).
    """
    settings.load_settings()
    init_db()

    mode = "DRY RUN" if settings.dry_run_mode() else "LIVE"
    client = KiteClient()
    orders = OrderManager(client)
    portfolio = _load_state()
    actions: list[str] = []
    prices: dict[str, float] = {}

    try:
        if not force:
            check_can_trade(require_market_open=not settings.dry_run_mode())
        elif kill_switch_only():
            check_can_trade(require_market_open=False)
    except SafetyHalt as exc:
        return _format_report(mode, portfolio, prices, [str(exc)], client)

    if client.is_live:
        client.load_instruments()
        _sync_broker_positions(client, portfolio)

    cash_only = settings.cash_only_mode()
    needs_approval = (
        not settings.dry_run_mode()
        and settings.require_trade_approval()
    )

    for m in MARKETS:
        df = load_market_data(
            m.symbol, m.interval, refresh=refresh, prefer_kite=client.is_live, kite_client=client
        )
        signals = STRATEGY_MAP[m.strategy](df)
        if signals.empty:
            continue

        row = signals.iloc[-1]
        ts = signals.index[-1]
        price = float(row["Close"])
        atr = float(row.get("atr", 0) or 0)
        signal = int(row.get("signal", 0) or 0)
        prices[m.symbol] = price

        pos = portfolio.positions.get(m.symbol)

        # Stop-loss hit
        if pos:
            stopped = False
            if pos.side == 1 and row["Low"] <= pos.stop_price:
                exit_price = pos.stop_price
                stopped = True
            elif pos.side == -1 and row["High"] >= pos.stop_price:
                exit_price = pos.stop_price
                stopped = True

            if stopped:
                intent = TradeIntent(
                    symbol=m.symbol,
                    side=pos.side,
                    quantity=pos.quantity,
                    price=exit_price,
                    stop_price=pos.stop_price,
                    reason="stop_loss",
                )
                if needs_approval:
                    proposal = propose_exit(
                        symbol=m.symbol,
                        side=pos.side,
                        quantity=pos.quantity,
                        price=exit_price,
                        reason="stop_loss",
                        strategy=m.strategy,
                        source="automation",
                    )
                    actions.append(
                        f"PROPOSED STOP {m.name} — {proposal_action_suffix(proposal)}"
                    )
                else:
                    result = orders.exit(intent, position_side=pos.side)
                    pnl = (exit_price - pos.entry_price) * pos.quantity * pos.side
                    _close_local(portfolio, m.symbol, exit_price, ts, "stop_loss", pnl)
                    update_daily_pnl(realized_delta=pnl)
                    actions.append(
                        f"STOP {m.name} [{result.status}] order={result.order_id} P&L Rs{pnl:,.0f}"
                    )
                pos = None

        # Signal exit
        if pos and signal != 0 and signal != pos.side:
            intent = TradeIntent(
                symbol=m.symbol,
                side=signal,
                quantity=pos.quantity,
                price=price,
                stop_price=pos.stop_price,
                reason="signal_exit",
            )
            if needs_approval:
                proposal = propose_exit(
                    symbol=m.symbol,
                    side=pos.side,
                    quantity=pos.quantity,
                    price=price,
                    reason="signal_exit",
                    strategy=m.strategy,
                    source="automation",
                )
                actions.append(
                    f"PROPOSED EXIT {m.name} — {proposal_action_suffix(proposal)}"
                )
            else:
                result = orders.exit(intent, position_side=pos.side)
                pnl = (price - pos.entry_price) * pos.quantity * pos.side
                _close_local(portfolio, m.symbol, price, ts, "signal_exit", pnl)
                update_daily_pnl(realized_delta=pnl)
                actions.append(
                    f"EXIT {m.name} [{result.status}] order={result.order_id} P&L Rs{pnl:,.0f}"
                )
            pos = None

        # New entry
        if not pos and signal != 0 and atr > 0:
            if not can_trade_side(m.symbol, signal, cash_only=cash_only):
                actions.append(f"SKIP {m.name} - short not allowed in cash-only mode")
                continue
            if correlation_blocks_new_trade(m.symbol, signal, m.group, portfolio.positions):
                actions.append(f"SKIP {m.name} - correlation filter")
                continue

            equity = portfolio_equity(portfolio, prices)
            qty = calc_position_size(equity, price, atr)
            if qty <= 0:
                continue
            stop = calc_stop(price, signal, atr)
            intent = TradeIntent(
                symbol=m.symbol,
                side=signal,
                quantity=qty,
                price=price,
                stop_price=stop,
                reason="signal_entry",
            )
            if needs_approval:
                proposal = propose_entry(
                    symbol=m.symbol,
                    side=signal,
                    quantity=qty,
                    price=price,
                    stop_price=stop,
                    reason="signal_entry",
                    strategy=m.strategy,
                    source="automation",
                )
                side = "LONG" if signal == 1 else "SHORT"
                actions.append(
                    f"PROPOSED {side} {m.name} qty={qty:.0f} stop=Rs{stop:.2f} — "
                    f"{proposal_action_suffix(proposal)}"
                )
            else:
                result = orders.enter(intent)
                if result.status in ("PLACED", "DRY_RUN"):
                    _open_local(portfolio, m, signal, price, qty, stop, ts)
                    side = "LONG" if signal == 1 else "SHORT"
                    actions.append(
                        f"ENTER {side} {m.name} [{result.status}] order={result.order_id} "
                        f"qty={qty:.0f} stop=Rs{stop:.2f}"
                    )
                else:
                    actions.append(f"FAILED entry {m.name}: {result.message}")

    _save_state(portfolio)
    return _format_report(mode, portfolio, prices, actions, client)


def kill_switch_only() -> bool:
    from src.safety import kill_switch_active
    from src.db import get_today_realized_pnl
    from src import settings as s

    if kill_switch_active():
        return True
    return get_today_realized_pnl() <= -s.max_daily_loss()


def _open_local(portfolio, market, side, price, qty, stop, ts):
    cost = price * qty
    if side == 1:
        portfolio.cash -= cost
    else:
        portfolio.cash += cost
    portfolio.positions[market.symbol] = Position(
        symbol=market.symbol,
        side=side,
        entry_price=price,
        quantity=qty,
        stop_price=stop,
        group=market.group,
        entry_time=str(ts),
    )


def _close_local(portfolio, symbol, price, ts, reason, pnl):
    pos = portfolio.positions.pop(symbol)
    if pos.side == 1:
        portfolio.cash += price * pos.quantity
    else:
        portfolio.cash -= price * pos.quantity
    portfolio.trades.append(
        {
            "symbol": symbol,
            "side": "long" if pos.side == 1 else "short",
            "entry_time": pos.entry_time,
            "exit_time": str(ts),
            "entry_price": pos.entry_price,
            "exit_price": price,
            "quantity": pos.quantity,
            "pnl": pnl,
            "reason": reason,
        }
    )
    record_trade(
        symbol=symbol,
        side="long" if pos.side == 1 else "short",
        quantity=pos.quantity,
        entry_time=pos.entry_time,
        entry_price=pos.entry_price,
        exit_time=str(ts),
        exit_price=price,
        pnl=pnl,
        reason=reason,
        run_type="dry_run" if settings.dry_run_mode() else "live",
        dry_run=settings.dry_run_mode(),
    )


def _format_report(mode, portfolio, prices, actions, client) -> str:
    equity = portfolio_equity(portfolio, prices)
    market_status = "OPEN" if is_market_open() else "CLOSED"
    lines = [
        "=" * 60,
        f"ZERODHA EXECUTION - {mode} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        f"Market: {market_status}  |  Equity: Rs{equity:,.0f}  |  Cash: Rs{portfolio.cash:,.0f}",
        f"Open positions: {len(portfolio.positions)}  |  Trades: {len(portfolio.trades)}",
        f"Kite connected: {'yes' if client.is_live else 'no (dry-run)'}",
        "",
    ]
    if actions:
        lines.append("Actions:")
        lines.extend(f"  * {a}" for a in actions)
    else:
        lines.append("No actions this run.")
    if portfolio.positions:
        lines.extend(["", "Positions:"])
        for sym, p in portfolio.positions.items():
            mark = prices.get(sym, p.entry_price)
            u_pnl = (mark - p.entry_price) * p.quantity * p.side
            lines.append(
                f"  {sym} {'LONG' if p.side == 1 else 'SHORT'} "
                f"@ Rs{p.entry_price:.2f} mark Rs{mark:.2f} uP&L Rs{u_pnl:,.0f}"
            )
    recent = recent_orders(5)
    if recent:
        lines.extend(["", "Recent orders (DB):"])
        for o in recent:
            lines.append(
                f"  {o['created_at'][:16]} {o['status']} {o['side']} "
                f"{o['symbol']} x{o['quantity']} ({'dry' if o['dry_run'] else 'live'})"
            )
    recent_tr = recent_trades(5)
    if recent_tr:
        lines.extend(["", "Recent Trades (DB):"])
        for t in recent_tr:
            lines.append(
                f"  {t['exit_time'][:16]} {t['symbol']} {t['side'].upper()} "
                f"qty {t['quantity']:.1f} entry {t['entry_price']:.2f} exit {t['exit_price']:.2f} "
                f"P&L Rs {t['pnl']:,.2f} ({t['return_pct']:.2f}%) [{t['run_type']}]"
            )
    lines.append("=" * 60)
    return "\n".join(lines)


def reset_live_state() -> str:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    return f"Live/dry-run state reset. Capital Rs{INITIAL_CAPITAL:,.0f}"
