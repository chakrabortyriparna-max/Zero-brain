"""Helper to summarize Slack channel history.

Usage:
    python summarize.py C0B0HTS2EA0 --hours 24 --output Memory/meetings/2026-05-13_slack-social.md
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))


def fetch_history(channel_id: str, hours: int) -> str:
    """Fetch Slack history via the integration CLI."""
    cmd = [
        "python",
        ".claude/scripts/integrations/query.py",
        "slack",
        "history",
        channel_id,
    ]
    if hours > 0:
        oldest = datetime.now(IST) - timedelta(hours=hours)
        oldest_ts = str(oldest.timestamp())
        cmd.extend(["--oldest", oldest_ts])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception as e:
        return f"Error fetching history: {e}"


def main():
    parser = argparse.ArgumentParser(description="Summarize Slack channel history.")
    parser.add_argument("channel_id", help="Slack channel ID (e.g. C0B0HTS2EA0)")
    parser.add_argument("--hours", type=int, default=24, help="Hours back to scan")
    parser.add_argument("--output", type=Path, help="Output markdown file path")
    args = parser.parse_args()

    history = fetch_history(args.channel_id, args.hours)
    print(history)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(history, encoding="utf-8")
        print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
