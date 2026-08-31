"""Paper trading session: fetch latest bars and simulate live decisions."""

from __future__ import annotations

import json
from datetime import datetime

from config import MARKETS
from src.backtest import STRATEGY_MAP
from src.data_loader import load_market_data
from src.db import record_session_equity, record_trade, recent_trades, update_daily_pnl
from src.risk import (
    Position,
    Portfolio,
    calc_position_size,
    calc_stop,
    correlation_blocks_new_trade,
    portfolio_equity,
)
from src.risk_governor import (
    build_governor_context,
    evaluate_risk_governor,
    format_risk_decision,
)
from src.trade_reasons import (
    entry_reason,
    exit_reason_label,
    symbol_label,
    trade_reason_summary,
)

STATE_FILE = __import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "paper_state.json"


def _load_state() -> Portfolio:
    if not STATE_FILE.exists():
        return Portfolio()
    raw = json.loads(STATE_FILE.read_text())
    portfolio = Portfolio(cash=raw["cash"])
    for sym, p in raw.get("positions", {}).items():
        portfolio.positions[sym] = Position(**p)
    portfolio.trades = raw.get("trades", [])
    return portfolio


def _save_state(portfolio: Portfolio):
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
                "entry_reason": p.entry_reason,
            }
            for sym, p in portfolio.positions.items()
        },
        "trades": portfolio.trades,
        "updated_at": datetime.now().isoformat(),
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2))


def _record_closed_trade(
    portfolio: Portfolio,
    *,
    symbol: str,
    side: str,
    entry_time,
    entry_price: float,
    exit_time,
    exit_price: float,
    quantity: float,
    pnl: float,
    entry_reason_text: str,
    exit_reason_code: str,
):
    summary = trade_reason_summary(
        entry_reason=entry_reason_text,
        exit_reason=exit_reason_code,
    )
    trade = {
        "symbol": symbol,
        "side": side,
        "entry_time": str(entry_time),
        "exit_time": str(exit_time),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "pnl": pnl,
        "entry_reason": entry_reason_text,
        "exit_reason": exit_reason_code,
        "reason": summary,
    }
    portfolio.trades.append(trade)
    record_trade(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_time=str(entry_time),
        entry_price=entry_price,
        exit_time=str(exit_time),
        exit_price=exit_price,
        pnl=pnl,
        reason=summary,
        run_type="paper",
        dry_run=True,
    )
    update_daily_pnl(realized_delta=pnl)


def _close_long(
    portfolio: Portfolio,
    symbol: str,
    *,
    exit_price: float,
    ts,
    exit_reason_code: str,
    actions: list[str],
):
    pos = portfolio.positions.pop(symbol)
    pnl = (exit_price - pos.entry_price) * pos.quantity
    portfolio.cash += exit_price * pos.quantity
    _record_closed_trade(
        portfolio,
        symbol=symbol,
        side="long",
        entry_time=pos.entry_time,
        entry_price=pos.entry_price,
        exit_time=ts,
        exit_price=exit_price,
        quantity=pos.quantity,
        pnl=pnl,
        entry_reason_text=pos.entry_reason,
        exit_reason_code=exit_reason_code,
    )
    label = symbol_label(symbol)
    actions.append(
        f"EXIT {label} LONG @ Rs{exit_price:.2f} (P&L Rs{pnl:,.0f}) "
        f"- {exit_reason_label(exit_reason_code)}"
    )


def _close_short(
    portfolio: Portfolio,
    symbol: str,
    *,
    exit_price: float,
    ts,
    exit_reason_code: str,
    actions: list[str],
):
    pos = portfolio.positions.pop(symbol)
    pnl = (pos.entry_price - exit_price) * pos.quantity
    portfolio.cash -= exit_price * pos.quantity
    _record_closed_trade(
        portfolio,
        symbol=symbol,
        side="short",
        entry_time=pos.entry_time,
        entry_price=pos.entry_price,
        exit_time=ts,
        exit_price=exit_price,
        quantity=pos.quantity,
        pnl=pnl,
        entry_reason_text=pos.entry_reason,
        exit_reason_code=exit_reason_code,
    )
    label = symbol_label(symbol)
    actions.append(
        f"EXIT {label} SHORT @ Rs{exit_price:.2f} (P&L Rs{pnl:,.0f}) "
        f"- {exit_reason_label(exit_reason_code)}"
    )


