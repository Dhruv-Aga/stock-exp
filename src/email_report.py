"""Send analysis reports via email (SMTP)."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("EMAIL_FROM", os.environ.get("SMTP_USER", "")),
        "to_addr": os.environ.get("EMAIL_TO", ""),
    }


def email_configured() -> bool:
    cfg = _smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"] and cfg["to_addr"])


def send_report(subject: str, body: str, *, html: str | None = None) -> str:
    cfg = _smtp_config()
    missing = [
        k
        for k, v in {
            "SMTP_HOST": cfg["host"],
            "SMTP_USER": cfg["user"],
            "SMTP_PASSWORD": cfg["password"],
            "EMAIL_TO": cfg["to_addr"],
        }.items()
        if not v
    ]
    if missing:
        raise ValueError(
            "Email not configured. Set environment variables: "
            + ", ".join(missing)
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = cfg["to_addr"]
    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["from_addr"], [cfg["to_addr"]], msg.as_string())

    return f"Report emailed to {cfg['to_addr']}"


def load_env_file(path: Path | None = None) -> None:
    """Load key=value pairs from .env into os.environ (simple parser)."""
    env_path = path or Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
