"""Automated Zerodha Kite Connect login via TOTP (no browser paste)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import requests

from src import settings

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "kite_token.json"
KITE_LOGIN_URL = "https://kite.zerodha.com/api/login"
KITE_TWOFA_URL = "https://kite.zerodha.com/api/twofa"


class KiteAutoLoginError(RuntimeError):
    """Raised when automated Kite login fails."""


def _token_expiry_ist(now: datetime | None = None) -> datetime:
    """Kite access tokens expire at the next 6:00 AM IST boundary."""
    now = now or datetime.now(IST)
    cutoff = datetime.combine(now.date(), time(6, 0), tzinfo=IST)
    if now >= cutoff:
        cutoff += timedelta(days=1)
    return cutoff


def is_cached_token_valid(*, now: datetime | None = None) -> bool:
    if not TOKEN_FILE.exists():
        return False
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    token = (data.get("access_token") or "").strip()
    if not token:
        return False
    expires_at = data.get("expires_at")
    if not expires_at:
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=IST)
    except ValueError:
        return False
    return datetime.now(IST) < expiry


def load_cached_token() -> str:
    if not is_cached_token_valid():
        return ""
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return (data.get("access_token") or "").strip()
    except (json.JSONDecodeError, OSError):
        return ""


def save_cached_token(access_token: str, *, user_id: str = "") -> dict[str, Any]:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    expires_at = _token_expiry_ist()
    payload = {
        "access_token": access_token,
        "user_id": user_id,
        "saved_at": datetime.now(IST).isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return payload


def _extract_request_token(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)
    token = (query.get("request_token") or [""])[0]
    if token:
        return token
    match = re.search(r"request_token=([^&]+)", redirect_url)
    if match:
        return match.group(1)
    raise KiteAutoLoginError(f"No request_token in redirect: {redirect_url[:120]}")


def login_with_totp(
    *,
    user_id: str | None = None,
    password: str | None = None,
    totp_secret: str | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Perform headless Kite login and return session data including access_token.

    Credentials default to environment variables:
    ZERODHA_USER_ID, ZERODHA_PASSWORD, ZERODHA_TOTP_SECRET, KITE_API_KEY, KITE_API_SECRET
    """
    settings.load_settings()

    user_id = (user_id or settings.zerodha_user_id()).strip()
    password = password or settings.zerodha_password()
    totp_secret = (totp_secret or settings.zerodha_totp_secret()).strip()
    api_key = (api_key or settings.kite_api_key()).strip()
    api_secret = api_secret or settings.kite_api_secret()

    if not all([user_id, password, totp_secret, api_key, api_secret]):
        raise KiteAutoLoginError(
            "Missing credentials. Set ZERODHA_USER_ID, ZERODHA_PASSWORD, "
            "ZERODHA_TOTP_SECRET, KITE_API_KEY, and KITE_API_SECRET in .env"
        )

    if not force and is_cached_token_valid():
        cached = load_cached_token()
        return {
            "access_token": cached,
            "cached": True,
            "expires_at": json.loads(TOKEN_FILE.read_text(encoding="utf-8")).get("expires_at"),
        }

    try:
        import pyotp
    except ImportError as exc:
        raise KiteAutoLoginError("Install pyotp: pip install pyotp") from exc

    session = requests.Session()
    session.headers.update({"User-Agent": "BharatScout/1.0"})

    login_resp = session.post(
        KITE_LOGIN_URL,
        data={"user_id": user_id, "password": password},
        timeout=30,
    )
    login_resp.raise_for_status()
    login_data = login_resp.json()
    if login_data.get("status") != "success":
        raise KiteAutoLoginError(f"Login failed: {login_data.get('message', login_data)}")

    request_id = login_data["data"]["request_id"]
    totp_code = pyotp.TOTP(totp_secret).now()

    twofa_resp = session.post(
        KITE_TWOFA_URL,
        data={
            "user_id": user_id,
            "request_id": request_id,
            "twofa_value": totp_code,
            "twofa_type": "totp",
        },
        timeout=30,
    )
    twofa_resp.raise_for_status()
    twofa_data = twofa_resp.json()
    if twofa_data.get("status") != "success":
        raise KiteAutoLoginError(f"2FA failed: {twofa_data.get('message', twofa_data)}")

    redirect_url = twofa_data["data"].get("redirect_url") or ""
    request_token = _extract_request_token(redirect_url)

    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=api_key)
    session_data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = session_data["access_token"]

    cache = save_cached_token(access_token, user_id=user_id)
    _update_env_access_token(access_token)

    return {
        "access_token": access_token,
        "user_id": session_data.get("user_id", user_id),
        "cached": False,
        "expires_at": cache["expires_at"],
    }


def _update_env_access_token(access_token: str) -> None:
    """Keep .env KITE_ACCESS_TOKEN in sync for tools that read env directly."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("KITE_ACCESS_TOKEN="):
            out.append(f"KITE_ACCESS_TOKEN={access_token}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"KITE_ACCESS_TOKEN={access_token}")
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def ensure_kite_token(*, force: bool = False) -> str:
    """Return a valid access token, refreshing via TOTP when needed."""
    settings.load_settings()
    if not force:
        env_token = settings.kite_access_token_from_env()
        if env_token and is_cached_token_valid() and load_cached_token() == env_token:
            return env_token
        cached = load_cached_token()
        if cached:
            return cached
    result = login_with_totp(force=force)
    return result["access_token"]
