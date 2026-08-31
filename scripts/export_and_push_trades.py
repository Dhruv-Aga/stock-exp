#!/usr/bin/env python3
"""Export trades and paper state from local DB to JSON and push to repo.

Usage: run this on the machine that has the SQLite DB (data/trading.db).
It will read trades (paper run_type), write data/trades.json and data/paper_state.json
and commit+push to origin/main so the GitHub Actions dashboard picks up history.

Security: do NOT run this on a machine with live API keys in .env committed — the script does not touch .env.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# Import DB helper
sys.path.insert(0, str(ROOT))
try:
    from src.db import all_trades
except Exception as e:
    print("Failed to import src.db. Run this from the repo root where src/ is on PYTHONPATH.")
    raise


def write_trades_json():
    trades = all_trades(run_type="paper")
    out = DATA / "trades.json"
    out.write_text(json.dumps(trades, default=str, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return out


def write_state_json():
    # Attempt to copy paper_state.json if present
    state_file = ROOT / "data" / "paper_state.json"
    out = DATA / "paper_state.json"
    if state_file.exists():
        out.write_text(state_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {out}")
        return out
    print("No paper_state.json found locally to export")
    return None


def git_commit_and_push(paths: list[Path]):
    # Stage, commit and push
    cmds = [
        ["git", "add"] + [str(p) for p in paths],
        ["git", "commit", "-m", "Auto: export trades and paper state [ci skip]"] ,
        ["git", "push", "origin", "main"],
    ]
    for cmd in cmds:
        print("Running:", " ".join(cmd))
        res = subprocess.run(cmd, cwd=str(ROOT))
        if res.returncode != 0:
            print("Command failed:", cmd)
            return False
    return True


def main():
    t = write_trades_json()
    s = write_state_json()
    paths = [p for p in [t, s] if p]
    if not paths:
        print("Nothing to commit")
        return
    ok = git_commit_and_push(paths)
    if ok:
        print("Pushed trades/state to origin/main")
    else:
        print("Failed to push — check git credentials and remote")


if __name__ == '__main__':
    main()
