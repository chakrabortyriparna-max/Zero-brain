"""Tests for .claude/scripts/memory_reflect.py."""
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from memory_reflect import MemoryReflect  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def reflector(tmp_path: Path):
    with patch("memory_reflect.MEMORY_MD", tmp_path / "MEMORY.md"):
        with patch("memory_reflect.HABITS_MD", tmp_path / "HABITS.md"):
            with patch("memory_reflect.DAILY_DIR", tmp_path / "daily"):
                yield MemoryReflect(dry_run=True)


class TestExtractItems:
    def test_explicit_tags(self, reflector: MemoryReflect):
        log = (
            "Some conversation\n"
            "**Decision:** We will use SQLite.\n"
            "**Lesson:** Claude Code transcript entries nest content.\n"
            "**Key Fact:** The PreCompact hook fires automatically.\n"
            "**Action Item:** Riparna to test the flush script.\n"
        )
        items = reflector.extract_items(log)
        assert "We will use SQLite." in items["Decisions"]
        assert "Claude Code transcript entries nest content." in items["Lessons"]
        assert "The PreCompact hook fires automatically." in items["Key Facts"]
        assert "Riparna to test the flush script." in items["Action Items"]

    def test_section_blocks(self, reflector: MemoryReflect):
        log = (
            "### Decisions\n"
            "- Chose PostgreSQL for VPS\n"
            "- Keep SQLite for local\n"
            "\n### Lessons\n"
            "- FastEmbed caches at ~/.cache/fastembed\n"
        )
        items = reflector.extract_items(log)
        assert "Chose PostgreSQL for VPS" in items["Decisions"]
        assert "Keep SQLite for local" in items["Decisions"]
        assert "FastEmbed caches at ~/.cache/fastembed" in items["Lessons"]

    def test_no_items(self, reflector: MemoryReflect):
        items = reflector.extract_items("Just a plain log with nothing special.")
        assert all(len(v) == 0 for v in items.values())


class TestMemoryUpdates:
    def test_append_to_section(self, reflector: MemoryReflect):
        content = "## Key Decisions\n\n## Lessons Learned\n"
        updated = reflector._append_to_section(content, "Key Decisions", ["Use SQLite"])
        assert "- Use SQLite" in updated
        assert "## Key Decisions\n- Use SQLite" in updated

    def test_append_to_missing_section(self, reflector: MemoryReflect):
        content = "## Lessons Learned\n"
        updated = reflector._append_to_section(content, "Key Decisions", ["Use SQLite"])
        assert "Use SQLite" not in updated  # section missing, no-op

    def test_update_projects_table(self, reflector: MemoryReflect):
        content = "## Active Projects\n| Project | Status |\n| Second Brain | In Progress |\n"
        updated = reflector._update_projects_table(content, {"Second Brain": "Done"})
        assert "| Second Brain | Done |" in updated


class TestHabitsArchive:
    def test_archive_and_reset(self, reflector: MemoryReflect):
        habits = (
            "# Daily Habits — 2026-05-16\n"
            "## Pillars\n"
            "- [x] **Main Project**\n"
            "- [ ] **Community**\n"
            "- [ ] **Relationships**\n"
            "## History\n"
        )
        memory_reflect_module = sys.modules["memory_reflect"]
        habits_path = memory_reflect_module.HABITS_MD
        habits_path.write_text(habits, encoding="utf-8")

        reflector.archive_habits("2026-05-16")

        content = habits_path.read_text(encoding="utf-8")
        # Check archive
        assert "### 2026-05-16" in content
        assert "✅ Main Project" in content
        assert "❌ Community" in content
        # Check reset
        assert "- [ ] **Main Project**" in content
        assert "- [ ] **Community**" in content

    def test_date_update(self, reflector: MemoryReflect):
        habits = "# Daily Habits — 2026-05-16\n## Pillars\n- [ ] **Main Project**\n## History\n"
        memory_reflect_module = sys.modules["memory_reflect"]
        habits_path = memory_reflect_module.HABITS_MD
        habits_path.write_text(habits, encoding="utf-8")

        reflector.archive_habits("2026-05-16")

        content = habits_path.read_text(encoding="utf-8")
        today = datetime.now(IST).strftime("%Y-%m-%d")
        assert f"# Daily Habits — {today}" in content


class TestParsePromotionJson:
    def test_valid_json(self, reflector: MemoryReflect):
        text = '{"promote_decisions":["D1"], "promote_lessons":["L1"], "promote_facts":["F1"], "update_projects":{}}'
        result = reflector._parse_promotion_json(text)
        assert result["promote_decisions"] == ["D1"]
        assert result["promote_lessons"] == ["L1"]

    def test_with_markdown_fences(self, reflector: MemoryReflect):
        text = '```json\n{"promote_decisions":["D1"], "promote_lessons":[], "promote_facts":[], "update_projects":{}}\n```'
        result = reflector._parse_promotion_json(text)
        assert result["promote_decisions"] == ["D1"]

    def test_invalid_json_fallback(self, reflector: MemoryReflect):
        result = reflector._parse_promotion_json("not json")
        assert result == {"promote_decisions": [], "promote_lessons": [], "promote_facts": [], "update_projects": {}}
