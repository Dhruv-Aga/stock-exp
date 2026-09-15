#!/usr/bin/env python3
"""FastAPI server for the in-app trading assistant and approval workflow."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src import settings
from src.api_auth import ApiAuthMiddleware, require_api_key
from src.agent.chat import list_available_tools, run_agent_chat
from src.approvals.executor import approve_and_execute
from src.approvals.store import list_proposals, pending_count, reject_proposal
from src.db import get_chat_session, list_chat_sessions, save_chat_session
from src.paper_report import build_paper_analysis
from src.triggers import list_alerts, get_alert, run_portfolio_checks, mark_reviewed
from src.triggers.analyzer import analyze_alert_with_llm, batch_analyze_pending_alerts

settings.load_settings()

app = FastAPI(title="Bharat Scout Trading Assistant", version="1.2.0")

app.add_middleware(ApiAuthMiddleware)

_allowed_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|\[::1\]|"
        r"[\w-]+(\.local)?|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-Bharat-Scout-Key", "Authorization"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class RejectRequest(BaseModel):
    note: str = ""


class ChatSessionPayload(BaseModel):
    title: str = "New chat"
    messages: list[ChatMessage] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AlertReviewRequest(BaseModel):
    action_taken: str = ""


def _frontend_running() -> bool:
    port = os.environ.get("FRONTEND_PORT", "8080")
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _load_paper_analysis() -> dict:
    try:
        return build_paper_analysis()
    except Exception:
        path = ROOT / "paper" / "analysis.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}


@app.get("/api/agent/health")
def health(request: Request):
    public = {
        "ok": True,
        "auth_required": settings.api_auth_required(),
    }
    if settings.api_auth_required():
        try:
            require_api_key(request)
        except HTTPException:
            return public
    return {
        **public,
        "groq_configured": bool(settings.groq_api_key()),
        "kite_configured": settings.kite_configured(),
        "live_trading": not settings.dry_run_mode(),
        "require_trade_approval": settings.require_trade_approval(),
        "auto_approve_trades": settings.auto_approve_trades(),
        "pending_proposals": pending_count(),
        "tools_count": len(list_available_tools()),
        "zerodha_auto_login": settings.zerodha_auto_login_configured(),
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/kite-login", response_class=HTMLResponse)
def kite_login_callback(request: Request):
    """Kite Connect login redirect target.

    After authorizing on Kite, Zerodha redirects here with a one-time
    ``request_token`` in the query string. This page displays that token so the
    user can paste it into ``run_kite_login.py`` (or complete the exchange
    directly). The route is public so the redirect works without an API key.
    """
    token = request.query_params.get("request_token", "")
    action = request.query_params.get("action", "")
    if not token:
        return HTMLResponse(
            "<h2>Kite login callback</h2>"
            "<p>No <code>request_token</code> found in the URL. "
            "Log in via <code>python run_kite_login.py</code> first.</p>",
            status_code=200,
        )

    exchange_error = ""
    access_token = ""
    if action == "login":
        try:
            from src import settings

            settings.load_settings()  # refresh .env (process may predate credential edits)
            from src.broker.kite_client import KiteClient

            client = KiteClient(dry_run=False)
            session = client.generate_session(token)
            access_token = session.get("access_token", "")
            if access_token:
                from src.kite_auto_login import save_cached_token

                save_cached_token(access_token, user_id=session.get("user_id", ""))
        except Exception as exc:  # noqa: BLE001 - surface any Kite error to the user
            exchange_error = str(exc)

    rows = "".join(
        f"<tr><td><code>{k}</code></td><td><code>{v}</code></td></tr>"
        for k, v in request.query_params.items()
    )
    token_html = f"<p><strong>request_token:</strong> <code>{token}</code></p>"
    if access_token:
        token_html += (
            "<p style='color:green'><strong>Success!</strong> Access token obtained "
            "and cached. It is also synced to <code>.env</code>.</p>"
        )
    elif exchange_error:
        token_html += (
            f"<p style='color:red'><strong>Token exchange failed:</strong> "
            f"<code>{exchange_error}</code></p>"
        )
    return HTMLResponse(
        "<h2>Kite login callback</h2>"
        f"{token_html}"
        "<p>Copy the <code>request_token</code> value above and paste it into "
        "<code>run_kite_login.py</code> when prompted.</p>"
        f"<h3>Query params</h3><table>{rows}</table>"
    )


@app.get("/api/paper/analysis")
def paper_analysis():
    return _load_paper_analysis()


@app.get("/api/trading/summary")
def trading_summary():
    analysis = _load_paper_analysis()
    open_positions = analysis.get("open_positions") or []
    return {
        "agent": {
            "online": True,
            "groq_configured": bool(settings.groq_api_key()),
            "kite_configured": settings.kite_configured(),
            "live_trading": not settings.dry_run_mode(),
            "require_trade_approval": settings.require_trade_approval(),
            "auto_approve_trades": settings.auto_approve_trades(),
            "pending_proposals": pending_count(),
            "tools_count": len(list_available_tools()),
        },
        "portfolio": {
            "equity": analysis.get("equity"),
            "cash": analysis.get("cash"),
            "unrealized_pnl": analysis.get("unrealized_pnl"),
            "total_return_pct": analysis.get("total_return_pct"),
            "open_positions": len(open_positions),
            "generated_at": analysis.get("generated_at"),
        },
        "signals": analysis.get("signals") or [],
        "session_actions": analysis.get("session_actions") or [],
        "mode": "live" if not settings.dry_run_mode() else "paper",
        "setup": {
            "env_file": (ROOT / ".env").exists(),
            "paper_snapshot": (ROOT / "paper" / "analysis.json").exists(),
            "services_running": _frontend_running(),
            "auto_approve_trades": settings.auto_approve_trades(),
        },
    }


@app.get("/api/trading/ab-comparison")
def ab_comparison_get(refresh: bool = False):
    """Return cached A/B comparison, or run a fresh one when refresh=true."""
    from src.ab_compare import load_ab_comparison, run_ab_comparison

    if refresh:
        return run_ab_comparison(refresh=True, save=True)
    cached = load_ab_comparison()
    if cached:
        return cached
    return run_ab_comparison(refresh=False, save=True)


@app.post("/api/trading/ab-comparison")
def ab_comparison_post(refresh: bool = True):
    from src.ab_compare import run_ab_comparison

    return run_ab_comparison(refresh=refresh, save=True)


@app.get("/api/agent/tools")
def tools():
    return {"tools": list_available_tools()}


@app.get("/api/agent/sessions")
def list_sessions():
    return {"sessions": list_chat_sessions(limit=50)}


@app.post("/api/agent/sessions")
def create_session(payload: ChatSessionPayload | None = None):
    cleaned = payload or ChatSessionPayload()
    session = save_chat_session(
        title=cleaned.title,
        messages=[m.model_dump() for m in cleaned.messages],
        metadata=cleaned.metadata,
    )
    return session


@app.get("/api/agent/sessions/{session_id}")
def get_session(session_id: str):
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@app.put("/api/agent/sessions/{session_id}")
def upsert_session(session_id: str, payload: ChatSessionPayload):
    return save_chat_session(
        session_id=session_id,
        title=payload.title,
        messages=[m.model_dump() for m in payload.messages],
        metadata=payload.metadata,
    )


@app.post("/api/agent/chat")
def chat(request: ChatRequest):
    messages = [m.model_dump() for m in request.messages]
    result = run_agent_chat(messages)
    result["pending_proposals"] = pending_count()
    return result


@app.get("/api/approvals")
def approvals_list(status: str = "pending"):
    st = None if status == "all" else status
    return {
        "proposals": list_proposals(status=st, limit=50),
        "pending_count": pending_count(),
        "require_trade_approval": settings.require_trade_approval(),
    }


@app.post("/api/approvals/{proposal_id}/approve")
def approvals_approve(proposal_id: str):
    """User explicitly approves and executes a live trade. Not callable by the LLM."""
    try:
        result = approve_and_execute(proposal_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/approvals/{proposal_id}/reject")
def approvals_reject(proposal_id: str, body: RejectRequest):
    try:
        return reject_proposal(proposal_id, note=body.note)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/triggers/check")
def triggers_check(auto_analyze: bool = True):
    """Run portfolio checks and queue alerts for LLM analysis."""
    try:
        result = run_portfolio_checks(auto_analyze=auto_analyze)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/triggers/alerts")
def triggers_list(status: str | None = None, symbol: str | None = None, limit: int = 50):
    """List portfolio alerts with optional filtering."""
    try:
        alerts = list_alerts(status=status, symbol=symbol, limit=limit)
        return {
            "alerts": alerts,
            "count": len(alerts),
            "total_pending": len(list_alerts(status="pending_analysis", limit=999)),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/triggers/alerts/{alert_id}")
def triggers_get_alert(alert_id: str):
    """Get a single alert by ID."""
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@app.post("/api/triggers/alerts/{alert_id}/analyze")
def triggers_analyze_alert(alert_id: str):
    """Run LLM analysis on a specific alert."""
    try:
        result = analyze_alert_with_llm(alert_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/triggers/analyze-pending")
def triggers_analyze_pending(limit: int = 10):
    """Run LLM analysis on up to N pending alerts."""
    try:
        results = batch_analyze_pending_alerts(limit=limit)
        return {
            "analyses_run": len(results),
            "results": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/triggers/alerts/{alert_id}/review")
def triggers_review_alert(alert_id: str, body: AlertReviewRequest):
    """Mark an alert as reviewed with optional action note."""
    try:
        alert = mark_reviewed(alert_id, action_taken=body.action_taken)
        return alert
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import os
    import uvicorn

    host = os.environ.get("HOST_BIND", "127.0.0.1")
    port = int(os.environ.get("AGENT_API_PORT", "8000"))
    uvicorn.run("run_agent_api:app", host=host, port=port, reload=False)
