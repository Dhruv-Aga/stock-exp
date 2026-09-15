"""Tests for Kite token cache helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.kite_auto_login import _token_expiry_ist, is_cached_token_valid, save_cached_token

IST = ZoneInfo("Asia/Kolkata")


def test_token_expiry_is_next_6am_ist():
    morning = datetime(2026, 9, 5, 7, 0, tzinfo=IST)
    expiry = _token_expiry_ist(morning)
    assert expiry.hour == 6
    assert expiry.date() == datetime(2026, 9, 6, tzinfo=IST).date()


def test_cached_token_validity(tmp_path, monkeypatch):
    token_file = tmp_path / "kite_token.json"
    monkeypatch.setattr("src.kite_auto_login.TOKEN_FILE", token_file)
    save_cached_token("abc123", user_id="AB1")
    assert is_cached_token_valid() is True

    stale = {
        "access_token": "abc123",
        "expires_at": (datetime.now(IST) - timedelta(hours=1)).isoformat(),
    }
    token_file.write_text(json.dumps(stale), encoding="utf-8")
    assert is_cached_token_valid() is False
