#!/usr/bin/env python3
"""
SessionEnd Hook for Riparna's Second Brain.
On session end, saves remaining conversation context to the daily log.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
# Allow importing shared_extract from the same directory
sys.path.insert(0, str(SCRIPT_DIR))
from shared_extract import extract_all_insights  # noqa: E402

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
    # Read session data from stdin if provided
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

    insights = extract_all_insights(transcript)

    # Exit silently when there is nothing to record
    if not insights:
        sys.exit(0)

    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    daily_file = ensure_daily_file(today)

    timestamp = now.strftime("%H:%M IST")
    block = f"\n\n## Session End — {timestamp}\n\n" + "\n".join(insights) + "\n"

    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(block)

    sys.exit(0)


if __name__ == "__main__":
    main()
