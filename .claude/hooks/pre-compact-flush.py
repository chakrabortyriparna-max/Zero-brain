#!/usr/bin/env python3
"""
PreCompact Hook for Riparna's Second Brain.
Reads JSONL transcript from stdin, extracts key decisions/facts/action items,
and appends a categorized block to today's daily log with IST timestamps.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from shared_extract import extract_all_insights, format_insights  # noqa: E402

PROJECT_ROOT = SCRIPT_DIR.parent.parent
DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"

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


def main():
    # Read JSONL transcript from stdin
    lines = sys.stdin.readlines()
    transcript = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            transcript.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    categorized = extract_all_insights(transcript)

    if not categorized:
        # Nothing to save; exit quietly
        sys.exit(0)

    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    daily_file = ensure_daily_file(today)

    timestamp = now.strftime("%H:%M IST")
    block = format_insights(categorized, title=f"Pre-Compact Flush — {timestamp}")

    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(block)

    sys.exit(0)


if __name__ == "__main__":
    main()
