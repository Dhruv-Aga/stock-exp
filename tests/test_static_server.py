"""Tests for restricted static file server."""

from __future__ import annotations

from scripts.static_server import _is_allowed, _resolve_path


def test_blocks_env_and_data():
    assert _is_allowed(".env") is False
    assert _is_allowed("data/trading.db") is False
    assert _is_allowed("server/.env") is False
    assert _resolve_path("/.env") is None


def test_allows_ui_paths():
    assert _is_allowed("index.html") is True
    assert _is_allowed("portfolio/index.html") is True
    assert _is_allowed("src/shell/config.js") is True