def _process_exits(
    portfolio: Portfolio,
    m,
    row,
    ts,
    price: float,
    signal: int,
    actions: list[str],
) -> None:
    pos = portfolio.positions.get(m.symbol)
    if pos:
        if pos.side == 1 and row["Low"] <= pos.stop_price:
            _close_long(
                portfolio,
                m.symbol,
                exit_price=pos.stop_price,
                ts=ts,
                exit_reason_code="stop_loss",
                actions=actions,
            )
            pos = None
        elif pos.side == -1 and row["High"] >= pos.stop_price:
            _close_short(
                portfolio,
                m.symbol,
                exit_price=pos.stop_price,
                ts=ts,
                exit_reason_code="stop_loss",
                actions=actions,
            )
            pos = None

    pos = portfolio.positions.get(m.symbol)
    if pos:
        should_exit = False
        exit_code = "signal_exit"
        if m.strategy in ("mean_reversion", "momentum_breakout"):
            should_exit = signal != 0 and signal != pos.side
        elif m.strategy == "trend_following":
            should_exit = signal != pos.side
            exit_code = "trend_exit"

        if should_exit:
            if pos.side == 1:
                _close_long(
                    portfolio,
                    m.symbol,
                    exit_price=price,
                    ts=ts,
                    exit_reason_code=exit_code,
                    actions=actions,
                )
            else:
                _close_short(
                    portfolio,
                    m.symbol,
                    exit_price=price,
                    ts=ts,
                    exit_reason_code=exit_code,
                    actions=actions,
                )


