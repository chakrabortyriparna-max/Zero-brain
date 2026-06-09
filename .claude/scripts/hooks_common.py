#!/usr/bin/env python3
"""Shared utilities for Second Brain hooks.

Extracts common logic (daily file creation, Cognee push, context loading)
to eliminate duplication across session-start, pre-compact, and session-end hooks.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
IST = timezone(timedelta(hours=5, minutes=30))


def ensure_daily_file(date_str: str) -> Path:
    """Create or return today's daily log file with Obsidian frontmatter."""
    daily_file = DAILY_DIR / f"{date_str}.md"
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    if not daily_file.exists():
        header = (
            f"---\n"
            f"date: {date_str}\n"
            f"timezone: IST (UTC+5:30)\n"
            f"---\n\n"
            f"# Daily Log — {date_str}\n"
        )
        daily_file.write_text(header, encoding="utf-8")
    return daily_file


def push_to_cognee(text: str, source: str) -> bool:
    """Push text to Cognee graph-vector memory. Non-blocking; errors swallowed.

    Uses the shared run_sync helper from cognee_memory for safe async execution.
    Returns True on success, False on failure.
    """
    try:
        scripts_dir = str(SCRIPT_DIR.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from cognee_memory import create_memory, run_sync

        mem = create_memory()
        run_sync(mem.ingest_text(text, source=source))
        return True
    except Exception as exc:
        print(f"[Cognee push failed] {exc}", file=sys.stderr)
        return False


def load_claude_md_content() -> tuple[str, str]:
    """Load actual content of project and global CLAUDE.md files.

    Returns (project_content, global_content).
    """
    project_claude = PROJECT_ROOT / "CLAUDE.md"
    global_claude = Path.home() / ".claude" / "CLAUDE.md"

    project_content = ""
    global_content = ""

    if project_claude.exists():
        try:
            project_content = project_claude.read_text(encoding="utf-8")
        except Exception:
            pass

    if global_claude.exists():
        try:
            global_content = global_claude.read_text(encoding="utf-8")
        except Exception:
            pass

    return project_content, global_content
