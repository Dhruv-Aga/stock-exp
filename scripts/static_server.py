#!/usr/bin/env python3
"""Restricted static file server — never exposes .env, data/, or source trees."""

from __future__ import annotations

import argparse
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

# Only these top-level paths are served over HTTP.
ALLOWED_PREFIXES = (
    "index.html",
    "style.css",
    "home/",
    "portfolio/",
    "approvals/",
    "assistant/",
    "screener/",
    "compare/",
    "paper/",
    "tracker/",
    "src/",
)

BLOCKED_PREFIXES = (
    ".env",
    ".git",
    ".dev",
    "data/",
    "server/",
    "scripts/",
    "tests/",
    "docs/",
)


def _is_allowed(rel: str) -> bool:
    rel = rel.lstrip("/")
    if not rel or rel.endswith("/"):
        rel = rel.rstrip("/") or "index.html"

    # Block hidden files and sensitive trees
    parts = Path(rel).parts
    if any(part.startswith(".") for part in parts):
        return False
    for blocked in BLOCKED_PREFIXES:
        if rel == blocked.rstrip("/") or rel.startswith(blocked):
            return False

    for allowed in ALLOWED_PREFIXES:
        if rel == allowed.rstrip("/") or rel.startswith(allowed):
            return True
    return False


def _resolve_path(rel: str) -> Path | None:
    rel = unquote(rel.lstrip("/"))
    if rel == "" or rel.endswith("/"):
        rel = (rel + "index.html") if rel else "index.html"

    if not _is_allowed(rel):
        return None

    candidate = (ROOT / rel).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


class RestrictedHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        # Quieter than default; dev.sh captures stdout/stderr
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        file_path = _resolve_path(path)
        if file_path is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        data = file_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bharat Scout restricted static server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FRONTEND_PORT", "8080")))
    parser.add_argument("--bind", default=os.environ.get("HOST_BIND", "127.0.0.1"))
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.bind, args.port), RestrictedHandler)
    print(f"Serving Bharat Scout UI on http://{args.bind}:{args.port} (restricted paths only)")
    server.serve_forever()


if __name__ == "__main__":
    main()
