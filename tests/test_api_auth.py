"""Tests for API authentication."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _client(monkeypatch, api_key: str = ""):
    monkeypatch.setenv("BHARAT_SCOUT_API_KEY", api_key)
    import src.settings as settings_mod

    importlib.reload(settings_mod)
    import run_agent_api

    importlib.reload(run_agent_api)
    return TestClient(run_agent_api.app)


def test_health_public_when_auth_required(monkeypatch):
    client = _client(monkeypatch, api_key="secret-key")
    res = client.get("/api/agent/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["auth_required"] is True
    assert "pending_proposals" not in body


def test_protected_route_requires_key(monkeypatch):
    client = _client(monkeypatch, api_key="secret-key")
    res = client.get("/api/approvals")
    assert res.status_code == 401

    res = client.get("/api/approvals", headers={"X-Bharat-Scout-Key": "secret-key"})
    assert res.status_code == 200


def test_open_when_no_api_key_configured(monkeypatch):
    client = _client(monkeypatch, api_key="")
    res = client.get("/api/approvals")
    assert res.status_code == 200
