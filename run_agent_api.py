#!/usr/bin/env python3
"""FastAPI server for the in-app trading assistant."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import settings
from src.agent.chat import list_available_tools, run_agent_chat

settings.load_settings()

app = FastAPI(title="Bharat Scout Trading Assistant", version="1.0.0")

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


@app.get("/api/agent/health")
def health():
    return {
        "ok": True,
        "groq_configured": bool(settings.groq_api_key()),
        "kite_configured": settings.kite_configured(),
        "tools_count": len(list_available_tools()),
    }


@app.get("/api/agent/tools")
def tools():
    return {"tools": list_available_tools()}


@app.post("/api/agent/chat")
def chat(request: ChatRequest):
    messages = [m.model_dump() for m in request.messages]
    result = run_agent_chat(messages)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("run_agent_api:app", host="0.0.0.0", port=8000, reload=False)
