"""pytest configuration — add .claude/scripts and .claude/hooks to import path."""

import sys
import shutil
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


@pytest.fixture
def isolated_project(tmp_path):
    """Create a temporary isolated copy of the project for hook testing."""
    project = tmp_path / "project"
    hooks_dir = project / ".claude" / "hooks"
    memory_dir = project / "Memory"
    daily_dir = memory_dir / "daily"

    hooks_dir.mkdir(parents=True)
    daily_dir.mkdir(parents=True)

    for f in HOOKS_DIR.glob("*.py"):
        shutil.copy(f, hooks_dir)

    (memory_dir / "SOUL.md").write_text("# SOUL\nTest soul\n", encoding="utf-8")
    (memory_dir / "USER.md").write_text("# USER\nTest user\n", encoding="utf-8")
    (memory_dir / "MEMORY.md").write_text("# MEMORY\nTest memory\n", encoding="utf-8")
    return project
