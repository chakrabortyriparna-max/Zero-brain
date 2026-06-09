#!/usr/bin/env python3
"""
Explicit Session Flush CLI for Riparna's Second Brain.

Reads the current (or specified) session transcript, extracts key
insights using shared heuristics, optionally uses an LLM for deeper
summarization, and appends a categorized block to today's daily log.

Usage:
    python .claude/scripts/flush_session.py
    python .claude/scripts/flush_session.py --preview
    python .claude/scripts/flush_session.py --transcript PATH
    python .claude/scripts/flush_session.py --llm
"""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
HOOKS_DIR = SCRIPT_DIR.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))
from shared_extract import extract_all_insights, format_insights  # noqa: E402

PROJECT_ROOT = SCRIPT_DIR.parent.parent
DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
TRANSCRIPT_PROJECT_DIR = Path.home() / ".claude" / "projects"

IST = timezone(timedelta(hours=5, minutes=30))


def ensure_daily_file(date_str: str) -> Path:
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


def _normalize_path_part(part: str) -> str:
    """Normalize a path part for matching against Claude project dir slugs."""
    return part.lower().replace(" ", "-").replace("_", "-")


def discover_current_transcript() -> Path | None:
    """Find the most recently modified JSONL transcript for this project."""
    cwd = Path.cwd().resolve()
    # Use the last few folder names as match tokens
    folder_tokens = [_normalize_path_part(p) for p in cwd.parts if p and p not in ("/", "\\", "C:", "Users", "home")]
    # Primary token is the immediate folder name (e.g., 'second-brain-starter')
    primary_token = folder_tokens[-1] if folder_tokens else ""
    # Secondary token is the parent folder (e.g., 'zero-brain')
    secondary_token = folder_tokens[-2] if len(folder_tokens) >= 2 else ""

    candidates = []
    if not TRANSCRIPT_PROJECT_DIR.exists():
        return None

    for proj_dir in TRANSCRIPT_PROJECT_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        proj_name_lower = proj_dir.name.lower()
        # Match if project dir contains both primary and secondary tokens
        match = primary_token and primary_token in proj_name_lower
        if secondary_token:
            match = match and secondary_token in proj_name_lower
        if not match:
            continue

        # Main transcripts
        jsonls = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if jsonls:
            candidates.append(jsonls[0])

        # Subagent transcripts
        subagents_dir = proj_dir / "subagents"
        if subagents_dir.is_dir():
            sub_jsonls = sorted(subagents_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if sub_jsonls:
                candidates.append(sub_jsonls[0])

    if not candidates:
        return None

    # Pick the most recently modified transcript overall
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_transcript(path: Path) -> list[dict]:
    transcript: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                transcript.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return transcript


def llm_summarize(transcript: list[dict]) -> dict[str, list[str]] | None:
    """Optional LLM-powered summarization via Anthropic API."""
    try:
        import anthropic
    except ImportError:
        print("[flush] anthropic package not installed; skipping LLM mode.")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[flush] ANTHROPIC_API_KEY not set; skipping LLM mode.")
        return None

    # Build a condensed transcript for the LLM (limit token usage)
    condensed_lines: list[str] = []
    for entry in transcript:
        etype = entry.get("type")
        if etype == "user":
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                condensed_lines.append(f"User: {content[:400]}")
        elif etype == "assistant":
            msg = entry.get("message", {})
            content = msg.get("content", [])
            texts: list[str] = []
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text", "")
                    if isinstance(t, str):
                        texts.append(t)
            if texts:
                condensed_lines.append(f"Assistant: {' '.join(texts)[:600]}")

    condensed = "\n".join(condensed_lines[-200:])  # last ~200 entries to keep cost low

    if not condensed:
        return None

    prompt = (
        "You are a session summarizer. Read the following conversation transcript "
        "and extract only significant items into these categories:\n"
        "- Decisions (what was decided)\n"
        "- Action Items (who needs to do what)\n"
        "- File Changes / Commits (what code/config was modified)\n"
        "- Lessons / Key Facts (what was learned or noted)\n"
        "Return JSON only with keys: Decisions, Action Items, File Changes, Lessons, Key Facts. "
        "Each value is a list of short strings. If a category has no items, use an empty list.\n\n"
        f"Transcript:\n{condensed}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
        # Find JSON in response
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(text[start:end+1])
            # Normalize to our category names
            mapping = {
                "Decisions": "Decisions",
                "Action Items": "Action Items",
                "File Changes": "File Changes",
                "Commits": "Commits",
                "Lessons": "Lessons",
                "Key Facts": "Key Facts",
            }
            result: dict[str, list[str]] = {}
            for k, v in parsed.items():
                canonical = mapping.get(k, k)
                if isinstance(v, list):
                    result[canonical] = [str(i) for i in v if i]
            return result
    except Exception as e:
        print(f"[flush] LLM summarization failed: {e}")

    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Flush session insights to daily log")
    parser.add_argument("--transcript", type=Path, help="Path to JSONL transcript")
    parser.add_argument("--preview", action="store_true", help="Show what would be saved without writing")
    parser.add_argument("--llm", action="store_true", help="Use LLM for summarization (costs API tokens)")
    args = parser.parse_args()

    # Resolve transcript
    transcript_path = args.transcript
    if not transcript_path:
        transcript_path = discover_current_transcript()

    if not transcript_path or not transcript_path.exists():
        print("[flush] No transcript found. Specify one with --transcript.")
        sys.exit(1)

    # Load transcript
    transcript = load_transcript(transcript_path)

    # Extract insights
    if args.llm:
        categorized = llm_summarize(transcript)
        if categorized is None:
            print("[flush] Falling back to heuristic extraction.")
            categorized = extract_all_insights(transcript)
    else:
        categorized = extract_all_insights(transcript)

    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%H:%M IST")

    # Build output
    title = f"Session Flush — {timestamp}"
    output = format_insights(categorized, title=title)

    # Console summary
    total = sum(len(v) for v in categorized.values())
    print(f"\n=== {title} ===")
    print(f"Transcript: {transcript_path}")
    print(f"Entries parsed: {len(transcript)}")
    print(f"Insights extracted: {total}")
    if total == 0:
        print("\nNo insights captured. Try using explicit tags in conversation:")
        print('  **Decision:** We will ...')
        print('  **Action Item:** Riparna to ...')
        print('  **Lesson:** ...')
    else:
        for cat, items in categorized.items():
            print(f"\n{cat} ({len(items)}):")
            for item in items:
                print(f"  - {item}")

    if not args.preview:
        daily_file = ensure_daily_file(today)
        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(output)
        print(f"\nAppended to {daily_file}")
    else:
        print("\n[PREVIEW] Nothing was written. Run without --preview to save.")


if __name__ == "__main__":
    main()
