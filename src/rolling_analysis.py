"""Daily and rolling monthly P&L analysis from backtest results."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from config import INITIAL_CAPITAL
from src.backtest import run_backtest


def _equity_to_daily_series(equity_curve: list[tuple]) -> pd.Series:
    if not equity_curve:
        return pd.Series(dtype=float)

    df = pd.DataFrame(equity_curve, columns=["ts", "equity"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    # Last equity reading per calendar day
    daily = df["equity"].resample("D").last().dropna()
    return daily


def daily_pnl_breakdown(equity_curve: list[tuple]) -> pd.DataFrame:
    daily = _equity_to_daily_series(equity_curve)
    if daily.empty:
        return pd.DataFrame(columns=["date", "equity", "daily_pnl", "daily_return_pct"])

    prev = daily.shift(1)
    prev.iloc[0] = INITIAL_CAPITAL
    out = pd.DataFrame(
        {
            "date": daily.index.date,
            "equity": daily.values,
            "daily_pnl": (daily - prev).values,
            "daily_return_pct": ((daily / prev - 1) * 100).values,
        }
    )
    return out


def calendar_month_pnl(equity_curve: list[tuple], trades: list[dict]) -> pd.DataFrame:
    daily = _equity_to_daily_series(equity_curve)
    if daily.empty:
        return pd.DataFrame()

    # Remove timezone for clean period grouping
    if daily.index.tz is not None:
        daily.index = daily.index.tz_localize(None)

    trade_month_pnl: dict[str, float] = {}
    trade_counts: dict[str, int] = {}
    for t in trades:
        exit_ts = pd.to_datetime(t["exit_time"])
        if exit_ts.tzinfo is not None:
            exit_ts = exit_ts.tz_localize(None)
        key = exit_ts.strftime("%Y-%m")
        trade_month_pnl[key] = trade_month_pnl.get(key, 0) + t["pnl"]
        trade_counts[key] = trade_counts.get(key, 0) + 1

    rows = []
    months = daily.groupby(pd.Grouper(freq="ME"))
    prev_end = INITIAL_CAPITAL
    for end_date, month_slice in months:
        if month_slice.empty:
            continue
        start_eq = prev_end
        end_eq = month_slice.iloc[-1]
        month_key = end_date.strftime("%Y-%m")
        rows.append(
            {
                "month": month_key,
                "start_equity": round(start_eq, 2),
                "end_equity": round(end_eq, 2),
                "month_pnl": round(end_eq - start_eq, 2),
                "month_return_pct": round((end_eq / start_eq - 1) * 100, 2),
                "trading_days": len(month_slice),
                "realized_trade_pnl": round(trade_month_pnl.get(month_key, 0), 2),
                "trades_closed": trade_counts.get(month_key, 0),
            }
        )
        prev_end = end_eq

    return pd.DataFrame(rows)


def rolling_30day_windows(equity_curve: list[tuple]) -> pd.DataFrame:
    """
    For each day, measure how much the portfolio gained/lost over the prior 30 days.
    Simulates: 'If I had run this strategy for the last month ending today, what would I earn?'
    """
    daily = _equity_to_daily_series(equity_curve)
    if len(daily) < 2:
        return pd.DataFrame(
            columns=[
                "as_of_date",
                "equity",
                "pnl_30d",
                "return_30d_pct",
                "start_equity_30d",
            ]
        )

    rows = []
    for i, (dt, eq) in enumerate(daily.items()):
        target_start = dt - timedelta(days=30)
        prior = daily[daily.index <= target_start]
        if prior.empty:
            # use earliest point if less than 30 days of history
            if i == 0:
                continue
            start_eq = INITIAL_CAPITAL if i < 30 else daily.iloc[max(0, i - 30)]
            start_date = daily.index[max(0, i - 30)]
            if (dt - start_date).days < 7:
                continue
            start_eq = daily.iloc[max(0, i - 30)]
        else:
            start_eq = prior.iloc[-1]

        pnl = eq - start_eq
        rows.append(
            {
                "as_of_date": dt.date(),
                "equity": round(eq, 2),
                "start_equity_30d": round(start_eq, 2),
                "pnl_30d": round(pnl, 2),
                "return_30d_pct": round((eq / start_eq - 1) * 100, 2),
                "lookback_days": (dt - daily.index[daily.index <= target_start][-1]).days
                if not prior.empty
                else min(30, i),
            }
        )

    return pd.DataFrame(rows)


def run_full_analysis(*, refresh: bool = False) -> dict:
    results = run_backtest(refresh=refresh)
    daily = daily_pnl_breakdown(results["equity_curve"])
    monthly = calendar_month_pnl(results["equity_curve"], results["trades"])
    rolling = rolling_30day_windows(results["equity_curve"])

    data_start = None
    data_end = None
    if not daily.empty:
        data_start = str(daily["date"].iloc[0])
        data_end = str(daily["date"].iloc[-1])

    return {
        "backtest": results,
        "daily_pnl": daily,
        "monthly_pnl": monthly,
        "rolling_30d": rolling,
        "data_start": data_start,
        "data_end": data_end,
    }


def format_analysis_report(analysis: dict) -> str:
    from config import INITIAL_CAPITAL

    bt = analysis["backtest"]
    daily = analysis["daily_pnl"]
    monthly = analysis["monthly_pnl"]
    rolling = analysis["rolling_30d"]

    lines = [
        "INDIA TRADING BOT - DAILY & MONTHLY ANALYSIS REPORT",
        "=" * 58,
        f"Capital        : Rs {INITIAL_CAPITAL:,.0f}",
        f"Data available : {analysis['data_start']} to {analysis['data_end']}",
        f"(Free yfinance: ~60 days for 15m bars; longer for 1h/4h)",
        "",
        "FULL PERIOD SUMMARY",
        f"  Final equity   : Rs {bt['final_equity']:,.0f}",
        f"  Total return   : {bt['total_return_pct']:.2f}%",
        f"  Total trades   : {bt['num_trades']}",
        "",
    ]

    if not monthly.empty:
        lines.append("CALENDAR MONTH BREAKDOWN (equity change per month)")
        lines.append("-" * 58)
        for _, r in monthly.iterrows():
            lines.append(
                f"  {r['month']}  P&L Rs {r['month_pnl']:,.0f}  "
                f"({r['month_return_pct']:+.2f}%)  "
                f"{int(r['trades_closed'])} trades closed"
            )
        avg_month = monthly["month_pnl"].mean()
        lines.append(f"  Average month: Rs {avg_month:,.0f}")
        lines.append("")

    if not rolling.empty:
        lines.append("ROLLING 30-DAY P&L (ending each day)")
        lines.append("-" * 58)
        recent = rolling.tail(10)
        for _, r in recent.iterrows():
            lines.append(
                f"  {r['as_of_date']}  30d P&L Rs {r['pnl_30d']:,.0f}  "
                f"({r['return_30d_pct']:+.2f}%)"
            )
        lines.append("")
        lines.append("Rolling 30-day stats (all history):")
        lines.append(f"  Best  30d period : Rs {rolling['pnl_30d'].max():,.0f}")
        lines.append(f"  Worst 30d period: Rs {rolling['pnl_30d'].min():,.0f}")
        lines.append(f"  Avg   30d period: Rs {rolling['pnl_30d'].mean():,.0f}")
        last_30d = rolling.iloc[-1]
        lines.append(
            f"  Latest 30d (as of {last_30d['as_of_date']}): "
            f"Rs {last_30d['pnl_30d']:,.0f}"
        )
        lines.append("")

    if not daily.empty:
        lines.append("DAILY P&L (last 14 days)")
        lines.append("-" * 58)
        for _, r in daily.tail(14).iterrows():
            sign = "+" if r["daily_pnl"] >= 0 else ""
            lines.append(
                f"  {r['date']}  {sign}Rs {r['daily_pnl']:,.0f}  "
                f"({r['daily_return_pct']:+.2f}%)  equity Rs {r['equity']:,.0f}"
            )
        lines.append("")
        lines.append("Daily stats:")
        lines.append(f"  Best day  : Rs {daily['daily_pnl'].max():,.0f}")
        lines.append(f"  Worst day : Rs {daily['daily_pnl'].min():,.0f}")
        lines.append(f"  Avg day   : Rs {daily['daily_pnl'].mean():,.0f}")
        lines.append(f"  Green days: {(daily['daily_pnl'] > 0).sum()} / {len(daily)}")

    lines.append("")
    lines.append("=" * 58)
    lines.append(
        "Note: Past patterns do not guarantee future results. "
        "Brokerage and taxes not included."
    )
    return "\n".join(lines)


def run_weekly_analysis(*, refresh: bool = False, days: int = 7) -> dict:
    results = run_backtest(refresh=refresh)
    daily = daily_pnl_breakdown(results["equity_curve"])

    cutoff = pd.Timestamp.now().normalize() - timedelta(days=days)
    week_daily = daily[pd.to_datetime(daily["date"]) >= cutoff] if not daily.empty else daily

    week_trades = []
    for t in results["trades"]:
        exit_ts = pd.to_datetime(t["exit_time"])
        if exit_ts.tzinfo is not None:
            exit_ts = exit_ts.tz_localize(None)
        if exit_ts >= cutoff:
            week_trades.append(t)

    if not week_daily.empty:
        prior = daily[pd.to_datetime(daily["date"]) < cutoff]
        start_equity = float(prior.iloc[-1]["equity"]) if not prior.empty else INITIAL_CAPITAL
        end_equity = float(week_daily.iloc[-1]["equity"])
        week_start = str(week_daily["date"].iloc[0])
        week_end = str(week_daily["date"].iloc[-1])
    else:
        start_equity = INITIAL_CAPITAL
        end_equity = results["final_equity"]
        week_start = week_end = str(cutoff.date())

    week_pnl = end_equity - start_equity
    week_return = (end_equity / start_equity - 1) * 100 if start_equity else 0

    by_symbol: dict[str, list] = {}
    for t in week_trades:
        by_symbol.setdefault(t["symbol"], []).append(t["pnl"])

    wins = [t for t in week_trades if t["pnl"] > 0]
    win_rate = (len(wins) / len(week_trades) * 100) if week_trades else 0.0

    return {
        "days": days,
        "week_start": week_start,
        "week_end": week_end,
        "start_equity": start_equity,
        "end_equity": end_equity,
        "week_pnl": week_pnl,
        "week_return_pct": week_return,
        "trades": week_trades,
        "num_trades": len(week_trades),
        "win_rate": win_rate,
        "by_symbol": by_symbol,
        "daily_pnl": week_daily,
        "open_positions": results["open_positions"],
    }


def format_weekly_report(analysis: dict) -> str:
    from config import INITIAL_CAPITAL, MARKETS

    names = {m.symbol: m.name for m in MARKETS}
    lines = [
        "INDIA TRADING BOT - WEEKLY PAPER BACKTEST REPORT",
        "=" * 58,
        f"Capital        : Rs {INITIAL_CAPITAL:,.0f}",
        f"Week period    : {analysis['week_start']} to {analysis['week_end']}",
        f"Markets        : VAML, VEDL, VEDPOWER, VISL, BHEL",
        "",
        "LAST 7 DAYS SUMMARY",
        f"  Start equity   : Rs {analysis['start_equity']:,.0f}",
        f"  End equity     : Rs {analysis['end_equity']:,.0f}",
        f"  Week P&L       : Rs {analysis['week_pnl']:,.0f}",
        f"  Week return    : {analysis['week_return_pct']:+.2f}%",
        f"  Trades closed  : {analysis['num_trades']}",
        f"  Win rate       : {analysis['win_rate']:.1f}%",
        "",
    ]

    if analysis["by_symbol"]:
        lines.append("PER SYMBOL (closed trades this week)")
        lines.append("-" * 58)
        for sym, pnls in analysis["by_symbol"].items():
            label = names.get(sym, sym)
            lines.append(
                f"  {label:22s}  {len(pnls):3d} trades  Rs {sum(pnls):,.0f}"
            )
        lines.append("")

    daily = analysis["daily_pnl"]
    if not daily.empty:
        lines.append("DAILY BREAKDOWN")
        lines.append("-" * 58)
        for _, r in daily.iterrows():
            sign = "+" if r["daily_pnl"] >= 0 else ""
            lines.append(
                f"  {r['date']}  {sign}Rs {r['daily_pnl']:,.0f}  "
                f"({r['daily_return_pct']:+.2f}%)  equity Rs {r['equity']:,.0f}"
            )
        lines.append("")

    if analysis["open_positions"]:
        lines.extend(["OPEN POSITIONS (end of week)", "-" * 58])
        for p in analysis["open_positions"]:
            label = names.get(p["symbol"], p["symbol"])
            side = "LONG" if p["side"] == 1 else "SHORT"
            lines.append(f"  {label} {side} @ Rs {p['entry_price']:.2f}")
        lines.append("")

    lines.extend([
        "=" * 58,
        "Note: VAML, VEDPOWER, VISL have limited history (recent listing).",
        "Brokerage and taxes not included. Past results do not guarantee future returns.",
    ])
    return "\n".join(lines)
