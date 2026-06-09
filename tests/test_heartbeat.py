"""Tests for .claude/scripts/heartbeat.py."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from heartbeat import HeartbeatRunner, Snapshot  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def runner(tmp_path: Path):
    # Patch all paths to use temp dirs
    with patch("heartbeat.STATE_FILE", tmp_path / "state.json"):
        with patch("heartbeat.DAILY_DIR", tmp_path / "daily"):
            with patch("heartbeat.DRAFTS_ACTIVE", tmp_path / "active"):
                with patch("heartbeat.DRAFTS_EXPIRED", tmp_path / "expired"):
                    with patch("heartbeat.HABITS_MD", tmp_path / "HABITS.md"):
                        yield HeartbeatRunner(dry_run=True)


class TestSnapshot:
    def test_to_dict_roundtrip(self):
        s = Snapshot(
            timestamp="2026-05-17T10:00:00+05:30",
            gmail_unread=[{"id": "1", "subject": "Test"}],
            github_notifications=[{"id": "n1", "title": "Issue"}],
            slack_activity={"general": [{"ts": "123", "text": "hi"}]},
            github_commits={"repo": [{"sha": "abc", "message": "fix"}]},
            habits_status={"Main Project": True},
        )
        d = s.to_dict()
        restored = Snapshot.from_dict(d)
        assert restored.timestamp == s.timestamp
        assert restored.gmail_unread == s.gmail_unread


class TestDiff:
    def test_no_changes(self, runner: HeartbeatRunner):
        prev = Snapshot(timestamp="", gmail_unread=[{"id": "1"}])
        curr = Snapshot(timestamp="", gmail_unread=[{"id": "1"}])
        diff = runner.compute_diff(prev, curr)
        assert not diff["has_changes"]
        assert len(diff["new_gmail"]) == 0

    def test_new_email(self, runner: HeartbeatRunner):
        prev = Snapshot(timestamp="", gmail_unread=[{"id": "1"}])
        curr = Snapshot(timestamp="", gmail_unread=[{"id": "1"}, {"id": "2"}])
        diff = runner.compute_diff(prev, curr)
        assert diff["has_changes"]
        assert len(diff["new_gmail"]) == 1
        assert diff["new_gmail"][0]["id"] == "2"

    def test_new_github_notification(self, runner: HeartbeatRunner):
        prev = Snapshot(timestamp="", github_notifications=[{"id": "n1"}])
        curr = Snapshot(timestamp="", github_notifications=[{"id": "n1"}, {"id": "n2"}])
        diff = runner.compute_diff(prev, curr)
        assert diff["has_changes"]
        assert len(diff["new_github"]) == 1

    def test_new_slack_message(self, runner: HeartbeatRunner):
        prev = Snapshot(timestamp="", slack_activity={"general": [{"ts": "1"}]})
        curr = Snapshot(timestamp="", slack_activity={"general": [{"ts": "1"}, {"ts": "2"}]})
        diff = runner.compute_diff(prev, curr)
        assert diff["has_changes"]
        assert len(diff["new_slack"]["general"]) == 1


class TestHabitDetection:
    def test_main_project_detected(self, runner: HeartbeatRunner):
        today = datetime.now(IST).strftime("%Y-%m-%d")
        snapshot = Snapshot(
            timestamp="",
            github_commits={"repo": [{"sha": "abc", "date": f"{today}T10:00:00Z"}]},
        )
        habits = runner.detect_habits(snapshot)
        assert habits["Main Project"] is True

    def test_main_project_not_detected(self, runner: HeartbeatRunner):
        snapshot = Snapshot(timestamp="", github_commits={})
        habits = runner.detect_habits(snapshot)
        assert habits["Main Project"] is False

    def test_community_detected(self, runner: HeartbeatRunner):
        with patch("heartbeat.SLACK_USER_ID", "U123"):
            snapshot = Snapshot(
                timestamp="",
                slack_activity={"general": [{"ts": "1", "user": "U123", "text": "hi"}]},
            )
            habits = runner.detect_habits(snapshot)
            assert habits["Community"] is True

    def test_community_not_detected(self, runner: HeartbeatRunner):
        snapshot = Snapshot(timestamp="", slack_activity={})
        habits = runner.detect_habits(snapshot)
        assert habits["Community"] is False


class TestStateIO:
    def test_save_and_load(self, runner: HeartbeatRunner):
        runner.dry_run = False
        s = Snapshot(timestamp="2026-05-17T10:00:00+05:30", gmail_unread=[{"id": "a"}])
        runner._save_state(s)
        loaded = runner._load_state()
        assert loaded.timestamp == s.timestamp
        assert loaded.gmail_unread == s.gmail_unread


class TestDailyLog:
    def test_ensure_daily_file(self, runner: HeartbeatRunner):
        path = runner._ensure_daily_file("2026-05-17")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Daily Log — 2026-05-17" in content
        assert "IST" in content


class TestDraftPersistence:
    def test_save_email_drafts(self, runner: HeartbeatRunner):
        runner.dry_run = False
        drafts = [
            {
                "recipient": "alice@example.com",
                "subject": "Re: Hello",
                "body": "Thanks for reaching out.",
                "source_id": "msg123",
            }
        ]
        saved = runner._save_email_drafts(drafts)
        assert len(saved) == 1
        assert saved[0].exists()
        content = saved[0].read_text(encoding="utf-8")
        assert "type: email" in content
        assert "alice@example.com" in content
        assert "Thanks for reaching out." in content

    def test_deduplicate_by_source_id(self, runner: HeartbeatRunner):
        runner.dry_run = False
        drafts = [
            {
                "recipient": "alice@example.com",
                "subject": "Re: Hello",
                "body": "Thanks.",
                "source_id": "msg123",
            }
        ]
        saved1 = runner._save_email_drafts(drafts)
        saved2 = runner._save_email_drafts(drafts)
        # Second call should skip existing draft with same source_id
        assert len(saved2) == 0

    def test_expire_old_drafts(self, runner: HeartbeatRunner):
        from heartbeat import DRAFTS_ACTIVE, DRAFTS_EXPIRED
        runner.dry_run = False
        old = DRAFTS_ACTIVE / "old_draft.md"
        DRAFTS_ACTIVE.mkdir(parents=True, exist_ok=True)
        old.write_text("old", encoding="utf-8")
        import time
        old_time = time.time() - (25 * 3600)
        os.utime(old, (old_time, old_time))
        moved = runner._expire_old_drafts()
        assert len(moved) == 1
        assert not old.exists()
        assert moved[0].exists()


class TestKeywordFallback:
    def test_keyword_flag_urgent(self, runner: HeartbeatRunner):
        emails = [
            {"subject": "Urgent: need reply", "from_addr": "boss@corp.com", "snippet": "urgent"},
            {"subject": "Lunch?", "from_addr": "friend@example.com", "snippet": "hi"},
        ]
        flags = runner._keyword_flag_emails(emails)
        assert len(flags) == 1
        assert "Urgent" in flags[0]

    def test_keyword_no_match(self, runner: HeartbeatRunner):
        emails = [{"subject": "Lunch?", "from_addr": "a@b.com", "snippet": "hi"}]
        flags = runner._keyword_flag_emails(emails)
        assert len(flags) == 0


class TestConfig:
    def test_config_loading(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "heartbeat.json"
            config_path.write_text(json.dumps({"enable_drafting": True, "draft_expiry_hours": 48}), encoding="utf-8")
            with patch("heartbeat.CONFIG_FILE", config_path):
                with patch("heartbeat.LLMClient"):
                    runner = HeartbeatRunner()
                    assert runner.config["enable_drafting"] is True
                    assert runner.config["draft_expiry_hours"] == 48
                    assert runner.use_llm is True


class TestErrorAggregation:
    def test_error_recording(self, runner: HeartbeatRunner):
        runner.errors.clear()
        runner._error("Test error")
        assert len(runner.errors) == 1
        assert "Test error" in runner.errors[0]


# Allow patching os.utime in tests
import os  # noqa: E402
