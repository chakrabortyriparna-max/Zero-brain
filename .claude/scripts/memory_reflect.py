#!/usr/bin/env python3
"""
Daily Memory Reflection — promotes key items from yesterday's daily log to MEMORY.md.

Runs daily at 8:00 AM IST (intended for Task Scheduler / cron).
Reviews yesterday's log, extracts decisions/lessons/facts, and updates MEMORY.md.
Archives yesterday's habit checklist in HABITS.md.

Features:
  - Idempotency: skips if already reflected for a given date
  - Deduplication: won't add the same item twice to MEMORY.md
  - LLM retry + fallback for promotion decisions

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
from file_utils import atomic_write, locked_open, safe_load_json  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))

DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
MEMORY_MD = PROJECT_ROOT / "Memory" / "MEMORY.md"
HABITS_MD = PROJECT_ROOT / "Memory" / "HABITS.md"
STATE_FILE = PROJECT_ROOT / ".claude" / "data" / "state" / "reflect-state.json"
CONFIG_FILE = PROJECT_ROOT / ".claude" / "config" / "heartbeat.json"


def _load_config() -> dict:
    defaults = {
        "llm_backend": "auto",
        "llm_fallback": True,
    }
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            defaults.update(loaded)
        except Exception:
            pass
    return defaults


class MemoryReflect:
    def __init__(self, dry_run: bool = False, use_llm: bool = False):
        self.dry_run = dry_run
        self.config = _load_config()
        self.use_llm = use_llm
        self.llm: Optional[LLMClient] = None
        self.errors: list[str] = []
        if use_llm:
            try:
                backend = self.config.get("llm_backend", "auto")
                self.llm = LLMClient(backend=None if backend == "auto" else backend)
            except RuntimeError as e:
                self._error(f"LLM not available: {e}")
                self.use_llm = False

    def _error(self, msg: str) -> None:
        self.errors.append(msg)
        print(f"[reflect] {msg}", file=sys.stderr)

    def _load_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _write_file(self, path: Path, content: str) -> None:
        if self.dry_run:
            return
        atomic_write(path, content)

    def _load_reflect_state(self) -> dict:
        return safe_load_json(STATE_FILE, default={})

    def _save_reflect_state(self, data: dict) -> None:
        if self.dry_run:
            return
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            from file_utils import atomic_write_json
            atomic_write_json(STATE_FILE, data)
        except Exception as e:
            self._error(f"Failed to save reflect state: {e}")

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

        section_pattern = r"###\s*(Decisions|Action Items|Lessons|Key Facts|Plans|File Changes|Tasks)\n((?:- .+\n)+)"
        for match in re.finditer(section_pattern, log_content, re.IGNORECASE):
            category = match.group(1)
            block = match.group(2)
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
            if self.config.get("llm_fallback", True):
                response = self.llm.complete_with_fallback(prompt, max_tokens=1024)
            else:
                response = self.llm.complete(prompt, max_tokens=1024)
            return self._parse_promotion_json(response)
        except Exception as e:
            self._error(f"LLM promotion failed: {e}")
            return {
                "promote_decisions": items.get("Decisions", []),
                "promote_lessons": items.get("Lessons", []),
                "promote_facts": items.get("Key Facts", []),
                "update_projects": {},
            }

    # ------------------------------------------------------------------
    # MEMORY.md Updates
    # ------------------------------------------------------------------
    def _normalize_item(self, text: str) -> str:
        """Normalize for deduplication comparison."""
        return re.sub(r"[^\w]", "", text.lower())

    def _section_existing_items(self, content: str, section: str) -> set[str]:
        """Return set of normalized existing items in a section."""
        existing: set[str] = set()
        # Find section and extract bullet items until next ##
        pattern = rf"##\s*{re.escape(section)}\s*\n"
        match = re.search(pattern, content)
        if not match:
            return existing
        start = match.end()
        # Find end of section (next ## or end of file)
        next_header = re.search(r"\n##\s", content[start:])
        end = start + next_header.start() if next_header else len(content)
        section_text = content[start:end]
        for line in section_text.splitlines():
            stripped = line.strip().lstrip("- ")
            if stripped:
                existing.add(self._normalize_item(stripped))
        return existing

    def _append_to_section(self, content: str, section: str, new_lines: list[str]) -> str:
        if not new_lines:
            return content
        existing = self._section_existing_items(content, section)
        unique_lines = [line for line in new_lines if self._normalize_item(line) not in existing]
        if not unique_lines:
            return content
        pattern = rf"(##\s*{re.escape(section)}\s*\n)"
        match = re.search(pattern, content)
        if not match:
            return content

        insert_pos = match.end()
        block = "\n".join(f"- {line}" for line in unique_lines) + "\n"
        return content[:insert_pos] + block + content[insert_pos:]

    def _update_projects_table(self, content: str, updates: dict[str, str]) -> str:
        if not updates:
            return content
        for project, status in updates.items():
            marker = f"| {project} |"
            for line in content.splitlines():
                if marker in line:
                    parts = line.split("|")
                    for i, part in enumerate(parts):
                        if part.strip() == project and i + 1 < len(parts):
                            parts[i + 1] = f" {status} "
                            new_line = "|".join(parts)
                            content = content.replace(line, new_line)
                            break
        return content

    def update_memory(self, promotion: dict[str, Any]) -> None:
        content = self._load_file(MEMORY_MD)
        if not content:
            self._error("MEMORY.md not found, skipping.")
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
                m = re.search(r"\*\*([^*]+)\*\*", stripped)
                if m:
                    checkboxes.append((m.group(1), checked))

        # Build archive entry
        archive_entry = f"\n### {yesterday}\n"
        for pillar, checked in checkboxes:
            status = "✅" if checked else "❌"
            archive_entry += f"- {status} {pillar}\n"

        # Insert into History section
        for i, line in enumerate(lines):
            if line.strip() == "## History":
                lines.insert(i + 1, archive_entry.strip())
                break

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

        # Idempotency check
        state = self._load_reflect_state()
        if state.get("last_reflected") == yesterday:
            print(f"[reflect] Already reflected on {yesterday}. Skipping.")
            return

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

        # Cognee consolidation: push promoted items into graph for self-improvement
        promoted = (
            promotion.get("promote_decisions", [])
            + promotion.get("promote_lessons", [])
            + promotion.get("promote_facts", [])
        )
        if promoted:
            asyncio.run(self._cognee_consolidate(promoted))

        # Save state
        state["last_reflected"] = yesterday
        self._save_reflect_state(state)

        if self.errors:
            print(f"[reflect] Completed with {len(self.errors)} errors.")
        else:
            print("[reflect] Done.")

    async def _cognee_consolidate(self, items: list[str]) -> None:
        """Push promoted items into Cognee graph for self-improvement."""
        try:
            from cognee_memory import create_memory
            mem = create_memory()
            text = "\n".join(items)
            await mem.ingest_text(text, source="memory_reflect")
            await mem.memify()
            print(f"[reflect] Cognee memify() completed for {len(items)} items.")
        except Exception as exc:
            self._error(f"Cognee consolidation failed: {exc}")


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
