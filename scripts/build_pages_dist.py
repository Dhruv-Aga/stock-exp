#!/usr/bin/env python3
"""Build a safe static artifact for GitHub Pages (no secrets, no backend code)."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist-pages"

# UI and demo assets only — never data/, server/, .env, or Python sources.
COPY_PATHS = [
    "index.html",
    "style.css",
    "home",
    "portfolio",
    "approvals",
    "assistant",
    "screener",
    "compare",
    "tracker",
    "src/app.js",
    "src/api.js",
    "src/data.js",
    "src/format.js",
    "src/shell",
]

# Optional demo snapshot — strip if you do not want any portfolio numbers public.
OPTIONAL_SNAPSHOT = ROOT / "paper" / "analysis.json"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for rel in COPY_PATHS:
        src = ROOT / rel
        dst = DIST / rel
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    if OPTIONAL_SNAPSHOT.exists():
        out = DIST / "paper" / "analysis.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OPTIONAL_SNAPSHOT, out)

    readme = DIST / "README-DEPLOY.txt"
    readme.write_text(
        "Static UI only. No agent API, approvals, or live trading on GitHub Pages.\n"
        "Do not commit real portfolio snapshots if this site is public.\n",
        encoding="utf-8",
    )
    print(f"Built Pages artifact at {DIST}")


if __name__ == "__main__":
    main()
