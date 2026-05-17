#!/usr/bin/env python3
"""
Daily Memory Reflection — promotes key items from yesterday's daily log to MEMORY.md.

Runs daily at 8:00 AM IST (intended for Task Scheduler / cron).
Reviews yesterday's log, extracts decisions/lessons/facts, and updates MEMORY.md.
Archives yesterday's habit checklist in HABITS.md.

Usage:
    python .claude/scripts/memory_reflect.py              # normal run
    python .claude/scripts/memory_reflect.py --preview   # show changes, no writes
    python .claude/scripts/memory_reflect.py --llm       # use LLM for promotion decisions
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from llm_client import LLMClient  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))

DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
MEMORY_MD = PROJECT_ROOT / "Memory" / "MEMORY.md"
HABITS_MD = PROJECT_ROOT / "Memory" / "HABITS.md"


class MemoryReflect:
    def __init__(self, dry_run: bool = False, use_llm: bool = False):
        self.dry_run = dry_run
        self.use_llm = use_llm
        self.llm: Optional[LLMClient] = None
        if use_llm:
            try:
                self.llm = LLMClient()
            except RuntimeError as e:
                print(f"[reflect] LLM not available: {e}", file=sys.stderr)
                self.use_llm = False

    def _load_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _write_file(self, path: Path, content: str) -> None:
        if self.dry_run:
            return
        path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def extract_items(self, log_content: str) -> dict[str, list[str]]:
        """Extract categorized items from a daily log."""
        items: dict[str, list[str]] = {
            "Decisions": [],
            "Action Items": [],
            "Lessons": [],
            "Key Facts": [],
        }

        # Look for explicit tags anywhere in the log
        tag_patterns = {
            "Decisions": r"\*\*Decision:\*\*\s*(.+?)(?=\n|$)",
            "Action Items": r"\*\*Action Item:\*\*\s*(.+?)(?=\n|$)",
            "Lessons": r"\*\*Lesson:\*\*\s*(.+?)(?=\n|$)",
            "Key Facts": r"\*\*Key Fact:\*\*\s*(.+?)(?=\n|$)",
        }

        for category, pattern in tag_patterns.items():
            for match in re.finditer(pattern, log_content, re.IGNORECASE):
                text = match.group(1).strip()
                if text and text not in items[category]:
                    items[category].append(text)

        # Also look for ### Category blocks (from shared_extract.py format)
        section_pattern = r"###\s*(Decisions|Action Items|Lessons|Key Facts|Plans|File Changes|Tasks)\n((?:- .+\n)+)"
        for match in re.finditer(section_pattern, log_content, re.IGNORECASE):
            category = match.group(1)
            block = match.group(2)
            # Map some categories
            if category in ("Plans", "File Changes", "Tasks"):
                category = "Key Facts"
            if category not in items:
                continue
            for line in block.strip().splitlines():
                line = line.lstrip("- ").strip()
                if line and line not in items[category]:
                    items[category].append(line)

        return items

    # ------------------------------------------------------------------
    # LLM Promotion
    # ------------------------------------------------------------------
    def _build_promotion_prompt(self, items: dict[str, list[str]], memory_content: str) -> str:
        parts = [
            "You are a memory curator. Your job is to review yesterday's activity "
            "and decide what should be promoted to the long-term MEMORY.md file.",
            "\n## Current MEMORY.md\n",
            memory_content[:1200],
            "\n## Yesterday's Extracted Items\n",
        ]
        for category, entries in items.items():
            if entries:
                parts.append(f"\n### {category}\n")
                for e in entries[:10]:
                    parts.append(f"- {e}")
        parts.append(
            "\n## Instructions\n"
            "Return ONLY this JSON structure (no markdown fences):\n"
            '{"promote_decisions":["..."], "promote_lessons":["..."], "promote_facts":["..."], '
            '"update_projects":{"Project Name":"New Status"}}'
        )
        return "\n".join(parts)

    def _parse_promotion_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "promote_decisions": [],
                "promote_lessons": [],
                "promote_facts": [],
                "update_projects": {},
            }

    def llm_promote(self, items: dict[str, list[str]], memory_content: str) -> dict[str, Any]:
        if not self.use_llm or not self.llm:
            return {
                "promote_decisions": items.get("Decisions", []),
                "promote_lessons": items.get("Lessons", []),
                "promote_facts": items.get("Key Facts", []),
                "update_projects": {},
            }
        prompt = self._build_promotion_prompt(items, memory_content)
        try:
            response = self.llm.complete(prompt, max_tokens=1024)
            return self._parse_promotion_json(response)
        except Exception as e:
            print(f"[reflect] LLM promotion failed: {e}", file=sys.stderr)
            return {
                "promote_decisions": items.get("Decisions", []),
                "promote_lessons": items.get("Lessons", []),
                "promote_facts": items.get("Key Facts", []),
                "update_projects": {},
            }

    # ------------------------------------------------------------------
    # MEMORY.md Updates
    # ------------------------------------------------------------------
    def _append_to_section(self, content: str, section: str, new_lines: list[str]) -> str:
        if not new_lines:
            return content
        # Find section header like ## Key Decisions
        pattern = rf"(##\s*{re.escape(section)}\s*\n)"
        match = re.search(pattern, content)
        if not match:
            return content

        insert_pos = match.end()
        block = "\n".join(f"- {line}" for line in new_lines) + "\n"
        return content[:insert_pos] + block + content[insert_pos:]

    def _update_projects_table(self, content: str, updates: dict[str, str]) -> str:
        if not updates:
            return content
        # Find ## Active Projects table and update matching rows
        for project, status in updates.items():
            # Simple row replacement heuristic
            pattern = rf"(\|\s*{re.escape(project)}\s*\|\s*)[^|\n]+"
            replacement = rf"\1{status}"
            content = re.sub(pattern, replacement, content, count=1)
        return content

    def update_memory(self, promotion: dict[str, Any]) -> None:
        content = self._load_file(MEMORY_MD)
        if not content:
            print("[reflect] MEMORY.md not found, skipping.", file=sys.stderr)
            return

        content = self._append_to_section(content, "Key Decisions", promotion.get("promote_decisions", []))
        content = self._append_to_section(content, "Lessons Learned", promotion.get("promote_lessons", []))
        content = self._append_to_section(content, "Important Facts", promotion.get("promote_facts", []))
        content = self._update_projects_table(content, promotion.get("update_projects", {}))

        if not self.dry_run:
            self._write_file(MEMORY_MD, content)
            print(f"[reflect] Updated {MEMORY_MD}")
        else:
            print("[reflect] [PREVIEW] Proposed MEMORY.md changes:")
            print(f"  - Decisions: {len(promotion.get('promote_decisions', []))}")
            print(f"  - Lessons: {len(promotion.get('promote_lessons', []))}")
            print(f"  - Facts: {len(promotion.get('promote_facts', []))}")
            print(f"  - Project updates: {promotion.get('update_projects', {})}")

    # ------------------------------------------------------------------
    # HABITS.md Archive
    # ------------------------------------------------------------------
    def archive_habits(self, yesterday: str) -> None:
        if not HABITS_MD.exists():
            return
        content = HABITS_MD.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Extract current checkbox states from Pillars section
        checkboxes: list[tuple[str, bool]] = []
        in_pillars = False
        for line in lines:
            stripped = line.strip()
            if stripped == "## Pillars":
                in_pillars = True
                continue
            if in_pillars and stripped.startswith("## "):
                in_pillars = False
            if in_pillars and stripped.startswith("- ["):
                checked = stripped.startswith("- [x]")
                # Extract pillar name between **
                m = re.search(r"\*\*([^*]+)\*\*", stripped)
                if m:
                    checkboxes.append((m.group(1), checked))

        # Build archive entry
        archive_entry = f"\n### {yesterday}\n"
        for pillar, checked in checkboxes:
            status = "✅" if checked else "❌"
            archive_entry += f"- {status} {pillar}\n"

        # Insert into History section
        history_marker = "## History"
        idx = content.find(history_marker)
        if idx != -1:
            insert_pos = idx + len(history_marker)
            # Skip to end of line
            while insert_pos < len(content) and content[insert_pos] != "\n":
                insert_pos += 1
            insert_pos += 1  # after newline
            content = content[:insert_pos] + archive_entry + content[insert_pos:]

        # Reset checkboxes
        for i, line in enumerate(lines):
            if line.strip().startswith("- [x]"):
                lines[i] = line.replace("- [x]", "- [ ]", 1)
        content = "\n".join(lines) + "\n"

        # Update date
        content = re.sub(
            r"# Daily Habits — \d{4}-\d{2}-\d{2}",
            f"# Daily Habits — {datetime.now(IST).strftime('%Y-%m-%d')}",
            content,
        )

        if not self.dry_run:
            self._write_file(HABITS_MD, content)
            print(f"[reflect] Archived habits for {yesterday} and reset checkboxes.")
        else:
            print(f"[reflect] [PREVIEW] Would archive {len(checkboxes)} habits for {yesterday}.")

    # ------------------------------------------------------------------
    # Main Run
    # ------------------------------------------------------------------
    def run(self) -> None:
        now = datetime.now(IST)
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        daily_file = DAILY_DIR / f"{yesterday}.md"

        print(f"[reflect] Reviewing {daily_file.name}")

        if not daily_file.exists():
            print(f"[reflect] No daily log found for {yesterday}. Nothing to reflect on.")
            return

        log_content = daily_file.read_text(encoding="utf-8")
        items = self.extract_items(log_content)
        total = sum(len(v) for v in items.values())
        print(f"[reflect] Extracted {total} items: { {k: len(v) for k, v in items.items()} }")

        memory_content = self._load_file(MEMORY_MD)
        promotion = self.llm_promote(items, memory_content)

        self.update_memory(promotion)
        self.archive_habits(yesterday)
        print("[reflect] Done.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Daily Memory Reflection")
    parser.add_argument("--preview", action="store_true", help="Show changes without writing")
    parser.add_argument("--llm", action="store_true", help="Use LLM for promotion decisions")
    args = parser.parse_args()

    reflector = MemoryReflect(dry_run=args.preview, use_llm=args.llm)
    reflector.run()


if __name__ == "__main__":
    main()
