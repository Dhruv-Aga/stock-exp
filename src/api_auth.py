"""API authentication for local/LAN deployments."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src import settings

# Public endpoints (no API key required). Keep this list minimal.
PUBLIC_PATHS = frozenset(
    {
        "/api/agent/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _extract_key(request: Request) -> str:
    header = request.headers.get("X-Bharat-Scout-Key", "").strip()
    if header:
        return header
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def verify_api_key(provided: str) -> bool:
    expected = settings.api_auth_key()
    if not expected:
        return True
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


class ApiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.api_auth_required():
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)

        if not verify_api_key(_extract_key(request)):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required. Set X-Bharat-Scout-Key header.",
                    "auth_required": True,
                },
            )

        return await call_next(request)


def require_api_key(request: Request) -> None:
    if settings.api_auth_required() and not verify_api_key(_extract_key(request)):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Set X-Bharat-Scout-Key header.",
        )
