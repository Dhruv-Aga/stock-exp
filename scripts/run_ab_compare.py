#!/usr/bin/env python3
"""Run paper vs live-shadow A/B comparison and print summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ab_compare import run_ab_comparison


def main() -> int:
    refresh = "--no-refresh" not in sys.argv
    result = run_ab_comparison(refresh=refresh, save=True)
    summary = result.get("summary", {})
    print("=" * 60)
    print("PAPER vs LIVE-SHADOW A/B COMPARISON")
    print("=" * 60)
    print(f"Generated: {result.get('generated_at')}")
    print(f"Data source: {result.get('data_source')}")
    print(f"Parity score: {summary.get('parity_score', 0):.1%}")
    print(f"Exit intents: {summary.get('exit_intents', 0)}")
    print(f"Entry intents: {summary.get('entry_intents', 0)}")
    print(f"Skips: {summary.get('skips', 0)}")
    print(f"Equity delta (same book): Rs{summary.get('equity_delta_same_book', 0):,.2f}")
    divergences = result.get("same_book_comparison", {}).get("divergences", [])
    if divergences:
        print("\nDivergences:")
        for d in divergences:
            print(f"  [{d['index']}] paper: {d.get('paper')}")
            print(f"       live:  {d.get('live_shadow')}")
    else:
        print("\nNo divergences — paper and live-shadow actions match.")
    print(f"\nSaved to data/ab_compare.json")
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
