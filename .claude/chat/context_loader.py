"""Load memory context for new chat sessions.

Provides SOUL.md + USER.md + MEMORY.md as a system prompt,
plus optional memory search for context-rich responses.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return len(text) // 4

# Resolve project root relative to this file: .claude/chat/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "Memory"


def _read_file(path: Path) -> str:
    """Read a file if it exists, return empty string otherwise."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_core_context() -> str:
    """
    Load SOUL.md + USER.md + MEMORY.md into a single context block.

    Returns a formatted string suitable for use as a system prompt
    or injected context at the start of a conversation.
    """
    soul = _read_file(MEMORY_DIR / "SOUL.md")
    user = _read_file(MEMORY_DIR / "USER.md")
    memory = _read_file(MEMORY_DIR / "MEMORY.md")

    parts = []
    if soul:
        parts.append(f"# Agent Identity (SOUL)\n{soul}")
    if user:
        parts.append(f"# User Profile (USER)\n{user}")
    if memory:
        parts.append(f"# Active Memory (MEMORY)\n{memory}")

    return "\n\n".join(parts)


def load_daily_logs(n: int = 3, max_chars_per_log: int = 8000) -> str:
    """
    Load the last N daily log files from Memory/daily/.

    Args:
        n: Number of recent daily logs to include.
        max_chars_per_log: Maximum characters to include from each log.
                           Default 8,000 chars ≈ ~2,000 tokens.

    Returns:
        Concatenated log content, or empty string if no logs found.
    """
    daily_dir = MEMORY_DIR / "daily"
    if not daily_dir.exists():
        return ""

    # Find YYYY-MM-DD.md files, sort descending, take N
    files = sorted(
        [f for f in daily_dir.iterdir() if f.suffix == ".md"],
        reverse=True,
    )[:n]

    if not files:
        return ""

    parts = ["# Recent Daily Logs"]
    for f in files:
        raw = f.read_text(encoding="utf-8")
        if len(raw) > max_chars_per_log:
            raw = raw[:max_chars_per_log] + f"\n\n... [truncated — {len(raw) - max_chars_per_log} more chars]"
        parts.append(f"## {f.stem}\n{raw}")

    return "\n\n".join(parts)


def search_memory(query: str, top_k: int = 5, path_prefix: Optional[str] = None) -> str:
    """
    Run a memory search and return formatted results.
    Primary: Cognee graph-vector search.
    Fallback: sqlite-vec + FTS5 hybrid search.
    """
    # Primary: Cognee graph-vector search
    try:
        import asyncio
        scripts_dir = str(PROJECT_ROOT / ".claude" / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from cognee_memory import create_memory, run_sync

        mem = create_memory()
        results = run_sync(mem.search(query, top_k=top_k))
        if results:
            lines = "\n".join(f"- {r}" for r in results)
            return f"# Relevant Memory Search Results (Cognee)\n{lines}\n"
    except Exception as exc:
        print(
            f"[context_loader] Cognee search failed: {exc}. Falling back to sqlite-vec.",
            file=sys.stderr,
        )

    # Fallback: sqlite-vec + FTS5 hybrid search
    search_script = PROJECT_ROOT / ".claude" / "scripts" / "memory_search.py"
    if not search_script.exists():
        return ""

    import subprocess, sys
    cmd = [sys.executable, str(search_script), query, "--top-k", str(top_k), "--mode", "hybrid"]
    if path_prefix:
        cmd.extend(["--path-prefix", path_prefix])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0:
            return f"# Relevant Memory Search Results\n{result.stdout}"
    except Exception:
        pass

    return ""


def build_system_prompt(include_daily_logs: bool = True, include_memory_search: Optional[str] = None) -> str:
    """
    Build the full system prompt for a new chat session.

    Args:
        include_daily_logs: Whether to append recent daily logs.
        include_memory_search: Optional search query to inject relevant memory.

    Returns:
        The complete system prompt string.
    """
    now_str = datetime.now(IST).strftime("%A, %d %B %Y, %I:%M %p %Z")
    system_info = f"# System Environment\nCurrent Date and Time: {now_str}"
    
    parts = [system_info, load_core_context()]

    if include_daily_logs:
        daily = load_daily_logs(n=3)
        if daily:
            parts.append(daily)

    if include_memory_search:
        search_results = search_memory(include_memory_search, top_k=5)
        if search_results:
            parts.append(search_results)

    prompt = "\n\n".join(parts)
    tok = estimate_tokens(prompt)
    if tok > 20000:
        print(
            f"[context_loader] WARNING: system prompt is ~{tok} tokens. "
            "Consider reducing max_chars_per_log or n.",
            file=sys.stderr,
        )
    return prompt


def _demo():
    """Quick sanity test — prints context length."""
    context = build_system_prompt(include_daily_logs=True)
    print(f"System prompt length: {len(context)} characters")
    print("---" * 20)
    print(context[:2000])
    print("...")


if __name__ == "__main__":
    _demo()
