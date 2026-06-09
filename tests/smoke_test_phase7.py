#!/usr/bin/env python3
"""Practical end-to-end smoke test for Phase 7 Chat Interface.

Run this before starting the bot to verify:
1. Slack tokens are valid
2. LLM backend is reachable
3. Session store works
4. Context loader finds memory files
5. All imports resolve correctly

Usage:
    python tests/smoke_test_phase7.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CHAT_DIR = PROJECT_ROOT / ".claude" / "chat"
SCRIPTS_DIR = PROJECT_ROOT / ".claude" / "scripts"

sys.path.insert(0, str(CHAT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

def banner(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def pass_fail(label, ok, detail=""):
    icon = "[PASS]" if ok else "[FAIL]"
    print(f"  {icon}  {label}" + (f"  ({detail})" if detail else ""))
    return ok


def main():
    results = []

    # ------------------------------------------------------------------ #
    # 1. Environment check
    # ------------------------------------------------------------------ #
    banner("1. Environment & Tokens")
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    slack_bot = os.environ.get("SLACK_BOT_TOKEN")
    slack_app = os.environ.get("SLACK_APP_TOKEN")
    results.append(pass_fail("SLACK_BOT_TOKEN exists", bool(slack_bot), f"length={len(slack_bot or '')}"))
    results.append(pass_fail("SLACK_APP_TOKEN exists", bool(slack_app), f"length={len(slack_app or '')}"))

    # ------------------------------------------------------------------ #
    # 2. Slack auth test
    # ------------------------------------------------------------------ #
    banner("2. Slack API Connectivity")
    try:
        from slack_sdk import WebClient
        client = WebClient(token=slack_bot)
        auth = client.auth_test()
        results.append(pass_fail("auth.test succeeds", auth.get("ok")))
        print(f"      Team: {auth.get('team')} | Bot: {auth.get('user')} ({auth.get('user_id')})")

        # Try listing channels
        ch_resp = client.conversations_list(types="public_channel,private_channel")
        chs = ch_resp.get("channels", [])
        results.append(pass_fail("conversations_list works", True, f"{len(chs)} channels"))
    except Exception as exc:
        results.append(pass_fail("Slack API", False, str(exc)))

    # ------------------------------------------------------------------ #
    # 3. LLM backend check
    # ------------------------------------------------------------------ #
    banner("3. LLM Backend")
    try:
        from llm_client import LLMClient
        llm = LLMClient()
        health = llm.health()
        results.append(pass_fail(f"Backend: {health['backend']}", True, f"model={health['model']}"))
        results.append(pass_fail("Ollama reachable", health.get("ollama_reachable", False)))
        results.append(pass_fail("Groq ready", health.get("groq_ready", False)))
        results.append(pass_fail("Anthropic ready", health.get("anthropic_ready", False)))
    except Exception as exc:
        results.append(pass_fail("LLM backend", False, str(exc)))

    # ------------------------------------------------------------------ #
    # 4. Session store
    # ------------------------------------------------------------------ #
    banner("4. Session Store (SQLite)")
    try:
        from session_store import SessionStore
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "smoke.db")
            store = SessionStore(db)
            s = store.get_or_create("thread_123", "C1", "U1")
            results.append(pass_fail("get_or_create", s.is_new and s.thread_ts == "thread_123"))
            store.append_message("thread_123", "user", "hello")
            msgs = store.get_messages("thread_123")
            results.append(pass_fail("append + get", len(msgs) == 1 and msgs[0]["content"] == "hello"))
    except Exception as exc:
        results.append(pass_fail("Session store", False, str(exc)))

    # ------------------------------------------------------------------ #
    # 5. Context loader
    # ------------------------------------------------------------------ #
    banner("5. Context Loader (Memory Files)")
    try:
        import context_loader as ctx
        core = ctx.load_core_context()
        results.append(pass_fail("load_core_context", len(core) > 0, f"{len(core)} chars"))

        daily = ctx.load_daily_logs(n=3)
        results.append(pass_fail("load_daily_logs", True, f"{len(daily)} chars"))

        prompt = ctx.build_system_prompt(include_daily_logs=True)
        results.append(pass_fail("build_system_prompt", len(prompt) > 0, f"{len(prompt)} chars"))
    except Exception as exc:
        results.append(pass_fail("Context loader", False, str(exc)))

    # ------------------------------------------------------------------ #
    # 6. Adapters
    # ------------------------------------------------------------------ #
    banner("6. Slack Adapter")
    try:
        from adapters import SlackAdapter
        a = SlackAdapter()
        dm = {"type": "message", "channel": "D1", "channel_type": "im", "user": "U1", "text": "hi", "ts": "123"}
        results.append(pass_fail("should_respond (DM)", a.should_respond(dm, "UBOT")))

        mention = {"type": "message", "channel": "C1", "channel_type": "channel", "user": "U1", "text": "<@UBOT> hi", "ts": "123"}
        results.append(pass_fail("should_respond (mention)", a.should_respond(mention, "UBOT")))

        plain = {"type": "message", "channel": "C1", "channel_type": "channel", "user": "U1", "text": "random", "ts": "123"}
        results.append(pass_fail("should_not_respond (plain)", not a.should_respond(plain, "UBOT")))
    except Exception as exc:
        results.append(pass_fail("Adapter", False, str(exc)))

    # ------------------------------------------------------------------ #
    # 7. Bot imports
    # ------------------------------------------------------------------ #
    banner("7. Bot Module Import")
    try:
        # Import without triggering the App() constructor
        import importlib.util
        spec = importlib.util.spec_from_file_location("bot", CHAT_DIR / "bot.py")
        mod = importlib.util.module_from_spec(spec)
        # We won't execute it (would start the app), just verify syntax
        import ast
        ast.parse((CHAT_DIR / "bot.py").read_text())
        results.append(pass_fail("bot.py syntax valid", True))
    except Exception as exc:
        results.append(pass_fail("bot.py syntax", False, str(exc)))

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    passed = sum(results)
    total = len(results)
    banner(f"Summary: {passed}/{total} checks passed")

    if passed == total:
        print("\nAll systems green. You can start the bot:")
        print("     python .claude/chat/bot.py")
        return 0
    else:
        print("\nSome checks failed. Fix the issues above before starting the bot.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
