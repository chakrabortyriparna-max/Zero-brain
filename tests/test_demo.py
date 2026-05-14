"""Validate demo outputs without requiring a browser."""

import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parents[1] / "demos"


def test_date_demo_runs():
    script = DEMO_DIR / "date_function_demo.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Current IST time" in result.stdout
    assert "2026-05-14" in result.stdout


def test_placeholder_env_exists():
    env_file = DEMO_DIR / "placeholder.env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "ANTHROPIC_API_KEY" in content
    assert "GITHUB_TOKEN" in content
    assert "xoxb-" in content  # Slack bot token placeholder
