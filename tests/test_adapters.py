"""Tests for .claude/chat/adapters.py."""
import sys
from pathlib import Path

import pytest

CHAT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "chat"
sys.path.insert(0, str(CHAT_DIR))

from adapters import SlackAdapter, contains_mention, is_bot_message

BOT_ID = "U123"


@pytest.fixture
def adapter():
    return SlackAdapter()


class TestIsBotMessage:
    def test_bot_subtype(self):
        event = {"subtype": "bot_message", "user": "U999"}
        assert is_bot_message(event, BOT_ID) is True

    def test_bot_user(self):
        event = {"user": BOT_ID, "text": "hello"}
        assert is_bot_message(event, BOT_ID) is True

    def test_human_user(self):
        event = {"user": "U999", "text": "hello"}
        assert is_bot_message(event, BOT_ID) is False


class TestContainsMention:
    def test_has_mention(self):
        assert contains_mention(f"Hey <@{BOT_ID}> help", BOT_ID) is True

    def test_no_mention(self):
        assert contains_mention("Hello world", BOT_ID) is False


class TestSlackAdapter:
    def test_dm_should_respond(self, adapter):
        event = {
            "type": "message",
            "channel": "D1",
            "channel_type": "im",
            "user": "U999",
            "text": "hello",
            "ts": "123",
        }
        assert adapter.should_respond(event, BOT_ID) is True

    def test_dm_bot_message_should_not_respond(self, adapter):
        event = {
            "type": "message",
            "channel": "D1",
            "channel_type": "im",
            "subtype": "bot_message",
            "text": "auto",
            "ts": "123",
        }
        assert adapter.should_respond(event, BOT_ID) is False

    def test_channel_mention_should_respond(self, adapter):
        event = {
            "type": "message",
            "channel": "C1",
            "channel_type": "channel",
            "user": "U999",
            "text": f"<@{BOT_ID}> hello",
            "ts": "123",
        }
        assert adapter.should_respond(event, BOT_ID) is True

    def test_channel_no_mention_should_not_respond(self, adapter):
        event = {
            "type": "message",
            "channel": "C1",
            "channel_type": "channel",
            "user": "U999",
            "text": "random chat",
            "ts": "123",
        }
        assert adapter.should_respond(event, BOT_ID) is False

    def test_thread_reply_should_respond(self, adapter):
        event = {
            "type": "message",
            "channel": "C1",
            "channel_type": "channel",
            "user": "U999",
            "text": "thanks!",
            "ts": "124",
            "thread_ts": "123",
        }
        assert adapter.should_respond(event, BOT_ID) is True

    def test_extract_thread_id_uses_thread_ts(self, adapter):
        event = {"ts": "124", "thread_ts": "123"}
        assert adapter.extract_thread_id(event) == "123"

    def test_extract_thread_id_fallback_to_ts(self, adapter):
        event = {"ts": "124"}
        assert adapter.extract_thread_id(event) == "124"

    def test_strip_mention(self, adapter):
        text = f"<@{BOT_ID}> please help"
        assert adapter.strip_bot_mention(text, BOT_ID) == "please help"

    def test_build_reply_payload(self, adapter):
        assert adapter.build_reply_payload("hi") == {"text": "hi"}
        assert adapter.build_reply_payload("hi", thread_ts="123") == {
            "text": "hi",
            "thread_ts": "123",
        }

    def test_extract_fields(self, adapter):
        event = {
            "user": "U999",
            "channel": "C1",
            "text": "hello",
            "channel_type": "channel",
            "ts": "123",
        }
        assert adapter.extract_user_id(event) == "U999"
        assert adapter.extract_channel_id(event) == "C1"
        assert adapter.extract_user_message(event) == "hello"
        assert adapter.extract_channel_type(event) == "channel"
