#!/usr/bin/env python3
"""Main Slack bot — Phase 7 Chat Interface.

Routes DMs and @mentions to persistent LLM conversations via Socket Mode.
Each Slack thread (or DM channel) = one persistent session backed by SQLite.

Security boundaries:
- Only responds to DMs, @mentions, and replies in threads the bot is in.
- Never initiates conversations.
- Never sends messages without user interaction.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Ensure project scripts are importable
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "scripts"))

from adapters import SlackAdapter  # noqa: E402
from context_loader import build_system_prompt  # noqa: E402
from graphify_query import build_llm_context  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from session_store import SessionStore  # noqa: E402

# Lazy Cognee imports — graph context for knowledge questions
try:
    from cognee_memory import create_memory
    from cognee.modules.search.types import SearchType
except Exception:
    create_memory = None  # type: ignore[misc]
    SearchType = None  # type: ignore[misc]

load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    print(
        "[bot] ERROR: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in .env",
        file=sys.stderr,
    )
    sys.exit(1)

# token_verification_enabled=False avoids an auth.test call at import time.
# We run auth_test explicitly in main() before starting the handler.
app = App(token=SLACK_BOT_TOKEN, token_verification_enabled=False)
adapter = SlackAdapter()
store = SessionStore(str(PROJECT_ROOT / ".claude" / "data" / "chat.db"))
llm = LLMClient()

BOT_USER_ID: str = ""

# Simple in-memory dedup to guard against duplicate event delivery.
_recently_processed: set[str] = set()
_DEDUP_LIMIT = 1000


def _is_duplicate(ts: str) -> bool:
    if ts in _recently_processed:
        return True
    _recently_processed.add(ts)
    # Prevent unbounded growth
    if len(_recently_processed) > _DEDUP_LIMIT:
        # Keep the most recent half
        sorted_ts = sorted(_recently_processed)
        _recently_processed.clear()
        _recently_processed.update(sorted_ts[_DEDUP_LIMIT // 2:])
    return False


def _resolve_session_and_thread(event: dict) -> tuple[str, Optional[str]]:
    """Return (session_id, thread_ts_for_reply) for this event.

    - DMs: session_id = channel_id, thread_ts = None (no threading needed)
    - Channels / app_mentions: session_id = thread_ts or ts,
      thread_ts = thread_ts or ts (reply in thread)
    """
    channel_type = adapter.extract_channel_type(event)
    if channel_type == "im":
        return adapter.extract_channel_id(event), None

    # For channels, use thread_ts if present (threaded reply),
    # otherwise use the message ts (first mention = new thread).
    ts = event.get("ts", "")
    thread_ts = event.get("thread_ts")
    session_id = thread_ts or ts
    reply_ts = thread_ts or ts
    return session_id, reply_ts


def _process_message(
    session_id: str,
    channel_id: str,
    user_id: str,
    text: str,
    say,
    thread_ts: Optional[str] = None,
) -> None:
    """Core message processing: load session, query LLM, reply, save history."""
    t_start = time.perf_counter()
    t_phases = {}

    # Load or create session
    session = store.get_or_create(session_id, channel_id, user_id)
    t_phases["session"] = time.perf_counter()

    # Only build system prompt for new sessions; reuse cached prompt for replies
    if session.is_new:
        try:
            system_prompt = build_system_prompt(include_daily_logs=True)
            store.set_system_prompt(session_id, system_prompt)
            print(f"[bot] New session {session_id} — injected memory context.")
        except Exception as exc:
            print(f"[bot] Warning: failed to load memory context: {exc}", file=sys.stderr)
            system_prompt = ""
    else:
        system_prompt = store.get_system_prompt(session_id) or ""
    t_phases["prompt"] = time.perf_counter()

    # Detect graphify commands for agentic mode
    parts = text.strip().split(None, 2)
    is_graphify = parts and parts[0].lower() == "graphify"
    graph_context = None
    if is_graphify:
        if len(parts) < 2:
            help_text = (
                "*Graphify commands:*\n"
                "- `graphify query <text>` — find matching nodes\n"
                "- `graphify neighbors <node>` — show connections\n"
                "- `graphify path <start> <end>` — shortest path\n"
                "- `graphify explain <node>` — full node details"
            )
            _send_reply(say, help_text, thread_ts=thread_ts)
            t_phases["reply"] = time.perf_counter()
            _log_timings("graphify-help", t_start, t_phases)
            return

        subcmd = parts[1].lower()
        arg = parts[2] if len(parts) > 2 else ""
        t_graph0 = time.perf_counter()
        try:
            graph_context = build_llm_context(subcmd, arg)
        except Exception as exc:
            print(f"[bot] graphify build failed: {exc}", file=sys.stderr)
            graph_context = f"Error building graph context: {exc}"
        print(
            f"[bot] graphify '{subcmd}' context built in "
            f"{int((time.perf_counter() - t_graph0) * 1000)}ms",
            file=sys.stderr,
        )

    # Append user message
    store.append_message(session_id, "user", text)

    # Build pruned message history for LLM (last 20 messages)
    messages = store.get_pruned_messages(session_id, max_messages=20)
    t_phases["history"] = time.perf_counter()

    # Inject graph context for agentic graphify mode
    if graph_context:
        # Remove the current user message (graphify command) from the list
        # and replace it with structured context + the original question
        if messages and messages[-1].get("role") == "user":
            messages.pop()

        instructions = (
            "You have access to a Graphify knowledge graph for this codebase. "
            "Use ONLY the graph context below to answer. "
            "If the context is insufficient, say so and suggest which files to read. "
            "Cite source files when possible.\n\n"
            f"{graph_context}"
        )
        messages.append({"role": "user", "content": instructions})
        messages.append({"role": "user", "content": f"User query: {text}"})

    # Inject Cognee graph context for knowledge questions (non-graphify)
    if not is_graphify:
        lowered = text.lower()
        if any(kw in lowered for kw in ("who", "what", "when", "why", "how", "project", "decision", "lesson", "fact")):
            cognee_ctx = _fetch_cognee_chat_context(text)
            if cognee_ctx:
                messages.append({"role": "system", "content": cognee_ctx})

    try:
        # Query LLM with pruned conversation history
        response = llm.chat(messages, system=system_prompt, max_tokens=2048)
    except Exception as exc:
        print(f"[bot] LLM error for session {session_id}: {exc}", file=sys.stderr)
        _send_reply(
            say,
            "Sorry, I ran into an error processing your message. Please try again.",
            thread_ts=thread_ts,
        )
        t_phases["reply"] = time.perf_counter()
        _log_timings("llm-error", t_start, t_phases)
        return
    t_phases["llm"] = time.perf_counter()

    # Save assistant response
    store.append_message(session_id, "assistant", response)

    # Reply
    _send_reply(say, response, thread_ts=thread_ts)
    t_phases["reply"] = time.perf_counter()
    _log_timings("llm" if not is_graphify else "graphify-llm", t_start, t_phases)


def _fetch_cognee_chat_context(query: str) -> Optional[str]:
    """Query Cognee for graph context relevant to the user message."""
    if create_memory is None or SearchType is None:
        return None
    try:
        import asyncio

        mem = create_memory()
        results = asyncio.get_event_loop().run_until_complete(
            mem.search(query, search_type=SearchType.GRAPH_COMPLETION, top_k=5)
        )
        if not results:
            return None
        lines = "\n".join(f"- {r}" for r in results)
        return f"## Cognee Graph Context\n{lines}\n"
    except Exception:
        return None


def _log_timings(label: str, t_start: float, t_phases: dict) -> None:
    """Print per-phase timing breakdown to stderr."""
    keys = list(t_phases.keys())
    lines = []
    prev = t_start
    for k in keys:
        ms = int((t_phases[k] - prev) * 1000)
        lines.append(f"{k}={ms}ms")
        prev = t_phases[k]
    total = int((t_phases[keys[-1]] - t_start) * 1000)
    print(f"[bot] timing [{label}] total={total}ms | {' | '.join(lines)}", file=sys.stderr)


def _send_reply(say, text: str, thread_ts: Optional[str] = None) -> None:
    """Send a reply, optionally threaded."""
    if thread_ts:
        say(text=text, thread_ts=thread_ts)
    else:
        say(text=text)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@app.event("app_mention")
def handle_mention(body, say):
    """Handle @mentions in channels."""
    event = body["event"]
    ts = event.get("ts", "")

    if _is_duplicate(ts):
        return
    if not adapter.should_respond(event, BOT_USER_ID):
        return

    session_id, thread_ts = _resolve_session_and_thread(event)
    channel_id = adapter.extract_channel_id(event)
    user_id = adapter.extract_user_id(event)
    raw_text = adapter.extract_user_message(event)
    user_text = adapter.strip_bot_mention(raw_text, BOT_USER_ID)

    _process_message(session_id, channel_id, user_id, user_text, say, thread_ts=thread_ts)


@app.event("message")
def handle_message(body, say):
    """Handle DMs and threaded replies in channels."""
    event = body["event"]
    ts = event.get("ts", "")

    # Skip bot messages immediately (fast path)
    if event.get("subtype") == "bot_message" or event.get("user") == BOT_USER_ID:
        return

    if _is_duplicate(ts):
        return
    if not adapter.should_respond(event, BOT_USER_ID):
        return

    session_id, thread_ts = _resolve_session_and_thread(event)
    channel_id = adapter.extract_channel_id(event)
    user_id = adapter.extract_user_id(event)
    raw_text = adapter.extract_user_message(event)
    user_text = adapter.strip_bot_mention(raw_text, BOT_USER_ID)

    _process_message(session_id, channel_id, user_id, user_text, say, thread_ts=thread_ts)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    global BOT_USER_ID

    # Fetch bot user ID to avoid echo loops
    try:
        auth_test = app.client.auth_test()
        BOT_USER_ID = auth_test["user_id"]
        print(f"[bot] Authenticated as {auth_test['user']} ({BOT_USER_ID})")
    except Exception as exc:
        print(f"[bot] ERROR: auth_test failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print("[bot] Starting Socket Mode handler...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    main()
