"""SQLite-backed chat session store for Slack bot threads.

Each Slack thread maps to one persistent ChatSession. Messages are stored
as a JSON array and hydrated on read. Connections are opened per method
call so the module is safe to use from multiple threads.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from contextlib import contextmanager

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class ChatSession:
    """Represents a single Slack-thread conversation session."""

    thread_ts: str
    channel_id: str
    user_id: str
    messages: List[dict]
    system_prompt: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_new: bool = False  # True when the session was just created


class SessionStore:
    """Persistent store for Slack-thread chat sessions backed by SQLite."""

    def __init__(self, db_path: str = ".claude/data/chat.db") -> None:
        """Initialize the store, ensuring tables exist.

        Args:
            db_path: Path to the SQLite database file. Parent directories are
                created automatically if they do not exist.
        """
        self._db_path = Path(db_path).resolve()
        self._ensure_parent_dir()
        self._init_db()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _ensure_parent_dir(self) -> None:
        """Create the parent directory for the database if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        """Return the current time as an ISO 8601 string in IST."""
        return datetime.now(IST).isoformat()

    @contextmanager
    def _connect(self):
        """Open a new connection with row factory enabled (auto-commits/closes)."""
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #

    def _init_db(self) -> None:
        """Create tables and indexes if they do not already exist."""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    thread_ts     TEXT PRIMARY KEY,
                    channel_id    TEXT NOT NULL,
                    user_id       TEXT NOT NULL,
                    messages_json TEXT NOT NULL DEFAULT '[]',
                    system_prompt TEXT,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS thread_meta (
                    thread_ts    TEXT PRIMARY KEY,
                    channel_name TEXT,
                    user_name    TEXT,
                    message_count INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                    ON sessions(updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_sessions_channel
                    ON sessions(channel_id);
                """
            )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def get_or_create(
        self, thread_ts: str, channel_id: str, user_id: str
    ) -> ChatSession:
        """Fetch an existing session or create a fresh one.

        Args:
            thread_ts: Slack thread timestamp (unique identifier).
            channel_id: Slack channel ID.
            user_id: Slack user ID.

        Returns:
            A ``ChatSession`` instance. ``is_new`` is ``True`` when created.
        """
        existing = self.get_session(thread_ts)
        if existing is not None:
            existing.is_new = False
            return existing

        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (thread_ts, channel_id, user_id,
                                      messages_json, system_prompt,
                                      created_at, updated_at)
                VALUES (?, ?, ?, '[]', NULL, ?, ?)
                ON CONFLICT(thread_ts) DO NOTHING
                """,
                (thread_ts, channel_id, user_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO thread_meta (thread_ts, message_count)
                VALUES (?, 0)
                ON CONFLICT(thread_ts) DO NOTHING
                """,
                (thread_ts,),
            )

        session = ChatSession(
            thread_ts=thread_ts,
            channel_id=channel_id,
            user_id=user_id,
            messages=[],
            system_prompt=None,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            is_new=True,
        )
        return session

    def get_session(self, thread_ts: str) -> Optional[ChatSession]:
        """Retrieve a session by thread timestamp.

        Args:
            thread_ts: Slack thread timestamp.

        Returns:
            The matching ``ChatSession``, or ``None`` if not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE thread_ts = ?", (thread_ts,)
            ).fetchone()

        if row is None:
            return None

        messages = self._load_messages(row["messages_json"])
        return ChatSession(
            thread_ts=row["thread_ts"],
            channel_id=row["channel_id"],
            user_id=row["user_id"],
            messages=messages,
            system_prompt=row["system_prompt"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_new=False,
        )

    def append_message(self, thread_ts: str, role: str, content: str) -> None:
        """Append a message dict to the session's message history.

        Args:
            thread_ts: Slack thread timestamp.
            role: Message role (e.g. ``user``, ``assistant``, ``system``).
            content: Message text.
        """
        session = self.get_session(thread_ts)
        if session is None:
            raise KeyError(f"No session found for thread_ts={thread_ts}")

        session.messages.append({"role": role, "content": content})
        now = self._now()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET messages_json = ?, updated_at = ?
                WHERE thread_ts = ?
                """,
                (json.dumps(session.messages, ensure_ascii=False), now, thread_ts),
            )
            conn.execute(
                """
                INSERT INTO thread_meta (thread_ts, message_count)
                VALUES (?, 1)
                ON CONFLICT(thread_ts) DO UPDATE SET
                    message_count = message_count + 1
                """,
                (thread_ts,),
            )

    def get_messages(self, thread_ts: str) -> List[dict]:
        """Return the conversation history for a thread.

        Args:
            thread_ts: Slack thread timestamp.

        Returns:
            List of message dicts with ``role`` and ``content`` keys.
        """
        session = self.get_session(thread_ts)
        if session is None:
            return []
        return session.messages

    def get_pruned_messages(self, thread_ts: str, max_messages: int = 20) -> List[dict]:
        """Return the last ``max_messages`` messages for a thread.

        Keeps the most recent conversation context while avoiding
        unbounded growth that inflates LLM token usage.

        Args:
            thread_ts: Slack thread timestamp.
            max_messages: Maximum number of recent messages to retain.

        Returns:
            List of message dicts with ``role`` and ``content`` keys.
        """
        messages = self.get_messages(thread_ts)
        if len(messages) <= max_messages:
            return messages
        return messages[-max_messages:]

    def set_system_prompt(self, thread_ts: str, prompt: str) -> None:
        """Set (or overwrite) the system prompt for a session.

        Args:
            thread_ts: Slack thread timestamp.
            prompt: The system prompt text.
        """
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET system_prompt = ?, updated_at = ?
                WHERE thread_ts = ?
                """,
                (prompt, now, thread_ts),
            )

    def get_system_prompt(self, thread_ts: str) -> Optional[str]:
        """Return the system prompt for a session, if any.

        Args:
            thread_ts: Slack thread timestamp.

        Returns:
            The prompt string, or ``None``.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT system_prompt FROM sessions WHERE thread_ts = ?",
                (thread_ts,),
            ).fetchone()
        return row["system_prompt"] if row else None

    def list_sessions(self, limit: int = 100) -> List[ChatSession]:
        """List recent sessions ordered by ``updated_at`` descending.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of ``ChatSession`` objects.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        sessions: List[ChatSession] = []
        for row in rows:
            sessions.append(
                ChatSession(
                    thread_ts=row["thread_ts"],
                    channel_id=row["channel_id"],
                    user_id=row["user_id"],
                    messages=self._load_messages(row["messages_json"]),
                    system_prompt=row["system_prompt"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    is_new=False,
                )
            )
        return sessions

    def clear_session(self, thread_ts: str) -> None:
        """Delete a session and its metadata.

        Args:
            thread_ts: Slack thread timestamp.
        """
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE thread_ts = ?", (thread_ts,))
            conn.execute("DELETE FROM thread_meta WHERE thread_ts = ?", (thread_ts,))

    def prune_old_sessions(self, days: int = 30) -> int:
        """Remove sessions that have not been updated in the last ``days`` days.

        Args:
            days: Age threshold in days.

        Returns:
            Number of sessions deleted.
        """
        cutoff = datetime.now(IST) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        with self._connect() as conn:
            # Collect thread_ts values to delete from both tables
            rows = conn.execute(
                "SELECT thread_ts FROM sessions WHERE updated_at < ?",
                (cutoff_iso,),
            ).fetchall()
            thread_ts_list = [r["thread_ts"] for r in rows]

            if not thread_ts_list:
                return 0

            placeholders = ",".join("?" * len(thread_ts_list))
            conn.execute(
                f"DELETE FROM sessions WHERE thread_ts IN ({placeholders})",
                thread_ts_list,
            )
            conn.execute(
                f"DELETE FROM thread_meta WHERE thread_ts IN ({placeholders})",
                thread_ts_list,
            )

        return len(thread_ts_list)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_messages(raw: str) -> List[dict]:
        """Safely deserialize a JSON message array.

        Returns an empty list on decode failure so the conversation is not lost.
        """
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []


# ---------------------------------------------------------------------- #
# Sanity test
# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_chat.db")
        store = SessionStore(db_path)

        # 1. Create a session
        session = store.get_or_create(
            thread_ts="1234567890.123456",
            channel_id="C123",
            user_id="U456",
        )
        assert session.is_new is True
        assert session.messages == []
        print("PASS: get_or_create returns new session")

        # 2. Fetch existing session
        existing = store.get_or_create(
            thread_ts="1234567890.123456",
            channel_id="C123",
            user_id="U456",
        )
        assert existing.is_new is False
        print("PASS: get_or_create returns existing session")

        # 3. Append messages
        store.append_message("1234567890.123456", "user", "Hello!")
        store.append_message("1234567890.123456", "assistant", "Hi there!")
        msgs = store.get_messages("1234567890.123456")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "Hi there!"
        print("PASS: append_message and get_messages work")

        # 4. System prompt
        store.set_system_prompt("1234567890.123456", "You are a helpful assistant.")
        prompt = store.get_system_prompt("1234567890.123456")
        assert prompt == "You are a helpful assistant."
        print("PASS: set_system_prompt and get_system_prompt work")

        # 5. List sessions
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].thread_ts == "1234567890.123456"
        print("PASS: list_sessions works")

        # 6. Prune (nothing old yet)
        pruned = store.prune_old_sessions(days=1)
        assert pruned == 0
        print("PASS: prune_old_sessions returns 0 for fresh session")

        # 7. Clear session
        store.clear_session("1234567890.123456")
        assert store.get_session("1234567890.123456") is None
        print("PASS: clear_session deletes the session")

        print("\nAll sanity tests passed.")
