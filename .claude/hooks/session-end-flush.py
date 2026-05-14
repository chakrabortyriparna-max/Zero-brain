#!/usr/bin/env python3
"""
DIAGNOSTIC SessionEnd Hook.
Logs exactly what stdin receives to a debug file before proceeding.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from shared_extract import extract_all_insights  # noqa: E402

PROJECT_ROOT = SCRIPT_DIR.parent.parent
DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
DEBUG_FILE = PROJECT_ROOT / ".claude" / "data" / "session-end-debug.log"

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
    # Read ALL stdin
    raw_stdin = sys.stdin.read()
    lines = raw_stdin.splitlines()

    # DEBUG: log what we received
    DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_FILE, "a", encoding="utf-8") as dbg:
        now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
        dbg.write(f"\n=== SessionEnd triggered at {now} ===\n")
        dbg.write(f"Raw stdin length: {len(raw_stdin)} chars\n")
        dbg.write(f"Number of lines: {len(lines)}\n")
        if lines:
            dbg.write("First 5 lines:\n")
            for i, line in enumerate(lines[:5]):
                dbg.write(f"  [{i}] {line[:200]}\n")
        else:
            dbg.write("STDIN IS EMPTY\n")

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

    # DEBUG: log extraction results
    with open(DEBUG_FILE, "a", encoding="utf-8") as dbg:
        dbg.write(f"Transcript entries parsed: {len(transcript)}\n")
        dbg.write(f"Insights extracted: {len(insights)}\n")
        if insights:
            for ins in insights:
                dbg.write(f"  - {ins}\n")

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
