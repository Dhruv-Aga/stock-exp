"""Live / dry-run execution engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from config import INITIAL_CAPITAL, MARKETS
from src import settings
from src.broker.kite_client import KiteClient
from src.broker.order_manager import OrderManager, TradeIntent
from src.broker.symbol_map import round_quantity
from src.db import init_db, recent_orders, record_session_equity, record_trade, recent_trades, update_daily_pnl
from src.risk import Position, Portfolio, portfolio_equity
from src.risk_governor import format_risk_decision
from src.safety import SafetyHalt, check_can_trade, is_market_open
from src.approvals.propose import propose_entry, propose_exit, proposal_action_suffix
from src.trading.session_plan import build_session_plan

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


def _run_type() -> str:
    return "dry_run" if settings.dry_run_mode() else "live"


def run_live_session(*, refresh: bool = True, force: bool = False) -> str:
    """
    Evaluate signals and route orders through Zerodha (or dry-run log).

    Uses the same session plan as paper trading (governor, exits, entries).
    force=True skips market-hours check (useful for testing).
    """
    settings.load_settings()
    init_db()

    mode = "DRY RUN" if settings.dry_run_mode() else "LIVE"
    run_type = _run_type()
    client = KiteClient()
    orders = OrderManager(client)
    portfolio = _load_state()
    actions: list[str] = []

    try:
        if not force:
            check_can_trade(require_market_open=not settings.dry_run_mode(), run_type=run_type)
        elif kill_switch_only(run_type):
            check_can_trade(require_market_open=False, run_type=run_type)
    except SafetyHalt as exc:
        return _format_report(mode, portfolio, {}, [str(exc)], client, plan_risk={})

    if client.is_live:
        client.load_instruments()
        _sync_broker_positions(client, portfolio)

    needs_approval = not settings.dry_run_mode() and settings.require_trade_approval()

    plan = build_session_plan(
        portfolio,
        refresh=refresh,
        prefer_kite=client.is_live,
        kite_client=client if client.is_live else None,
    )
    prices = plan.prices

    for intent in plan.exit_intents:
        market = next((m for m in MARKETS if m.symbol == intent.symbol), None)
        if not market:
            continue
        pos = portfolio.positions.get(intent.symbol)
        if not pos:
            continue

        trade_intent = TradeIntent(
            symbol=intent.symbol,
            side=intent.side,
            quantity=int(pos.quantity),
            price=intent.price,
            stop_price=intent.stop_price,
            reason=intent.reason_code,
        )
        if needs_approval:
            proposal = propose_exit(
                symbol=intent.symbol,
                side=intent.side,
                quantity=pos.quantity,
                price=intent.price,
                reason=intent.reason_code,
                strategy=intent.strategy,
                source="automation",
            )
            actions.append(
                f"PROPOSED EXIT {intent.name} ({intent.reason_code}) — "
                f"{proposal_action_suffix(proposal)}"
            )
        else:
            result = orders.exit(trade_intent, position_side=pos.side)
            pnl = (intent.price - pos.entry_price) * pos.quantity * pos.side
            _close_local(portfolio, intent.symbol, intent.price, intent.ts, intent.reason_code, pnl)
            update_daily_pnl(realized_delta=pnl, run_type=run_type)
            actions.append(
                f"EXIT {intent.name} [{result.status}] order={result.order_id} "
                f"P&L Rs{pnl:,.0f} ({intent.reason_code})"
            )

    for msg in plan.skip_messages:
        actions.append(msg)

    for intent in plan.entry_intents:
        market = next((m for m in MARKETS if m.symbol == intent.symbol), None)
        if not market:
            continue

        qty = float(round_quantity(intent.symbol, intent.quantity))
        if qty <= 0:
            actions.append(f"SKIP {intent.name} - rounded quantity is zero")
            continue

        trade_intent = TradeIntent(
            symbol=intent.symbol,
            side=intent.side,
            quantity=int(qty),
            price=intent.price,
            stop_price=intent.stop_price,
            reason="signal_entry",
        )
        if needs_approval:
            proposal = propose_entry(
                symbol=intent.symbol,
                side=intent.side,
                quantity=qty,
                price=intent.price,
                stop_price=intent.stop_price,
                reason=intent.reason_text,
                strategy=intent.strategy,
                source="automation",
            )
            side = "LONG" if intent.side == 1 else "SHORT"
            mult = plan.risk_decision.get("risk_multiplier", 1.0)
            mult_note = f" [risk {mult:.2f}x]" if mult != 1.0 else ""
            actions.append(
                f"PROPOSED {side} {intent.name} qty={qty:.0f} stop=Rs{intent.stop_price:.2f}{mult_note} — "
                f"{proposal_action_suffix(proposal)}"
            )
        else:
            result = orders.enter(trade_intent)
            if result.status in ("PLACED", "DRY_RUN"):
                _open_local(portfolio, market, intent.side, intent.price, qty, intent.stop_price, intent.ts)
                side = "LONG" if intent.side == 1 else "SHORT"
                mult = plan.risk_decision.get("risk_multiplier", 1.0)
                mult_note = f" [risk {mult:.2f}x]" if mult != 1.0 else ""
                actions.append(
                    f"ENTER {side} {intent.name} [{result.status}] order={result.order_id} "
                    f"qty={qty:.0f} stop=Rs{intent.stop_price:.2f}{mult_note}"
                )
            else:
                actions.append(f"FAILED entry {intent.name}: {result.message}")

    equity = portfolio_equity(portfolio, prices)
    unrealized = sum(
        (prices.get(sym, p.entry_price) - p.entry_price) * p.quantity * p.side
        for sym, p in portfolio.positions.items()
    )
    record_session_equity(
        equity=equity, cash=portfolio.cash, unrealized=unrealized, run_type=run_type
    )
    _save_state(portfolio)
    return _format_report(mode, portfolio, prices, actions, client, plan_risk=plan.risk_decision)


def kill_switch_only(run_type: str = "live") -> bool:
    from src.safety import kill_switch_active
    from src.db import get_today_realized_pnl
    from src import settings as s

    if kill_switch_active():
        return True
    return get_today_realized_pnl(run_type=run_type) <= -s.max_daily_loss()


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


def _format_report(mode, portfolio, prices, actions, client, *, plan_risk: dict) -> str:
    equity = portfolio_equity(portfolio, prices)
    market_status = "OPEN" if is_market_open() else "CLOSED"
    lines = [
        "=" * 60,
        f"ZERODHA EXECUTION - {mode} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
    ]
    if plan_risk:
        lines.extend([format_risk_decision(plan_risk), ""])
    lines.extend(
        [
            f"Market: {market_status}  |  Equity: Rs{equity:,.0f}  |  Cash: Rs{portfolio.cash:,.0f}",
            f"Open positions: {len(portfolio.positions)}  |  Trades: {len(portfolio.trades)}",
            f"Kite connected: {'yes' if client.is_live else 'no (dry-run)'}",
            "",
        ]
    )
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
