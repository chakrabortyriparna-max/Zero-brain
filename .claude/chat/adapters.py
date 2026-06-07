"""Platform adapter layer for normalizing chat platform events.

Phase 7 of the Second Brain project. Provides a common interface over
platform-specific payloads, starting with Slack.
"""

from typing import Optional, Protocol


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_bot_message(event: dict, bot_user_id: str) -> bool:
    """Return True if the event was sent by the bot or is a bot_message subtype."""
    if event.get("subtype") == "bot_message":
        return True
    if event.get("user") == bot_user_id:
        return True
    return False


def contains_mention(text: str, bot_user_id: str) -> bool:
    """Return True if the text contains an @-mention of the bot user."""
    mention = f"<@{bot_user_id}>"
    return mention in text


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class PlatformAdapter(Protocol):
    """Common interface for normalizing platform-specific chat events."""

    def extract_thread_id(self, event: dict) -> str:
        """Return the unique thread identifier for this event."""
        ...

    def extract_user_message(self, event: dict) -> str:
        """Return the text the user sent."""
        ...

    def extract_user_id(self, event: dict) -> str:
        """Return the user's platform ID."""
        ...

    def extract_channel_id(self, event: dict) -> str:
        """Return the channel/conversation ID."""
        ...

    def extract_channel_type(self, event: dict) -> str:
        """Return channel type ('im', 'channel', 'group', etc.)."""
        ...

    def should_respond(self, event: dict, bot_user_id: str) -> bool:
        """Return True if the bot should respond to this event."""
        ...

    def build_reply_payload(self, text: str, thread_ts: Optional[str] = None) -> dict:
        """Build the payload for sending a reply."""
        ...

    def strip_bot_mention(self, text: str, bot_user_id: str) -> str:
        """Remove @bot mention from the beginning of a message."""
        ...


# ---------------------------------------------------------------------------
# SlackAdapter
# ---------------------------------------------------------------------------

class SlackAdapter:
    """Adapter that normalizes Slack message events to the PlatformAdapter interface."""

    # -- Extraction helpers --------------------------------------------------

    def extract_thread_id(self, event: dict) -> str:
        """Use `thread_ts` if present, else fall back to `ts`."""
        return event.get("thread_ts") or event["ts"]

    def extract_user_message(self, event: dict) -> str:
        """Return the raw text of the user's message."""
        return event["text"]

    def extract_user_id(self, event: dict) -> str:
        """Return the Slack user ID."""
        return event["user"]

    def extract_channel_id(self, event: dict) -> str:
        """Return the Slack channel ID."""
        return event["channel"]

    def extract_channel_type(self, event: dict) -> str:
        """Return the channel type (e.g. 'im', 'channel', 'group')."""
        return event.get("channel_type", "unknown")

    # -- Response logic ------------------------------------------------------

    def should_respond(self, event: dict, bot_user_id: str) -> bool:
        """Decide whether the bot should reply to this Slack event.

        Rules:
        - Skip bot messages and messages sent by the bot itself.
        - In DMs (channel_type == "im"): always respond.
        - In public channels / groups: only respond if the message
          @-mentions the bot or is in a thread the bot is already in.
        """
        if is_bot_message(event, bot_user_id):
            return False

        channel_type = self.extract_channel_type(event)
        if channel_type == "im":
            return True

        text = event.get("text", "")
        if contains_mention(text, bot_user_id):
            return True

        # threaded reply where the bot is already participating
        if event.get("thread_ts") is not None:
            return True

        return False

    # -- Reply helpers -------------------------------------------------------

    def build_reply_payload(self, text: str, thread_ts: Optional[str] = None) -> dict:
        """Build a Slack chat.postMessage payload.

        If *thread_ts* is provided, the reply is threaded under that message.
        """
        payload: dict = {"text": text}
        if thread_ts is not None:
            payload["thread_ts"] = thread_ts
        return payload

    def strip_bot_mention(self, text: str, bot_user_id: str) -> str:
        """Remove ``<@BOT_ID>`` from the start of the message and strip whitespace."""
        mention = f"<@{bot_user_id}>"
        if text.startswith(mention):
            text = text[len(mention):]
        return text.strip()


# ---------------------------------------------------------------------------
# Smoke tests / examples
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    BOT_ID = "U12345678"
    adapter = SlackAdapter()

    # Example 1: simple DM
    dm_event = {
        "type": "message",
        "channel": "D98765432",
        "channel_type": "im",
        "user": "U00000001",
        "text": "Hello bot",
        "ts": "1716123456.123456",
    }

    assert adapter.extract_thread_id(dm_event) == "1716123456.123456"
    assert adapter.extract_user_message(dm_event) == "Hello bot"
    assert adapter.extract_user_id(dm_event) == "U00000001"
    assert adapter.extract_channel_id(dm_event) == "D98765432"
    assert adapter.extract_channel_type(dm_event) == "im"
    assert adapter.should_respond(dm_event, BOT_ID) is True

    reply = adapter.build_reply_payload("Hi there!")
    assert reply == {"text": "Hi there!"}

    # Example 2: channel mention
    channel_mention_event = {
        "type": "message",
        "channel": "C11111111",
        "channel_type": "channel",
        "user": "U00000002",
        "text": f"<@{BOT_ID}> please summarize",
        "ts": "1716123457.000001",
    }

    assert adapter.extract_thread_id(channel_mention_event) == "1716123457.000001"
    assert adapter.should_respond(channel_mention_event, BOT_ID) is True
    assert adapter.strip_bot_mention(channel_mention_event["text"], BOT_ID) == "please summarize"

    reply_threaded = adapter.build_reply_payload("Here is the summary.", thread_ts="1716123457.000001")
    assert reply_threaded == {
        "text": "Here is the summary.",
        "thread_ts": "1716123457.000001",
    }

    # Example 3: threaded reply (bot already in thread)
    thread_reply_event = {
        "type": "message",
        "channel": "C11111111",
        "channel_type": "channel",
        "user": "U00000003",
        "text": "thanks!",
        "ts": "1716123458.000002",
        "thread_ts": "1716123457.000001",
    }

    assert adapter.should_respond(thread_reply_event, BOT_ID) is True
    # For threaded replies, extract_thread_id returns thread_ts (parent), not the reply ts
    assert adapter.extract_thread_id(thread_reply_event) == "1716123457.000001"

    # Example 4: bot should skip its own message
    bot_own_event = {
        "type": "message",
        "channel": "C11111111",
        "channel_type": "channel",
        "user": BOT_ID,
        "text": "I agree",
        "ts": "1716123459.000003",
    }

    assert adapter.should_respond(bot_own_event, BOT_ID) is False

    # Example 5: bot_message subtype
    bot_subtype_event = {
        "type": "message",
        "channel": "D98765432",
        "channel_type": "im",
        "subtype": "bot_message",
        "bot_id": "B123",
        "text": " Automated alert",
        "ts": "1716123460.000004",
    }

    assert adapter.should_respond(bot_subtype_event, BOT_ID) is False

    # Example 6: channel message without mention or thread
    no_mention_event = {
        "type": "message",
        "channel": "C11111111",
        "channel_type": "channel",
        "user": "U00000004",
        "text": "random chat",
        "ts": "1716123461.000005",
    }

    assert adapter.should_respond(no_mention_event, BOT_ID) is False

    print("All SlackAdapter assertions passed.")
