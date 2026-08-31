#!/usr/bin/env python3
"""Generate a simple HTML dashboard from the paper trading session.

This script runs the paper trading session (updates data/paper_state.json),
builds the analysis via src.paper_report.build_paper_analysis and writes
paper/index.html (suitable for GitHub Pages) and paper/analysis.json.
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

PAPER_DIR = ROOT / "paper"
PAPER_DIR.mkdir(parents=True, exist_ok=True)


def render_html(analysis: dict) -> str:
    gen = analysis.get("generated_at")
    if hasattr(gen, "strftime"):
        gen = gen.strftime("%Y-%m-%d %H:%M")
    title = "India Trading Bot — Paper Dashboard"
    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial; max-width: 1200px; margin: 20px auto; padding: 0 18px; background:#f6f8fa }
    header { display:flex; justify-content:space-between; align-items:center }
    h1 { font-size: 1.4rem; margin:0 }
    .meta { color:#666 }
    .cards { display:flex; gap:12px; margin:12px 0 }
    .card { background:#fff; border:1px solid #e1e4e8; border-radius:8px; padding:12px; box-shadow:0 1px 0 rgba(0,0,0,0.02) }
    .card.small { flex:1; min-width:140px }
    .grid { display:grid; grid-template-columns: 1fr 420px; gap:12px; align-items:start }
    table { width:100%; border-collapse:collapse; font-size:0.95rem }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #f1f1f1 }
    th.sortable { cursor:pointer; color:#0366d6 }
    .muted { color:#666; font-size:0.9rem }
    .pos-positive { color: green }
    .pos-negative { color: red }
    canvas { width:100% !important; height:220px !important }
    .controls { display:flex; gap:8px; align-items:center }
    input[type=search] { padding:6px 8px; border-radius:6px; border:1px solid #ddd }
    .download { padding:6px 10px; border-radius:6px; background:#0366d6; color:#fff; border:none }
    .site-nav { display:flex; gap:16px; margin-bottom:12px; font-size:0.9rem }
    .site-nav a { color:#0366d6; text-decoration:none }
    .site-nav a:hover { text-decoration:underline }
    """

    def money(v):
        try:
            return f"Rs {v:,.0f}"
        except Exception:
            return str(v)

    # Prepare chart data
    daily = analysis.get('daily_equity') or []
    daily_labels = [str(r.get('date')) for r in reversed(daily[-90:])]
    daily_equity = [float(r.get('equity')) if r.get('equity') is not None else None for r in reversed(daily[-90:])]

    recent = analysis.get('recent_trades') or []
    recent_labels = [str(t.get('exit_time'))[:16] for t in recent[:50]]
    recent_pnl = [float(t.get('pnl', 0)) for t in recent[:50]]

    all_trades_for_table = analysis.get('recent_trades') or []

    symbols_summary = {}
    for t in all_trades_for_table:
        s = t.get('symbol')
        pnl = float(t.get('pnl', 0))
        qty = float(t.get('quantity', 0))
        symbols_summary.setdefault(s, {"pnl":0.0, "trades":0, "qty":0.0})
        symbols_summary[s]['pnl'] += pnl
        symbols_summary[s]['trades'] += 1
        symbols_summary[s]['qty'] += qty

    html_lines = [
        "<!doctype html>",
        "<html>",
        "<head>",
        f"<meta charset=\"utf-8\" />",
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />",
        f"<title>{html.escape(title)}</title>",
        f"<style>{css}</style>",
        "<script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>",
        "</head>",
        "<body>",
        "<nav class=\"site-nav\">",
        "<a href=\"/\">← Bharat Scout</a>",
        "<a href=\"/tracker/\">Portfolio Tracker</a>",
        "<a href=\"/paper/\">Paper Dashboard</a>",
        "<a href=\"/assistant/\">Assistant</a>",
        "</nav>",
        "<header>",
        f"<h1>{html.escape(title)}</h1>",
        f"<div class=\"meta\">Generated: {html.escape(str(gen))}</div>",
        "</header>",
        "<div class=\"cards\">",
        f"<div class=\"card small\"><div class=\"muted\">Equity</div><div><strong>{money(analysis.get('equity',0))}</strong></div></div>",
        f"<div class=\"card small\"><div class=\"muted\">Cash</div><div><strong>{money(analysis.get('cash',0))}</strong></div></div>",
        f"<div class=\"card small\"><div class=\"muted\">Unrealized</div><div><strong>{money(analysis.get('unrealized_pnl',0))}</strong></div></div>",
        f"<div class=\"card small\"><div class=\"muted\">Closed trades</div><div><strong>{analysis.get('total_closed_trades',0)}</strong></div></div>",
        "</div>",
        "<div class=\"controls\">",
        "<input id=\"globalFilter\" type=\"search\" placeholder=\"Filter trades / symbols\" />",
        "<button class=\"download\" onclick=\"downloadJSON()\">Download JSON</button>",
        "<button class=\"download\" onclick=\"downloadCSV()\">Download CSV</button>",
        "</div>",
        "<div class=\"grid\">",
    ]

    # Left: charts and symbols summary
    html_lines += [
        "<div>",
        "<div class=\"card\"><h3>Equity (last 90 days)</h3><canvas id=\"equityChart\"></canvas></div>",
        "<div class=\"card\"><h3>Cumulative Returns (closed trades)</h3><canvas id=\"cumChart\"></canvas></div>",
        "</div>",
    ]

    # Right: open positions and symbols summary
    html_lines += [
        "<div>",
        "<div class=\"card\"><h3>Portfolio snapshot</h3>",
        "<ul>",
        f"<li>Equity: <strong>{money(analysis.get('equity', 0))}</strong></li>",
        f"<li>Cash: <strong>{money(analysis.get('cash', 0))}</strong></li>",
        f"<li>Unrealized P&L: <strong>{money(analysis.get('unrealized_pnl', 0))}</strong></li>",
        f"<li>Total return: <strong>{analysis.get('total_return_pct', 0):+.2f}%</strong></li>",
        f"<li>Open positions: <strong>{len(analysis.get('open_positions', []))}</strong></li>",
        "</ul></div>",
        "<div class=\"card\"><h3>Positions</h3>",
    ]

    open_positions = analysis.get('open_positions') or []
    if not open_positions:
        html_lines.append("<div class=\"muted\">No open positions</div>")
    else:
        html_lines.append("<table>")
        html_lines.append("<tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Mark</th><th>Qty</th><th>uP&L</th></tr>")
        for p in open_positions:
            pnl = p.get('unrealized_pnl', 0)
            cls = 'pos-positive' if pnl >= 0 else 'pos-negative'
            html_lines.append(
                f"<tr><td>{html.escape(p.get('symbol',''))}</td>"
                f"<td>{html.escape(p.get('side',''))}</td>"
                f"<td>{money(p.get('entry_price',0))}</td>"
                f"<td>{money(p.get('mark_price',0))}</td>"
                f"<td>{p.get('quantity',0):.2f}</td>"
                f"<td class=\"{cls}\">{money(p.get('unrealized_pnl',0))}</td></tr>")
        html_lines.append("</table>")
    html_lines.append("</div>")

    # Symbols summary
    html_lines.append("<div class=\"card\"><h3>Symbol summary</h3>")
    if not symbols_summary:
        html_lines.append("<div class=\"muted\">No closed trades</div>")
    else:
        html_lines.append("<table>")
        html_lines.append("<tr><th>Symbol</th><th>Trades</th><th>Total P&L</th><th>Quantity</th></tr>")
        for s, v in symbols_summary.items():
            cls = 'pos-positive' if v['pnl'] >= 0 else 'pos-negative'
            html_lines.append(f"<tr><td>{html.escape(s)}</td><td>{v['trades']}</td><td class=\"{cls}\">{money(v['pnl'])}</td><td>{v['qty']:.2f}</td></tr>")
        html_lines.append("</table>")
    html_lines.append("</div>")

    html_lines.append("</div>")

    # All trades table with search and sort
    html_lines.append("<div class=\"card\"><h3>All closed trades</h3>")
    html_lines.append("<div class=\"muted\">Use the search box above to filter. Click headers to sort.</div>")
    all_trades = all_trades_for_table
    if not all_trades:
        html_lines.append("<div class=\"muted\">No closed trades</div>")
    else:
        html_lines.append("<table id=\"allTradesTable\">")
        html_lines.append("<thead><tr>")
        headers = ["Exit","Symbol","Side","Entry","Exit","P&L","Reason"]
        for h in headers:
            html_lines.append(f"<th class=\"sortable\">{h}</th>")
        html_lines.append("</tr></thead><tbody>")
        for t in all_trades:
            pnl = float(t.get('pnl',0))
            cls = 'pos-positive' if pnl >= 0 else 'pos-negative'
            exit_time = str(t.get('exit_time',''))[:16]
            reason = t.get('reason','') or ''
            html_lines.append(
                f"<tr><td>{html.escape(exit_time)}</td>"
                f"<td>{html.escape(t.get('symbol',''))}</td>"
                f"<td>{html.escape(t.get('side',''))}</td>"
                f"<td>{money(t.get('entry_price',0))}</td>"
                f"<td>{money(t.get('exit_price',0))}</td>"
                f"<td class=\"{cls}\">{money(pnl)}</td>"
                f"<td>{html.escape(str(reason))}</td></tr>")
        html_lines.append("</tbody></table>")
    html_lines.append("</div>")

    # Embed JS data and render charts + utilities
    html_lines.append("<script>")
    html_lines.append(f"const equityLabels = {json.dumps(daily_labels)};")
    html_lines.append(f"const equityData = {json.dumps(daily_equity)};")
    html_lines.append(f"const tradesLabels = {json.dumps(recent_labels)};")
    html_lines.append(f"const tradesData = {json.dumps(recent_pnl)};")
    html_lines.append(f"const allTrades = {json.dumps(all_trades_for_table, default=str)};")

    html_lines.append(r"const equityCtx = document.getElementById('equityChart').getContext('2d');")
    html_lines.append(r"new Chart(equityCtx, { type: 'line', data: { labels: equityLabels, datasets: [{ label: 'Equity', data: equityData, borderColor: 'rgb(33,150,243)', backgroundColor: 'rgba(33,150,243,0.08)', tension: 0.2 }] }, options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: false } } } });")

    html_lines.append(r"const cumCtx = document.getElementById('cumChart').getContext('2d');")
    html_lines.append(r"const cumData = (function(){ let s=0; return allTrades.map(t=>{ s+= (t.pnl? Number(t.pnl):0); return s; }); })();")
    html_lines.append(r"new Chart(cumCtx, { type: 'line', data: { labels: allTrades.map(t=>String(t.exit_time).slice(0,16)), datasets: [{ label: 'Cumulative P&L', data: cumData, borderColor: 'rgb(75,192,192)', backgroundColor: 'rgba(75,192,192,0.08)', tension: 0.2 }] }, options: { plugins: { legend: { display: false } } } });")

    html_lines.append(r"const tradesCtx = document.getElementById('tradesChart').getContext('2d');")
    html_lines.append(r"new Chart(tradesCtx, { type: 'bar', data: { labels: tradesLabels, datasets: [{ label: 'P&L', data: tradesData, backgroundColor: tradesData.map(v => v>=0 ? 'rgba(40,167,69,0.7)' : 'rgba(220,53,69,0.7)') }] }, options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { maxRotation: 60, minRotation: 30 } } } } });")

    # Client-side utilities: download JSON/CSV, filter and sort
    html_lines.append(r"function downloadJSON(){ const a=document.createElement('a'); const blob=new Blob([JSON.stringify({analysis: allTrades},null,2)],{type:'application/json'}); a.href=URL.createObjectURL(blob); a.download='trades.json'; a.click(); }")
    html_lines.append(r"function downloadCSV(){ if(!allTrades.length){ alert('No trades to export'); return; } const keys=Object.keys(allTrades[0]); const rows=[keys.join(',')]; allTrades.forEach(t=>{ rows.push(keys.map(k=> '"'+String(t[k]||'')+'"').join(',')); }); const a=document.createElement('a'); const blob=new Blob([rows.join('\n')],{type:'text/csv'}); a.href=URL.createObjectURL(blob); a.download='trades.csv'; a.click(); }")
    html_lines.append(r"document.getElementById('globalFilter').addEventListener('input', function(e){ const q=e.target.value.toLowerCase(); document.querySelectorAll('#allTradesTable tbody tr').forEach(r=>{ r.style.display = r.innerText.toLowerCase().includes(q) ? '' : 'none'; }); });")

    # Sortable headers
    html_lines.append(r"document.querySelectorAll('#allTradesTable th.sortable').forEach((th,idx)=>{ th.addEventListener('click', ()=>{ const tbody=th.closest('table').querySelector('tbody'); const rows=Array.from(tbody.querySelectorAll('tr')); const asc = !th.classList.contains('asc'); rows.sort((a,b)=>{ const aText=a.children[idx].innerText.trim(); const bText=b.children[idx].innerText.trim(); const aNum=parseFloat(aText.replace(/[^0-9.-]+/g,'')); const bNum=parseFloat(bText.replace(/[^0-9.-]+/g,'')); if(!isNaN(aNum) && !isNaN(bNum)) return asc? aNum-bNum: bNum-aNum; return asc? aText.localeCompare(bText): bText.localeCompare(aText); }); tbody.innerHTML=''; rows.forEach(r=>tbody.appendChild(r)); document.querySelectorAll('#allTradesTable th').forEach(h=>h.classList.remove('asc','desc')); th.classList.add(asc?'asc':'desc'); }); });")

    html_lines.append("</script>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def main():
    parser = argparse.ArgumentParser(description="Generate dashboard from paper trading session")
    parser.add_argument("--refresh", action="store_true", help="Refresh market data")
    parser.add_argument("--no-refresh", action="store_true", help="Use cached data")
    args = parser.parse_args()

    refresh = args.refresh and not args.no_refresh
    # Load any previously-committed trades JSON so the dashboard can show history
    SAVED_TRADES = ROOT / "data" / "trades.json"
    saved_trades = []
    if SAVED_TRADES.exists():
        try:
            saved_trades = json.loads(SAVED_TRADES.read_text(encoding="utf-8"))
        except Exception:
            saved_trades = []

    session = run_paper_session(refresh=refresh)
    analysis = build_paper_analysis(session=session)

    # If DB has no trades (common on ephemeral runners), fall back to saved_trades
    if (not analysis.get('recent_trades')) and saved_trades:
        analysis['recent_trades'] = saved_trades[-20:]
        analysis['total_closed_trades'] = len(saved_trades)

    # If there's no daily_equity (no DB equity snapshots), derive a simple equity series
    # from saved_trades so charts can render on ephemeral runners.
    if (not analysis.get('daily_equity')) and saved_trades:
        try:
            trades_sorted = sorted(saved_trades, key=lambda t: t.get('exit_time') or '')
            cum = 0.0
            # Estimate starting equity from analysis: equity - total_pnl (falls back to 0)
            start_equity = float(analysis.get('equity', 0)) - float(analysis.get('total_pnl', 0))
            derived = []
            for t in trades_sorted:
                pnl = float(t.get('pnl') or 0)
                cum += pnl
                exit_time = str(t.get('exit_time') or '')
                # normalize date portion
                date_label = exit_time.split('T')[0] if 'T' in exit_time else exit_time.split(' ')[0] if exit_time else ''
                derived.append({
                    'date': date_label,
                    'realized_pnl': pnl,
                    'unrealized_pnl': 0.0,
                    'equity': start_equity + cum,
                })
            # keep only the last 90 points
            analysis['daily_equity'] = derived[-90:]
        except Exception:
            # If anything fails, leave daily_equity as empty list
            analysis['daily_equity'] = []

    # Persist JSON analysis for tracker page and GitHub MCP
    with (PAPER_DIR / "analysis.json").open("w", encoding="utf-8") as f:
        json.dump({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in analysis.items()}, f, default=str, indent=2)

    html_out = render_html(analysis)
    with (PAPER_DIR / "index.html").open("w", encoding="utf-8") as f:
        f.write(html_out)

    # Export DB trades to data/trades.json so future runs can reuse history
    try:
        from src.db import all_trades  # noqa: E402

        all_t = all_trades(run_type="paper")
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        with (ROOT / "data" / "trades.json").open("w", encoding="utf-8") as f:
            json.dump(all_t, f, default=str, indent=2)
    except Exception:
        pass

    print(f"Wrote dashboard to {PAPER_DIR / 'index.html'}")
    print(f"Wrote analysis to {PAPER_DIR / 'analysis.json'}")


if __name__ == '__main__':
    main()
