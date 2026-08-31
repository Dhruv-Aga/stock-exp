#!/usr/bin/env python3
"""Export trades and paper state from local DB to JSON and optionally push to repo.

Usage: run this on the machine that has the SQLite DB (data/trading.db).
By default the script only writes data/trades.json (and copies paper_state.json if present).
Use --push to attempt a git commit+push (commits only trades.json by default).

Options:
  --push                Attempt to commit and push to origin (default: no push)
  --include-state       Include paper_state.json in the commit (not recommended for public repos)
  --branch BRANCH       Remote branch to push to (default: main)
  --pull-first          Run 'git pull --rebase origin BRANCH' before push
  --token TOKEN         Use a personal access token for HTTPS push (or set GIT_PUSH_TOKEN env)

Security: do NOT run this on a machine with live API keys in .env committed — the script does not touch .env.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# Ensure sqlite3 available
import sqlite3


def write_trades_json():
    """Read all trades from the local SQLite DB and write data/trades.json."""
    db_path = ROOT / "data" / "trading.db"
    trades = []
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM trades ORDER BY exit_time ASC')
        rows = cur.fetchall()
        for r in rows:
            trades.append({k: r[k] for k in r.keys()})
        conn.close()
    out = DATA / "trades.json"
    out.write_text(json.dumps(trades, default=str, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return out


def write_state_json():
    """Copy paper_state.json (if present) to data/ for archival. This file is typically in .gitignore."""
    state_file = ROOT / "data" / "paper_state.json"
    out = DATA / "paper_state.json"
    if state_file.exists():
        out.write_text(state_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {out}")
        return out
    print("No paper_state.json found locally to export")
    return None


def run(cmd, cwd=ROOT, check=False, capture=False, env=None):
    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(cwd), check=False, capture_output=capture, env=env)
    if capture:
        stdout = res.stdout.decode('utf-8', errors='ignore') if res.stdout else ''
        stderr = res.stderr.decode('utf-8', errors='ignore') if res.stderr else ''
        return res.returncode, stdout, stderr
    return res.returncode


def git_commit_and_push(paths: list[Path], branch: str = 'main', pull_first: bool = False, token: str | None = None):
    """Stage, commit and push given paths. If token provided and remote is https, temporarily rewrite origin URL.
    Only paths under the repo will be used.
    """
    # Convert to relative paths
    rel_paths = [str(p.relative_to(ROOT)) for p in paths]

    # Optional pull first
    if pull_first:
        rc = run(["git", "pull", "--rebase", "origin", branch])
        if rc != 0:
            print("git pull failed; continuing but this may cause push conflicts")

    # git add
    rc = run(["git", "add"] + rel_paths)
    if rc != 0:
        print("git add failed")
        return False

    # git commit (may return non-zero if nothing to commit)
    rc, out, err = run(["git", "commit", "-m", "Auto: export trades [ci skip]"], capture=True)
    if rc != 0:
        if 'nothing to commit' in out.lower() or 'nothing to commit' in err.lower():
            print("No changes to commit")
            return True
        print("git commit failed:\n", out, err)
        return False

    # Push
    original_url_rc, original_url, _ = run(["git", "remote", "get-url", "origin"], capture=True)
    original_url = original_url.strip() if original_url else ''
    temp_set = False
    try:
        env = os.environ.copy()
        if token:
            if original_url.startswith("https://"):
                token_url = original_url.replace("https://", f"https://{token}@")
                # Set remote url temporarily
                rc = run(["git", "remote", "set-url", "origin", token_url])
                if rc != 0:
                    print("Failed to set token remote URL; aborting push")
                    return False
                temp_set = True
            else:
                print("Remote is not HTTPS; token-based push not supported for SSH remotes.")
                # proceed without token
        rc = run(["git", "push", "origin", branch], env=env)
        if rc != 0:
            print("git push failed; check credentials and remote:")
            return False
    finally:
        if temp_set and original_url:
            run(["git", "remote", "set-url", "origin", original_url])
    return True


def parse_args():
    p = argparse.ArgumentParser(description="Export trades.json and optionally push to origin")
    p.add_argument('--push', action='store_true', help='Attempt to commit and push the exported files')
    p.add_argument('--include-state', action='store_true', help='Include paper_state.json in the commit (not recommended)')
    p.add_argument('--branch', default='main', help='Remote branch to push to (default: main)')
    p.add_argument('--pull-first', action='store_true', help='Run git pull --rebase before pushing')
    p.add_argument('--token', default=None, help='GitHub personal access token (or set GIT_PUSH_TOKEN env var)')
    return p.parse_args()


def main():
    args = parse_args()
    t = write_trades_json()
    s = None
    if args.include_state:
        s = write_state_json()

    paths = [t]
    if args.include_state and s:
        paths.append(s)

    if not args.push:
        print("Not pushing -- run with --push to attempt commit & push. Exiting.")
        return

    token = args.token or os.environ.get('GIT_PUSH_TOKEN') or os.environ.get('GH_PAGES_DEPLOY_TOKEN')
    ok = git_commit_and_push(paths, branch=args.branch, pull_first=args.pull_first, token=token)
    if ok:
        print("Pushed trades to origin/{}".format(args.branch))
    else:
        print("Failed to push — check git credentials and remote")


if __name__ == '__main__':
    main()
