#!/usr/bin/env python3
"""Generate a simple HTML dashboard from the paper trading session.

This script runs the paper trading session (updates data/paper_state.json),
builds the analysis via src.paper_report.build_paper_analysis and writes
docs/index.html (suitable for GitHub Pages) and docs/analysis.json.
"""

from __future__ import annotations

import argparse
import json
import html
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.paper_trader import run_paper_session, STATE_FILE  # noqa: E402
from src.paper_report import build_paper_analysis  # noqa: E402

DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)


def render_html(analysis: dict) -> str:
    gen = analysis.get("generated_at")
    if hasattr(gen, "strftime"):
        gen = gen.strftime("%Y-%m-%d %H:%M")
    title = "India Trading Bot — Paper Dashboard"
    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial; max-width: 980px; margin: 24px auto; padding: 0 16px; }
    h1 { font-size: 1.4rem; }
    .card { border: 1px solid #e1e4e8; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #f1f1f1; }
    .muted { color: #666; font-size: 0.9rem }
    .pos-positive { color: green }
    .pos-negative { color: red }
    
    """

    def money(v):
        try:
            return f"Rs {v:,.0f}"
        except Exception:
            return str(v)

    html_lines = [
        "<!doctype html>",
        "<html>",
        "<head>",
        f"<meta charset=\"utf-8\" />",
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        f"<title>{html.escape(title)}</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<div class=\"muted\">Generated: {html.escape(str(gen))}</div>",
    ]

    # Snapshot
    html_lines.append("<div class=\"card\"><h2>Portfolio snapshot</h2>")
    html_lines.append("<ul>")
    html_lines.append(f"<li>Equity: <strong>{money(analysis.get('equity', 0))}</strong></li>")
    html_lines.append(f"<li>Cash: <strong>{money(analysis.get('cash', 0))}</strong></li>")
    html_lines.append(f"<li>Unrealized P&L: <strong>{money(analysis.get('unrealized_pnl', 0))}</strong></li>")
    html_lines.append(f"<li>Total return: <strong>{analysis.get('total_return_pct', 0):+.2f}%</strong></li>")
    html_lines.append(f"<li>Closed trades: <strong>{analysis.get('total_closed_trades', 0)}</strong></li>")
    html_lines.append(f"<li>Open positions: <strong>{len(analysis.get('open_positions', []))}</strong></li>")
    html_lines.append("</ul></div>")

    # Open positions
    open_positions = analysis.get('open_positions') or []
    html_lines.append("<div class=\"card\"><h2>Open positions</h2>")
    if not open_positions:
        html_lines.append("<div class=\"muted\">No open positions</div>")
    else:
        html_lines.append("<table>")
        html_lines.append("<tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Mark</th><th>Qty</th><th>uP&L</th><th>Stop</th></tr>")
        for p in open_positions:
            pnl = p.get('unrealized_pnl', 0)
            cls = 'pos-positive' if pnl >= 0 else 'pos-negative'
            html_lines.append(
                f"<tr><td>{html.escape(p.get('symbol',''))}</td>"
                f"<td>{html.escape(p.get('side',''))}</td>"
                f"<td>{money(p.get('entry_price',0))}</td>"
                f"<td>{money(p.get('mark_price',0))}</td>"
                f"<td>{p.get('quantity',0):.2f}</td>"
                f"<td class=\"{cls}\">{money(p.get('unrealized_pnl',0))}</td>"
                f"<td>{money(p.get('stop_price',0))}</td></tr>")
        html_lines.append("</table>")
    html_lines.append("</div>")

    # Recent trades
    recent = analysis.get('recent_trades') or []
    html_lines.append("<div class=\"card\"><h2>Recent closed trades</h2>")
    if not recent:
        html_lines.append("<div class=\"muted\">No recent closed trades</div>")
    else:
        html_lines.append("<table>")
        html_lines.append("<tr><th>Exit</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>P&L</th></tr>")
        for t in recent[:20]:
            pnl = float(t.get('pnl',0))
            cls = 'pos-positive' if pnl >= 0 else 'pos-negative'
            exit_time = str(t.get('exit_time',''))[:16]
            html_lines.append(
                f"<tr><td>{html.escape(exit_time)}</td>"
                f"<td>{html.escape(t.get('symbol',''))}</td>"
                f"<td>{html.escape(t.get('side',''))}</td>"
                f"<td>{money(t.get('entry_price',0))}</td>"
                f"<td>{money(t.get('exit_price',0))}</td>"
                f"<td class=\"{cls}\">{money(pnl)}</td></tr>")
        html_lines.append("</table>")
    html_lines.append("</div>")

    # Daily equity
    daily = analysis.get('daily_equity') or []
    html_lines.append("<div class=\"card\"><h2>Daily equity snapshots</h2>")
    if not daily:
        html_lines.append("<div class=\"muted\">No daily snapshots</div>")
    else:
        html_lines.append("<table>")
        html_lines.append("<tr><th>Date</th><th>Realized</th><th>Unrealized</th><th>Equity</th></tr>")
        for row in reversed(daily[-14:]):
            html_lines.append(
                f"<tr><td>{html.escape(str(row.get('date','')))}</td>"
                f"<td>{money(row.get('realized_pnl',0))}</td>"
                f"<td>{money(row.get('unrealized_pnl',0))}</td>"
                f"<td>{money(row.get('equity')) if row.get('equity') is not None else 'n/a'}</td></tr>")
        html_lines.append("</table>")
    html_lines.append("</div>")

    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def main():
    parser = argparse.ArgumentParser(description="Generate dashboard from paper trading session")
    parser.add_argument("--refresh", action="store_true", help="Refresh market data")
    parser.add_argument("--no-refresh", action="store_true", help="Use cached data")
    args = parser.parse_args()

    refresh = args.refresh and not args.no_refresh
    session = run_paper_session(refresh=refresh)
    analysis = build_paper_analysis(session=session)

    # Persist JSON analysis for debugging
    with (DOCS / "analysis.json").open("w", encoding="utf-8") as f:
        json.dump({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in analysis.items()}, f, default=str, indent=2)

    html_out = render_html(analysis)
    with (DOCS / "index.html").open("w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"Wrote dashboard to {DOCS / 'index.html'}")


if __name__ == '__main__':
    main()
