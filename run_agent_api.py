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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import settings
from src.agent.chat import list_available_tools, run_agent_chat
from src.approvals.executor import approve_and_execute
from src.approvals.store import list_proposals, pending_count, reject_proposal

settings.load_settings()

app = FastAPI(title="Bharat Scout Trading Assistant", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class RejectRequest(BaseModel):
    note: str = ""


def _frontend_running() -> bool:
    port = os.environ.get("FRONTEND_PORT", "8080")
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=1) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _load_paper_analysis() -> dict:
    path = ROOT / "paper" / "analysis.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


@app.get("/api/agent/health")
def health():
    return {
        "ok": True,
        "groq_configured": bool(settings.groq_api_key()),
        "kite_configured": settings.kite_configured(),
        "live_trading": not settings.dry_run_mode(),
        "require_trade_approval": settings.require_trade_approval(),
        "auto_approve_trades": settings.auto_approve_trades(),
        "pending_proposals": pending_count(),
        "tools_count": len(list_available_tools()),
    }


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


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("AGENT_API_PORT", "8000"))
    uvicorn.run("run_agent_api:app", host="0.0.0.0", port=port, reload=False)
