"""Lifecycle integration tests for hooks."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestSessionStart:
    def test_outputs_context(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        assert "# Session Context" in result.stdout
        assert "## SOUL" in result.stdout
        assert "## USER" in result.stdout
        assert "## MEMORY" in result.stdout
        assert "## Recent Daily Logs" in result.stdout

    def test_creates_daily_file(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"
        assert not daily.exists()

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        assert daily.exists()
        content = daily.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "date:" in content
        assert "# Daily Log" in content

    def test_appends_marker(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        content = daily.read_text(encoding="utf-8")
        assert content.count("## Session Start") == 2

    def test_loads_recent_daily_logs(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        daily_dir = isolated_project / "Memory" / "daily"

        # Create 5 daily logs
        for i in range(5):
            date = f"2024-01-{i+1:02d}"
            (daily_dir / f"{date}.md").write_text(
                f"---\ndate: {date}\n---\n\n# Daily Log — {date}\n\nContent {i}.\n",
                encoding="utf-8",
            )

        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        # Should load last 3: 01-03, 01-04, 01-05
        assert "Content 4." in result.stdout
        assert "Content 3." in result.stdout
        assert "Content 2." in result.stdout
        assert "Content 1." not in result.stdout


class TestPreCompact:
    def test_extracts_insights(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        transcript = [
            {"role": "assistant", "content": "I decided to use PostgreSQL."},
            {"role": "assistant", "content": "action item: review the schema."},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "src/models.py"}}
                ],
            },
        ]
        result = subprocess.run(
            [sys.executable, str(hooks / "pre-compact-flush.py")],
            input="\n".join(json.dumps(e) for e in transcript),
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        content = daily.read_text(encoding="utf-8")
        assert "## Pre-Compact Flush" in content
        assert "### Decisions" in content
        assert "- use PostgreSQL" in content
        assert "### Action Items" in content
        assert "- review the schema" in content
        assert "### File Changes" in content
        assert "- Edited code: src/models.py" in content

    def test_empty_stdin(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"
        initial = daily.read_text(encoding="utf-8") if daily.exists() else ""

        result = subprocess.run(
            [sys.executable, str(hooks / "pre-compact-flush.py")],
            input="",
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        if daily.exists():
            assert daily.read_text(encoding="utf-8") == initial

    def test_malformed_jsonl(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        bad_input = (
            "not json\n"
            '{"role": "assistant", "content": "I decided to use Redis."}\n'
            "{bad json\n"
        )
        result = subprocess.run(
            [sys.executable, str(hooks / "pre-compact-flush.py")],
            input=bad_input,
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        content = daily.read_text(encoding="utf-8")
        assert "### Decisions" in content
        assert "- use Redis" in content


class TestSessionEnd:
    def test_extracts_insights(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        transcript = [
            {"role": "assistant", "content": "lesson learned: always test before pushing."},
        ]
        result = subprocess.run(
            [sys.executable, str(hooks / "session-end-flush.py")],
            input="\n".join(json.dumps(e) for e in transcript),
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        content = daily.read_text(encoding="utf-8")
        assert "## Session End" in content
        assert "### Lessons" in content
        assert "- always test before pushing" in content

    def test_empty_stdin(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        result = subprocess.run(
            [sys.executable, str(hooks / "session-end-flush.py")],
            input="",
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0


class TestCrossSessionLinkage:
    def test_round_trip(self, isolated_project):
        """Prove that SessionStart loads what PreCompact and SessionEnd saved."""
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")

        # --- Session 1: Work + PreCompact ---
        transcript = [
            {"role": "assistant", "content": "I decided to adopt async SQLAlchemy."},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "TaskCreate",
                        "input": {"subject": "Migrate to async"},
                    }
                ],
            },
        ]
        result = subprocess.run(
            [sys.executable, str(hooks / "pre-compact-flush.py")],
            input="\n".join(json.dumps(e) for e in transcript),
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0

        # --- Session 1: End ---
        transcript = [
            {"role": "assistant", "content": "lesson learned: benchmark before migration."}
        ]
        result = subprocess.run(
            [sys.executable, str(hooks / "session-end-flush.py")],
            input="\n".join(json.dumps(e) for e in transcript),
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0

        # --- Session 2: Start (loads history) ---
        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        stdout = result.stdout

        assert "### Decisions" in stdout
        assert "- adopt async SQLAlchemy" in stdout
        assert "### Tasks" in stdout
        assert "- Created task: Migrate to async" in stdout
        assert "### Lessons" in stdout
        assert "- benchmark before migration" in stdout

    def test_daily_file_mkdir_bug_fixed(self, isolated_project):
        """Regression: ensure_daily_file used to fail if Memory/daily/ was missing."""
        hooks = isolated_project / ".claude" / "hooks"
        daily_dir = isolated_project / "Memory" / "daily"
        import shutil
        shutil.rmtree(daily_dir)
        assert not daily_dir.exists()

        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        assert daily_dir.exists()