def run_paper_session(*, refresh: bool = True) -> dict:
    """Evaluate latest bar for each market and update paper portfolio."""
    portfolio = _load_state()
    prices: dict[str, float] = {}
    actions: list[str] = []
    data_as_of: dict[str, str] = {}
    market_rows: list[dict] = []

    # Phase 1: load markets, process exits, collect signals
    for m in MARKETS:
        df = load_market_data(m.symbol, m.interval, refresh=refresh)
        signals = STRATEGY_MAP[m.strategy](df)
        if signals.empty:
            continue

        row = signals.iloc[-1]
        ts = signals.index[-1]
        price = float(row["Close"])
        atr = float(row.get("atr", 0) or 0)
        signal = int(row.get("signal", 0) or 0)
        prices[m.symbol] = price
        data_as_of[m.symbol] = str(ts)

        reason_text = (
            entry_reason(m.strategy, signal, row) if signal != 0 else "No entry signal"
        )
        market_rows.append(
            {
                "market": m,
                "row": row,
                "ts": ts,
                "price": price,
                "atr": atr,
                "signal": signal,
                "entry_reason_text": reason_text,
            }
        )
        _process_exits(portfolio, m, row, ts, price, signal, actions)

    # Phase 2: risk governor (rules + Groq LLM)
    governor_context = build_governor_context(
        portfolio, market_rows=market_rows, prices=prices
    )
    risk_decision = evaluate_risk_governor(governor_context)

    # Phase 3: new entries (respect governor)
    for item in market_rows:
        m = item["market"]
        row = item["row"]
        ts = item["ts"]
        price = item["price"]
        atr = item["atr"]
        signal = item["signal"]
        reason_text = item["entry_reason_text"]

        if m.symbol in portfolio.positions:
            continue
        if signal == 0 or atr <= 0:
            continue

        if risk_decision.block_new_entries:
            actions.append(
                f"SKIP {m.name} - risk governor blocked new entries "
                f"({risk_decision.action})"
            )
            continue

        if correlation_blocks_new_trade(
            m.symbol, signal, m.group, portfolio.positions
        ):
            actions.append(
                f"SKIP {m.name} - correlation filter "
                f"(already long another {m.group} symbol)"
            )
            continue

        equity = portfolio_equity(portfolio, prices)
        qty = calc_position_size(equity, price, atr) * risk_decision.risk_multiplier
        if qty <= 0:
            continue
        cost = price * qty
        if signal == 1 and portfolio.cash < cost:
            qty = portfolio.cash / price
            cost = price * qty
        if qty <= 0:
            continue
        stop = calc_stop(price, signal, atr)
        if signal == 1:
            portfolio.cash -= cost
        else:
            portfolio.cash += cost
        portfolio.positions[m.symbol] = Position(
            symbol=m.symbol,
            side=signal,
            entry_price=price,
            quantity=qty,
            stop_price=stop,
            group=m.group,
            entry_time=str(ts),
            entry_reason=reason_text,
        )
        side = "LONG" if signal == 1 else "SHORT"
        mult_note = (
            f" [risk {risk_decision.risk_multiplier:.2f}x]"
            if risk_decision.risk_multiplier != 1.0
            else ""
        )
        actions.append(
            f"ENTER {side} {m.name} @ Rs{price:.2f} qty={qty:.2f} "
            f"stop=Rs{stop:.2f}{mult_note} - {reason_text}"
        )

    equity = portfolio_equity(portfolio, prices)
    unrealized = sum(
        (prices.get(sym, p.entry_price) - p.entry_price) * p.quantity * p.side
        for sym, p in portfolio.positions.items()
    )
    record_session_equity(equity=equity, cash=portfolio.cash, unrealized=unrealized)
    _save_state(portfolio)

    risk_text = format_risk_decision(risk_decision)
    lines = [
        "=" * 60,
        f"PAPER TRADING SESSION - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        risk_text,
        "",
        f"Equity: Rs{equity:,.0f}  |  Cash: Rs{portfolio.cash:,.0f}",
        f"Open positions: {len(portfolio.positions)}  |  Total trades: {len(portfolio.trades)}",
        "",
    ]
    if actions:
        lines.append("Actions this run:")
        lines.extend(f"  * {a}" for a in actions)
    else:
        lines.append("No new actions - holding current positions.")
    if portfolio.positions:
        lines.extend(["", "Current positions:"])
        for sym, p in portfolio.positions.items():
            mark = prices.get(sym, p.entry_price)
            u_pnl = (mark - p.entry_price) * p.quantity * p.side
            lines.append(
                f"  {symbol_label(sym)} {'LONG' if p.side == 1 else 'SHORT'} "
                f"@ Rs{p.entry_price:.2f}  mark Rs{mark:.2f}  uP&L Rs{u_pnl:,.0f}"
            )
            if p.entry_reason:
                lines.append(f"    Entry reason: {p.entry_reason}")
    recent_tr = recent_trades(5)
    if recent_tr:
        lines.extend(["", "Recent Trades (DB):"])
        for t in recent_tr:
            lines.append(
                f"  {t['exit_time'][:16]} {symbol_label(t['symbol'])} {t['side'].upper()} "
                f"qty {t['quantity']:.1f} entry {t['entry_price']:.2f} exit {t['exit_price']:.2f} "
                f"P&L Rs {t['pnl']:,.2f} ({t['return_pct']:.2f}%)"
            )
            lines.append(f"    Reason: {t['reason']}")
    lines.append("=" * 60)

    return {
        "summary": "\n".join(lines),
        "actions": actions,
        "equity": equity,
        "cash": portfolio.cash,
        "unrealized_pnl": unrealized,
        "open_positions": len(portfolio.positions),
        "total_trades": len(portfolio.trades),
        "prices": prices,
        "data_as_of": data_as_of,
        "portfolio": portfolio,
        "risk_decision": risk_decision.to_dict(),
        "governor_context": governor_context,
    }


def reset_paper_account():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    from config import INITIAL_CAPITAL

    return f"Paper account reset to Rs{INITIAL_CAPITAL:,.0f}"
