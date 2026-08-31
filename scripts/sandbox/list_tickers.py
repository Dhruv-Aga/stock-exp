#!/usr/bin/env python3
"""Example sandbox script — list configured tickers."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import MARKETS

tickers = [{"symbol": m.symbol, "strategy": m.strategy} for m in MARKETS]
print(json.dumps({"tickers": tickers}, indent=2))
