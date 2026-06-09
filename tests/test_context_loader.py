"""Tests for .claude/chat/context_loader.py."""
import sys
import tempfile
from pathlib import Path

import pytest

CHAT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "chat"
sys.path.insert(0, str(CHAT_DIR))

import context_loader as loader  # noqa: E402


@pytest.fixture(autouse=True)
def patch_project_root(monkeypatch):
    """Route context_loader to a temporary Memory directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_dir = Path(tmpdir) / "Memory"
        memory_dir.mkdir()
        monkeypatch.setattr(loader, "MEMORY_DIR", memory_dir)
        yield memory_dir


def _write(memory_dir, filename, content):
    (memory_dir / filename).write_text(content, encoding="utf-8")


class TestLoadCoreContext:
    def test_loads_all_three(self, patch_project_root):
        _write(patch_project_root, "SOUL.md", "# SOUL\nBe helpful.")
        _write(patch_project_root, "USER.md", "# USER\nRiparna.")
        _write(patch_project_root, "MEMORY.md", "# MEMORY\nActive project.")
        ctx = loader.load_core_context()
        assert "Agent Identity" in ctx
        assert "Be helpful" in ctx
        assert "Riparna" in ctx
        assert "Active project" in ctx

    def test_missing_files_graceful(self, patch_project_root):
        ctx = loader.load_core_context()
        assert ctx == ""


class TestLoadDailyLogs:
    def test_loads_recent_logs(self, patch_project_root):
        daily = patch_project_root / "daily"
        daily.mkdir()
        (daily / "2026-05-18.md").write_text("Day 1")
        (daily / "2026-05-19.md").write_text("Day 2")
        (daily / "2026-05-20.md").write_text("Day 3")
        logs = loader.load_daily_logs(n=2)
        assert "Day 3" in logs
        assert "Day 2" in logs
        assert "Day 1" not in logs

    def test_no_daily_dir(self, patch_project_root):
        assert loader.load_daily_logs() == ""


class TestBuildSystemPrompt:
    def test_includes_all_parts(self, patch_project_root):
        _write(patch_project_root, "SOUL.md", "SOUL content")
        daily = patch_project_root / "daily"
        daily.mkdir()
        (daily / "2026-05-20.md").write_text("Today")
        prompt = loader.build_system_prompt(include_daily_logs=True)
        assert "SOUL content" in prompt
        assert "Today" in prompt

    def test_without_daily_logs(self, patch_project_root):
        _write(patch_project_root, "SOUL.md", "SOUL content")
        prompt = loader.build_system_prompt(include_daily_logs=False)
        assert "SOUL content" in prompt
        assert "Recent Daily Logs" not in prompt
