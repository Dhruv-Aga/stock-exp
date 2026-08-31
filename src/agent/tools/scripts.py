"""Sandboxed Python and Node script runner."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SANDBOX = ROOT / "scripts" / "sandbox"
MAX_OUTPUT = 50_000
TIMEOUT_SEC = 30


def _resolve_script(filename: str) -> Path:
    if not filename or ".." in filename or filename.startswith("/"):
        raise ValueError("Invalid script filename")

    script = (SANDBOX / filename).resolve()
    if not script.is_relative_to(SANDBOX.resolve()):
        raise ValueError("Script must be inside scripts/sandbox/")
    if not script.exists():
        raise FileNotFoundError(f"Script not found: {filename} (place files in scripts/sandbox/)")
    return script


def _run_command(cmd: list[str]) -> dict[str, Any]:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        cwd=str(SANDBOX),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SEC,
        env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
    )
    stdout = (proc.stdout or "")[:MAX_OUTPUT]
    stderr = (proc.stderr or "")[:MAX_OUTPUT]
    return {
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "command": " ".join(cmd),
    }


def run_python_script(args: dict[str, Any]) -> dict[str, Any]:
    script = _resolve_script(args["filename"])
    if script.suffix != ".py":
        raise ValueError("Python runner requires a .py file")

    cmd = [sys.executable, str(script.name)]
    extra = args.get("args") or []
    if extra:
        cmd.extend(str(a) for a in extra)
    return _run_command(cmd)


def run_node_script(args: dict[str, Any]) -> dict[str, Any]:
    script = _resolve_script(args["filename"])
    if script.suffix != ".js":
        raise ValueError("Node runner requires a .js file")

    cmd = ["node", str(script.name)]
    extra = args.get("args") or []
    if extra:
        cmd.extend(str(a) for a in extra)
    return _run_command(cmd)
