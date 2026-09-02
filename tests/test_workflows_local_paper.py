"""Ensure paper trading is never invoked from GitHub Actions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# Commands / modules that run a paper session or refresh paper state.
PAPER_SESSION_MARKERS = (
    "run_paper.py",
    "run_daily_report.py",
    "run_weekly_paper.py",
    "generate_dashboard.py",
    "paper_trader",
    "run_paper_session",
    "dev.sh paper",
    "dev.ps1 paper",
)


def _executable_workflow_text(text: str) -> str:
    """Drop YAML comments so docs about local paper runs are not treated as jobs."""
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            line = line[: line.index("#")]
        lines.append(line)
    return "\n".join(lines)


def test_daily_report_workflow_removed():
    assert not (WORKFLOWS / "daily-report.yml").exists()


def test_pages_workflow_is_static_only():
    pages = _executable_workflow_text(
        (WORKFLOWS / "pages.yml").read_text(encoding="utf-8")
    )
    assert "deploy-pages" in pages
    for marker in PAPER_SESSION_MARKERS:
        assert marker not in pages, f"pages.yml must not run paper trading ({marker})"


def test_no_workflow_runs_paper_trading():
    yaml_files = list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml"))
    assert yaml_files, "expected at least one GitHub workflow"
    offenders = []
    for path in yaml_files:
        text = _executable_workflow_text(path.read_text(encoding="utf-8"))
        for marker in PAPER_SESSION_MARKERS:
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, (
        "Paper trading must run locally only, not in GitHub Actions: "
        + ", ".join(offenders)
    )
