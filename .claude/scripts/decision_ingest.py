#!/usr/bin/env python3
"""Ingest **Decision:** tags from the Second Brain vault and emit structured JSON."""

import argparse
import json
import hashlib
import os
import re
import glob
import sys
from datetime import datetime, timedelta

# Reuse project root relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
MEMORY_ROOT = os.path.join(PROJECT_ROOT, "Memory")


def _extract_project_tag_from_context(content: str, match_start: int) -> str:
    """Look backward from match position for a markdown heading to infer project tag."""
    lines = content[:match_start].split("\n")
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading.lower() in ("key decisions", "decisions", "decision log"):
                continue
            return re.sub(r"[^a-z0-9-]", "-", heading.lower()).strip("-")
    return "general"


def extract_decisions_from_file(filepath: str, source_label: str) -> list:
    """Parse **Decision:** and **Key Decision:** tags from a markdown file."""
    decisions = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return decisions

    # Match **Decision:** or **Key Decision:** — capture until next bold tag, heading, or list boundary
    pattern = re.compile(
        r"\*\*(?:Key\s+)?Decision:\*\*\s*(.+?)(?=\n\s*\*\*|\n\s*#{1,6}\s|\n\s*[-*]\s+\*\*|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    for match in pattern.finditer(content):
        text = match.group(1).strip()
        if not text or len(text) < 10:
            continue

        decision_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        project_tag = _extract_project_tag_from_context(content, match.start())

        # MEMORY.md is a global file — decisions there apply to all projects
        if os.path.basename(filepath).lower() == "memory.md":
            project_tag = "general"

        # Try to extract an explicit date from nearby text
        date_str = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d")
        date_nearby = re.search(r"(\d{4}-\d{2}-\d{2})", content[max(0, match.start() - 200):match.start()])
        if date_nearby:
            date_str = date_nearby.group(1)

        decisions.append({
            "id": decision_hash[:12],
            "text": text,
            "date": date_str,
            "source_file": os.path.relpath(filepath, PROJECT_ROOT),
            "source_label": source_label,
            "project_tag": project_tag,
            "decision_hash": decision_hash,
        })

    return decisions


def main():
    parser = argparse.ArgumentParser(description="Ingest decisions from Second Brain vault")
    parser.add_argument("--days", type=int, default=30, help="Look back N days for daily logs")
    parser.add_argument("--sources", default="daily,memory,projects", help="Comma-separated sources")
    parser.add_argument("--output", required=True, help="Path to write decisions JSON")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(days=args.days)
    sources = [s.strip() for s in args.sources.split(",")]
    all_decisions = []

    # 1. Daily logs
    if "daily" in sources:
        daily_dir = os.path.join(MEMORY_ROOT, "daily")
        if os.path.isdir(daily_dir):
            for filepath in glob.glob(os.path.join(daily_dir, "*.md")):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                except OSError:
                    continue
                if mtime >= cutoff:
                    all_decisions.extend(extract_decisions_from_file(filepath, "daily"))

    # 2. MEMORY.md Key Decisions section
    if "memory" in sources:
        memory_file = os.path.join(MEMORY_ROOT, "MEMORY.md")
        if os.path.exists(memory_file):
            all_decisions.extend(extract_decisions_from_file(memory_file, "memory"))

    # 3. Project status files
    if "projects" in sources:
        projects_dir = os.path.join(MEMORY_ROOT, "projects")
        if os.path.isdir(projects_dir):
            for root, _dirs, files in os.walk(projects_dir):
                for file in files:
                    if file.endswith(".md"):
                        filepath = os.path.join(root, file)
                        all_decisions.extend(extract_decisions_from_file(filepath, "projects"))

    # Deduplicate by hash
    seen = set()
    unique = []
    for d in all_decisions:
        if d["decision_hash"] not in seen:
            seen.add(d["decision_hash"])
            unique.append(d)

    # Sort by date descending
    unique.sort(key=lambda x: x["date"], reverse=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Ingested {len(unique)} unique decisions from {len(sources)} source(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
