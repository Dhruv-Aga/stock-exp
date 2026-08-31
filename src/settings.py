"""Runtime settings loaded from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from src.email_report import load_env_file

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "trading.db"


def _bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def _float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def load_settings() -> None:
    load_env_file()


def kite_configured() -> bool:
    return bool(kite_api_key() and kite_api_secret() and kite_access_token())


def kite_api_key() -> str:
    return os.environ.get("KITE_API_KEY", "").strip()


def kite_api_secret() -> str:
    return os.environ.get("KITE_API_SECRET", "").strip()


def kite_access_token() -> str:
    return os.environ.get("KITE_ACCESS_TOKEN", "").strip()


def live_trading_enabled() -> bool:
    return _bool("LIVE_TRADING", False)


def dry_run_mode() -> bool:
    return not live_trading_enabled()


def max_daily_loss() -> float:
    return _float("MAX_DAILY_LOSS", 2000.0)


def kill_switch_enabled() -> bool:
    return _bool("KILL_SWITCH", False)


def cash_only_mode() -> bool:
    """Cash/equity only - no F&O shorts."""
    return _bool("CASH_ONLY", True)


def order_tag() -> str:
    return os.environ.get("ORDER_TAG", "india-bot")[:20]


def groq_api_key() -> str:
    return os.environ.get("GROQ_API_KEY", "").strip()


def groq_model() -> str:
    raw = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    if raw.startswith("groq/"):
        return raw.split("/", 1)[1]
    return raw


def llm_risk_governor_enabled() -> bool:
    return _bool("LLM_RISK_GOVERNOR", True)


def require_trade_approval() -> bool:
    """When True, live trades require explicit user approval before Kite execution."""
    return _bool("REQUIRE_TRADE_APPROVAL", True)


def shadow_proposals_enabled() -> bool:
    """When True, paper sessions create shadow proposals for live review."""
    return _bool("SHADOW_LIVE_PROPOSALS", True)
