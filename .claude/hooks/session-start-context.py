#!/usr/bin/env python3
"""
SessionStart Hook for Riparna's Second Brain.
Reads SOUL.md + USER.md + MEMORY.md + last 3 daily logs.
Outputs combined context to stdout for injection into the conversation.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MEMORY_DIR = PROJECT_ROOT / "Memory"
DAILY_DIR = MEMORY_DIR / "daily"

IST = timezone(timedelta(hours=5, minutes=30))


def read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!-- {path.name} not found -->\n"


def get_last_n_daily_logs(n: int = 3) -> list[Path]:
    if not DAILY_DIR.exists():
        return []
    logs = sorted(DAILY_DIR.glob("*.md"), reverse=True)
    return logs[:n]


def build_context() -> str:
    soul = read_file(MEMORY_DIR / "SOUL.md")
    user = read_file(MEMORY_DIR / "USER.md")
    memory = read_file(MEMORY_DIR / "MEMORY.md")

    logs = get_last_n_daily_logs(3)
    daily_sections = []
    for log in logs:
        content = read_file(log)
        daily_sections.append(f"### Daily Log — {log.stem}\n\n{content}")

    daily_combined = "\n\n---\n\n".join(daily_sections) if daily_sections else "<!-- No daily logs found -->"

    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")

    context = f"""# Session Context — {timestamp}

## SOUL
{soul}

## USER
{user}

## MEMORY
{memory}

## Recent Daily Logs
{daily_combined}
"""
    return context


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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(build_context())

    # Append session start marker to daily log
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")
    daily_file = ensure_daily_file(today)
    timestamp = now.strftime("%H:%M IST")
    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Session Start — {timestamp}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
