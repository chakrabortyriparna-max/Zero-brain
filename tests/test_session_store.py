"""Tests for .claude/chat/session_store.py."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CHAT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "chat"
sys.path.insert(0, str(CHAT_DIR))

from session_store import ChatSession, SessionStore

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        yield SessionStore(db_path)


class TestGetOrCreate:
    def test_creates_new_session(self, store):
        session = store.get_or_create("ts1", "C1", "U1")
        assert session.is_new is True
        assert session.thread_ts == "ts1"
        assert session.channel_id == "C1"
        assert session.user_id == "U1"
        assert session.messages == []
        assert session.system_prompt is None

    def test_returns_existing_session(self, store):
        store.get_or_create("ts1", "C1", "U1")
        existing = store.get_or_create("ts1", "C1", "U1")
        assert existing.is_new is False


class TestMessages:
    def test_append_and_get(self, store):
        store.get_or_create("ts1", "C1", "U1")
        store.append_message("ts1", "user", "hello")
        store.append_message("ts1", "assistant", "hi")
        msgs = store.get_messages("ts1")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi"}

    def test_get_messages_unknown_session(self, store):
        assert store.get_messages("unknown") == []

    def test_append_to_unknown_raises(self, store):
        with pytest.raises(KeyError, match="No session found"):
            store.append_message("unknown", "user", "hello")


class TestSystemPrompt:
    def test_set_and_get(self, store):
        store.get_or_create("ts1", "C1", "U1")
        store.set_system_prompt("ts1", "You are helpful.")
        assert store.get_system_prompt("ts1") == "You are helpful."

    def test_get_none(self, store):
        store.get_or_create("ts1", "C1", "U1")
        assert store.get_system_prompt("ts1") is None


class TestListAndPrune:
    def test_list_sessions(self, store):
        store.get_or_create("ts1", "C1", "U1")
        store.get_or_create("ts2", "C2", "U2")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_prune_old(self, store):
        store.get_or_create("ts1", "C1", "U1")
        # Manually age the session
        cutoff = datetime.now(IST) - timedelta(days=60)
        with store._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE thread_ts = ?",
                (cutoff.isoformat(), "ts1"),
            )
        pruned = store.prune_old_sessions(days=30)
        assert pruned == 1
        assert store.get_session("ts1") is None

    def test_prune_nothing_fresh(self, store):
        store.get_or_create("ts1", "C1", "U1")
        assert store.prune_old_sessions(days=30) == 0


class TestClear:
    def test_clear_existing(self, store):
        store.get_or_create("ts1", "C1", "U1")
        store.clear_session("ts1")
        assert store.get_session("ts1") is None


class TestJsonSafety:
    def test_corrupted_messages_json(self, store):
        store.get_or_create("ts1", "C1", "U1")
        # Corrupt the JSON
        with store._connect() as conn:
            conn.execute(
                "UPDATE sessions SET messages_json = ? WHERE thread_ts = ?",
                ("not json", "ts1"),
            )
        session = store.get_session("ts1")
        assert session.messages == []
