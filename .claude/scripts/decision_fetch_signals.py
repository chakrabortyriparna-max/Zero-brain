#!/usr/bin/env python3
"""Fetch GitHub commits / Slack messages as signals for decision drift analysis."""

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
QUERY_PY = os.path.join(SCRIPT_DIR, "integrations", "query.py")
DEFAULT_MAPPING = os.path.join(PROJECT_ROOT, ".claude", "data", "decision-mapping.json")


def _run_query(*cmd_args) -> str:
    """Invoke the existing query.py integration CLI."""
    cmd = [sys.executable, QUERY_PY] + list(cmd_args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return json.dumps({"error": e.stderr or str(e)})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "timeout"})


def fetch_github(repo: str, days: int) -> dict:
    """Fetch recent commits for a repo."""
    raw = _run_query("github", "commits", repo, "--limit", "30")
    return {
        "source": "github",
        "repo": repo,
        "days": days,
        "raw": raw,
    }


def fetch_slack(channel: str, days: int) -> dict:
    """Fetch recent Slack history for a channel."""
    # query.py slack history expects --oldest as a timestamp; approximate
    from datetime import datetime, timedelta
    oldest_ts = (datetime.now() - timedelta(days=days)).timestamp()
    raw = _run_query("slack", "history", channel, "--oldest", str(int(oldest_ts)))
    return {
        "source": "slack",
        "channel": channel,
        "days": days,
        "raw": raw,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch decision signals from GitHub or Slack")
    parser.add_argument("--source", choices=["github", "slack"], required=True)
    parser.add_argument("--decisions", required=True, help="Path to decisions JSON")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mapping", default=DEFAULT_MAPPING, help="Project tag → repo/channel mapping JSON")
    args = parser.parse_args()

    with open(args.decisions, "r", encoding="utf-8") as f:
        decisions = json.load(f)

    mapping = {}
    if os.path.exists(args.mapping):
        with open(args.mapping, "r", encoding="utf-8") as f:
            mapping = json.load(f)

    signals = []

    if args.source == "github":
        repos = set()
        for d in decisions:
            tag = d.get("project_tag", "general")
            if tag in mapping and "github" in mapping[tag]:
                repos.add(mapping[tag]["github"])
            elif "/" in tag and len(tag.split("/")) == 2:
                # Infer owner/repo from kebab-case if it looks like one
                repos.add(tag)

        for repo in sorted(repos):
            signals.append(fetch_github(repo, args.days))

    elif args.source == "slack":
        channels = set()
        for d in decisions:
            tag = d.get("project_tag", "general")
            if tag in mapping and "slack" in mapping[tag]:
                channels.add(mapping[tag]["slack"])

        for channel in sorted(channels):
            signals.append(fetch_slack(channel, args.days))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)

    print(f"Fetched {len(signals)} {args.source} signal group(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
