"""Tests for .claude/chat/bot.py."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CHAT_DIR = Path(__file__).resolve().parent.parent / ".claude" / "chat"
sys.path.insert(0, str(CHAT_DIR))

# Must patch env *before* bot imports App
with patch.dict(
    os.environ,
    {
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_APP_TOKEN": "xapp-test",
        "GROQ_API_KEY": "dummy",
    },
):
    import bot  # noqa: E402


@pytest.fixture(autouse=True)
def reset_bot_user_id(monkeypatch):
    monkeypatch.setattr(bot, "BOT_USER_ID", "U_BOT")
    yield


class TestIsDuplicate:
    def test_first_time_false(self):
        bot._recently_processed.clear()
        assert bot._is_duplicate("123") is False

    def test_second_time_true(self):
        bot._recently_processed.clear()
        bot._is_duplicate("123")
        assert bot._is_duplicate("123") is True

    def test_different_ts_false(self):
        bot._recently_processed.clear()
        bot._is_duplicate("123")
        assert bot._is_duplicate("456") is False


class TestResolveSessionAndThread:
    def test_dm(self):
        event = {"channel_type": "im", "channel": "D1", "ts": "123"}
        sid, thread_ts = bot._resolve_session_and_thread(event)
        assert sid == "D1"
        assert thread_ts is None

    def test_channel_first_mention(self):
        event = {"channel_type": "channel", "ts": "123"}
        sid, thread_ts = bot._resolve_session_and_thread(event)
        assert sid == "123"
        assert thread_ts == "123"

    def test_channel_thread_reply(self):
        event = {"channel_type": "channel", "ts": "124", "thread_ts": "123"}
        sid, thread_ts = bot._resolve_session_and_thread(event)
        assert sid == "123"
        assert thread_ts == "123"


class TestProcessMessage:
    @patch.object(bot, "llm")
    @patch.object(bot, "store")
    @patch("bot.build_system_prompt", return_value="system prompt")
    def test_new_session_injects_context(self, mock_build, mock_store, mock_llm):
        mock_session = MagicMock()
        mock_session.is_new = True
        mock_store.get_or_create.return_value = mock_session
        mock_store.get_pruned_messages.return_value = [{"role": "user", "content": "hi"}]
        mock_store.get_system_prompt.return_value = "system prompt"
        mock_llm.chat.return_value = "hello!"

        say = MagicMock()
        bot._process_message("sid", "C1", "U1", "hi", say, thread_ts="123")

        mock_store.get_or_create.assert_called_once_with("sid", "C1", "U1")
        mock_build.assert_called_once()
        mock_store.set_system_prompt.assert_called_once_with("sid", "system prompt")
        mock_store.append_message.assert_any_call("sid", "user", "hi")
        mock_store.append_message.assert_any_call("sid", "assistant", "hello!")
        say.assert_called_once_with(text="hello!", thread_ts="123")

    @patch.object(bot, "llm")
    @patch.object(bot, "store")
    def test_existing_session_no_context_injection(self, mock_store, mock_llm):
        mock_session = MagicMock()
        mock_session.is_new = False
        mock_store.get_or_create.return_value = mock_session
        mock_store.get_pruned_messages.return_value = [{"role": "user", "content": "hi"}]
        mock_store.get_system_prompt.return_value = "existing prompt"
        mock_llm.chat.return_value = "hello!"

        say = MagicMock()
        bot._process_message("sid", "C1", "U1", "hi", say)

        mock_store.set_system_prompt.assert_not_called()
        mock_llm.chat.assert_called_once_with(
            [{"role": "user", "content": "hi"}],
            system="existing prompt",
            max_tokens=2048,
        )

    @patch.object(bot, "llm")
    @patch.object(bot, "store")
    def test_llm_error_sends_sorry(self, mock_store, mock_llm):
        mock_session = MagicMock()
        mock_session.is_new = False
        mock_store.get_or_create.return_value = mock_session
        mock_store.get_pruned_messages.return_value = []
        mock_store.get_system_prompt.return_value = None
        mock_llm.chat.side_effect = RuntimeError("API down")

        say = MagicMock()
        bot._process_message("sid", "C1", "U1", "hi", say, thread_ts="123")

        say.assert_called_once_with(
            text="Sorry, I ran into an error processing your message. Please try again.",
            thread_ts="123",
        )
