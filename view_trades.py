#!/usr/bin/env python3
"""CLI tool to view trades recorded in the database."""

import argparse
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.settings import DB_PATH, load_settings


def main():
    parser = argparse.ArgumentParser(
        description="Query and display trades recorded in the database"
    )
    parser.add_argument(
        "--run-type",
        choices=["paper", "dry_run", "live"],
        help="Filter trades by run type (paper, dry_run, live)",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Filter trades by stock symbol (e.g., VEDL.NS)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Number of recent trades to display (default: 30)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        help="Path to export the query results as a CSV file",
    )
    args = parser.parse_args()

    load_settings()

    if not DB_PATH.exists():
        print(f"Database file does not exist at: {DB_PATH}")
        print("No trades have been recorded yet.")
        sys.exit(0)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trades';"
    )
    if not cursor.fetchone():
        print("The 'trades' table does not exist in the database yet.")
        print("Run paper or live execution sessions to record trades first.")
        conn.close()
        sys.exit(0)

    query = "SELECT * FROM trades WHERE 1=1"
    params = []

    if args.run_type:
        query += " AND run_type = ?"
        params.append(args.run_type)

    if args.symbol:
        query += " AND (symbol = ? OR symbol LIKE ?)"
        params.extend([args.symbol, f"{args.symbol}%"])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    rows = cursor.execute(query, tuple(params)).fetchall()
    conn.close()

    if not rows:
        print("No matching trades found in the database.")
        sys.exit(0)

    trades = [dict(r) for r in rows]

    # Convert to pandas DataFrame for pretty representation and CSV exporting
    try:
        import pandas as pd
        df = pd.DataFrame(trades)
        
        # Clean column ordering for output
        cols = [
            "id", "symbol", "side", "quantity", 
            "entry_time", "entry_price", 
            "exit_time", "exit_price", 
            "pnl", "return_pct", "reason", "run_type"
        ]
        # Keep only existing columns
        cols = [c for c in cols if c in df.columns]
        df = df[cols]

        if args.csv:
            df.to_csv(args.csv, index=False)
            print(f"Successfully exported {len(df)} trades to: {args.csv}")
        else:
            print("\n" + "=" * 100)
            print(f"RECENTS TRADES DATABASE (Showing last {len(df)} matches)")
            print("=" * 100)
            # Formatting floats
            formatters = {
                "entry_price": lambda x: f"Rs {x:,.2f}",
                "exit_price": lambda x: f"Rs {x:,.2f}",
                "pnl": lambda x: f"Rs {x:+,.2f}",
                "return_pct": lambda x: f"{x:+.2f}%",
                "quantity": lambda x: f"{x:.1f}",
            }
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(df.to_string(index=False, formatters=formatters))
            print("=" * 100 + "\n")
    except ImportError:
        # Fallback manual formatting if pandas is not available
        if args.csv:
            import csv
            with open(args.csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=trades[0].keys())
                writer.writeheader()
                writer.writerows(trades)
            print(f"Exported {len(trades)} trades to: {args.csv}")
        else:
            print("\n" + "=" * 90)
            print(f"RECENTS TRADES DATABASE (Showing last {len(trades)} matches)")
            print("=" * 90)
            header = f"{'ID':<4} | {'Symbol':<12} | {'Side':<5} | {'Qty':<5} | {'Entry Price':<12} | {'Exit Price':<12} | {'P&L (Rs)':<11} | {'Return %':<8} | {'Type':<8}"
            print(header)
            print("-" * 90)
            for t in trades:
                side_str = t["side"].upper()
                pnl_str = f"{t['pnl']:+,.1f}"
                ret_str = f"{t['return_pct']:+.2f}%"
                print(
                    f"{t['id']:<4} | {t['symbol']:<12} | {side_str:<5} | {t['quantity']:<5.1f} | "
                    f"Rs {t['entry_price']:<9.2f} | Rs {t['exit_price']:<9.2f} | {pnl_str:<11} | {ret_str:<8} | {t['run_type']:<8}"
                )
            print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
