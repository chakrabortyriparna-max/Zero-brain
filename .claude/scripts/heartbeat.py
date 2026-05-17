#!/usr/bin/env python3
"""
Second Brain Heartbeat — proactive monitoring daemon.

Polls Gmail, Slack, and GitHub every run, diffs against the previous snapshot,
auto-detects habits, optionally drafts replies via LLM, and logs activity.

Usage:
    python .claude/scripts/heartbeat.py              # normal run
    python .claude/scripts/heartbeat.py --llm          # enable LLM drafting
    python .claude/scripts/heartbeat.py --dry-run      # gather only, no writes
    python .claude/scripts/heartbeat.py --force        # run even if no changes
    python .claude/scripts/heartbeat.py --notify       # send Windows toast
"""
import argparse
import json
import os
import re
import sys
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from llm_client import LLMClient  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))

STATE_FILE = PROJECT_ROOT / ".claude" / "data" / "state" / "heartbeat-state.json"
DAILY_DIR = PROJECT_ROOT / "Memory" / "daily"
DRAFTS_ACTIVE = PROJECT_ROOT / "Memory" / "drafts" / "active"
DRAFTS_EXPIRED = PROJECT_ROOT / "Memory" / "drafts" / "expired"
SOUL_MD = PROJECT_ROOT / "Memory" / "SOUL.md"
USER_MD = PROJECT_ROOT / "Memory" / "USER.md"
HABITS_MD = PROJECT_ROOT / "Memory" / "HABITS.md"

# Configurable via USER.md or env
SLACK_USER_ID = os.environ.get("SLACK_USER_ID", "")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "")
GITHUB_MAIN_REPO = os.environ.get("GITHUB_MAIN_REPO", "")

DRAFT_EXPIRY_HOURS = 24


@dataclass
class Snapshot:
    """Capture of external state at a point in time."""
    timestamp: str
    gmail_unread: list[dict] = field(default_factory=list)
    github_notifications: list[dict] = field(default_factory=list)
    slack_activity: dict[str, list[dict]] = field(default_factory=dict)
    github_commits: dict[str, list[dict]] = field(default_factory=dict)
    habits_status: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "gmail_unread": self.gmail_unread,
            "github_notifications": self.github_notifications,
            "slack_activity": self.slack_activity,
            "github_commits": self.github_commits,
            "habits_status": self.habits_status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Snapshot":
        return cls(
            timestamp=d.get("timestamp", ""),
            gmail_unread=d.get("gmail_unread", []),
            github_notifications=d.get("github_notifications", []),
            slack_activity=d.get("slack_activity", {}),
            github_commits=d.get("github_commits", {}),
            habits_status=d.get("habits_status", {}),
        )


class HeartbeatRunner:
    def __init__(self, dry_run: bool = False, use_llm: bool = False, notify: bool = False):
        self.dry_run = dry_run
        self.use_llm = use_llm
        self.notify = notify
        self.llm: Optional[LLMClient] = None
        if use_llm:
            try:
                self.llm = LLMClient()
            except RuntimeError as e:
                print(f"[heartbeat] LLM not available: {e}", file=sys.stderr)
                self.use_llm = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_dirs(self) -> None:
        DAILY_DIR.mkdir(parents=True, exist_ok=True)
        DRAFTS_ACTIVE.mkdir(parents=True, exist_ok=True)
        DRAFTS_EXPIRED.mkdir(parents=True, exist_ok=True)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Snapshot:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                return Snapshot.from_dict(data)
            except Exception:
                pass
        # Empty baseline
        return Snapshot(timestamp="", gmail_unread=[], github_notifications=[], slack_activity={}, github_commits={})

    def _save_state(self, snapshot: Snapshot) -> None:
        if self.dry_run:
            return
        try:
            STATE_FILE.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[heartbeat] Failed to save state: {e}", file=sys.stderr)

    def _ensure_daily_file(self, date_str: str) -> Path:
        daily_file = DAILY_DIR / f"{date_str}.md"
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

    def _load_markdown(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^\w\-]", "_", text.lower().strip())[:40]

    # ------------------------------------------------------------------
    # Gather Phase
    # ------------------------------------------------------------------
    def _gather_gmail(self) -> list[dict]:
        try:
            from integrations import gmail_integration as gmail
            msgs = gmail.list_unread(max_results=20)
            return [
                {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "subject": m.subject,
                    "from_addr": m.from_addr,
                    "snippet": m.snippet,
                    "body_text": m.body_text[:800],
                }
                for m in msgs
            ]
        except Exception as e:
            print(f"[heartbeat] Gmail gather failed: {e}", file=sys.stderr)
            return []

    def _gather_github_notifications(self) -> list[dict]:
        try:
            from integrations import github_integration as gh
            notifs = gh.list_notifications()
            return [
                {
                    "id": n.id,
                    "title": n.title,
                    "type": n.type,
                    "repo": n.repo,
                    "reason": n.reason,
                    "unread": n.unread,
                }
                for n in notifs
            ]
        except Exception as e:
            print(f"[heartbeat] GitHub gather failed: {e}", file=sys.stderr)
            return []

    def _gather_github_commits(self, repo_name: Optional[str] = None) -> dict[str, list[dict]]:
        repo = repo_name or GITHUB_MAIN_REPO
        if not repo:
            return {}
        try:
            from integrations import github_integration as gh
            commits = gh.list_commits(repo, limit=20)
            return {
                repo: [
                    {"sha": c.sha, "message": c.message, "author": c.author, "date": c.date}
                    for c in commits
                ]
            }
        except Exception as e:
            print(f"[heartbeat] GitHub commits gather failed: {e}", file=sys.stderr)
            return {}

    def _gather_slack_activity(self) -> dict[str, list[dict]]:
        try:
            from integrations import slack_integration as slack
            channels = slack.list_channels()
            out: dict[str, list[dict]] = {}
            # Load previous timestamp per channel from state
            previous = self._load_state()
            prev_slack = previous.slack_activity if previous else {}

            for ch in channels:
                if ch.is_private:
                    continue
                oldest = None
                if ch.name in prev_slack and prev_slack[ch.name]:
                    oldest = prev_slack[ch.name][-1]["ts"]
                msgs = slack.get_history(ch.id, oldest_ts=oldest, limit=50)
                if msgs:
                    out[ch.name] = [
                        {"ts": m.ts, "user": m.user, "text": m.text[:400]}
                        for m in msgs
                    ]
            return out
        except Exception as e:
            print(f"[heartbeat] Slack gather failed: {e}", file=sys.stderr)
            return {}

    def build_snapshot(self) -> Snapshot:
        now = datetime.now(IST).isoformat()
        snapshot = Snapshot(
            timestamp=now,
            gmail_unread=self._gather_gmail(),
            github_notifications=self._gather_github_notifications(),
            slack_activity=self._gather_slack_activity(),
            github_commits=self._gather_github_commits(),
        )
        return snapshot

    # ------------------------------------------------------------------
    # Diff Phase
    # ------------------------------------------------------------------
    def _diff_lists(self, current: list[dict], previous: list[dict], key: str) -> list[dict]:
        prev_ids = {p[key] for p in previous}
        return [c for c in current if c[key] not in prev_ids]

    def compute_diff(self, previous: Snapshot, current: Snapshot) -> dict[str, Any]:
        new_gmail = self._diff_lists(current.gmail_unread, previous.gmail_unread, "id")
        new_github = self._diff_lists(
            current.github_notifications, previous.github_notifications, "id"
        )
        new_slack: dict[str, list[dict]] = {}
        for ch, msgs in current.slack_activity.items():
            prev_msgs = previous.slack_activity.get(ch, [])
            prev_ts = {m["ts"] for m in prev_msgs}
            new_msgs = [m for m in msgs if m["ts"] not in prev_ts]
            if new_msgs:
                new_slack[ch] = new_msgs

        return {
            "new_gmail": new_gmail,
            "new_github": new_github,
            "new_slack": new_slack,
            "has_changes": bool(new_gmail or new_github or new_slack),
        }

    # ------------------------------------------------------------------
    # Habits Phase
    # ------------------------------------------------------------------
    def detect_habits(self, snapshot: Snapshot) -> dict[str, bool]:
        status: dict[str, bool] = {}
        today = datetime.now(IST).strftime("%Y-%m-%d")

        # Main Project: any GitHub commit today?
        main_project = False
        for repo, commits in snapshot.github_commits.items():
            for c in commits:
                date_str = c.get("date", "")[:10]
                if date_str == today:
                    main_project = True
                    break
            if main_project:
                break
        status["Main Project"] = main_project

        # Community: any Slack message from Riparna in public channels?
        community = False
        slack_user = SLACK_USER_ID or ""
        for ch, msgs in snapshot.slack_activity.items():
            for m in msgs:
                if slack_user and m.get("user") == slack_user:
                    community = True
                    break
            if community:
                break
        status["Community"] = community

        return status

    def _update_habits_file(self, status: dict[str, bool]) -> None:
        if self.dry_run:
            return
        if not HABITS_MD.exists():
            return
        content = HABITS_MD.read_text(encoding="utf-8")
        lines = content.splitlines()
        out_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            for pillar, done in status.items():
                if stripped.startswith(f"- [ ] **{pillar}**") and done:
                    line = line.replace("- [ ]", "- [x]")
                elif stripped.startswith(f"- [x] **{pillar}**") and not done:
                    line = line.replace("- [x]", "- [ ]")
            out_lines.append(line)
        HABITS_MD.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Draft Phase
    # ------------------------------------------------------------------
    def _build_llm_prompt(self, diff: dict, soul: str, user: str) -> str:
        parts = [
            "You are Riparna's Second Brain heartbeat. "
            "You monitor her external accounts and identify items needing attention. "
            "You draft email replies and summarize activity. "
            "You NEVER send anything — you only draft for her review.",
            "\n## Personality and Rules",
            soul[:800],
            user[:400],
            "\n## New Unread Emails",
        ]
        if diff["new_gmail"]:
            for m in diff["new_gmail"]:
                parts.append(f"- From: {m['from_addr']} | Subject: {m['subject']}")
                parts.append(f"  Snippet: {m['snippet']}")
        else:
            parts.append("_No new unread emails._")

        parts.append("\n## New GitHub Notifications")
        if diff["new_github"]:
            for n in diff["new_github"]:
                parts.append(f"- [{n['repo']}] {n['title']} ({n['type']}) — reason: {n['reason']}")
        else:
            parts.append("_No new GitHub notifications._")

        parts.append("\n## New Slack Activity")
        if diff["new_slack"]:
            for ch, msgs in diff["new_slack"].items():
                parts.append(f"\n### #{ch}")
                for m in msgs[:5]:
                    parts.append(f"- {m['text'][:200]}")
        else:
            parts.append("_No new Slack activity._")

        parts.append(
            "\n## Instructions\n"
            "1. Identify which emails need a reply. For each, draft a concise, professional reply.\n"
            "2. Summarize Slack activity in 1-2 sentences.\n"
            "3. Flag urgent GitHub notifications.\n"
            "4. Return ONLY the following JSON structure (no markdown fences):\n"
            '{"attention_items":["..."], "email_drafts":[{"recipient":"","subject":"","body":"","source_id":""}], "slack_summary":"", "github_flags":["..."]}'
        )
        return "\n".join(parts)

    def _parse_draft_json(self, text: str) -> dict:
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
                "attention_items": [],
                "email_drafts": [],
                "slack_summary": text[:500],
                "github_flags": [],
            }

    def generate_drafts(self, diff: dict) -> dict:
        if not self.use_llm or not self.llm:
            return {
                "attention_items": [],
                "email_drafts": [],
                "slack_summary": "",
                "github_flags": [],
            }
        soul = self._load_markdown(SOUL_MD)
        user = self._load_markdown(USER_MD)
        prompt = self._build_llm_prompt(diff, soul, user)
        try:
            response = self.llm.complete(prompt, max_tokens=2048)
            return self._parse_draft_json(response)
        except Exception as e:
            print(f"[heartbeat] LLM draft generation failed: {e}", file=sys.stderr)
            return {
                "attention_items": [],
                "email_drafts": [],
                "slack_summary": "",
                "github_flags": [],
            }

    # ------------------------------------------------------------------
    # Draft Persistence
    # ------------------------------------------------------------------
    def _save_email_drafts(self, drafts: list[dict]) -> list[Path]:
        saved: list[Path] = []
        if self.dry_run:
            return saved
        now = datetime.now(IST)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M")
        for d in drafts:
            slug = self._slugify(d.get("subject", "draft"))
            filename = f"{date_str}_{time_str}_email_{slug}.md"
            filepath = DRAFTS_ACTIVE / filename
            body = d.get("body", "")
            frontmatter = (
                f"---\n"
                f"type: email\n"
                f"source_id: {d.get('source_id', '')}\n"
                f"recipient: {d.get('recipient', '')}\n"
                f"subject: {d.get('subject', '')}\n"
                f"context: heartbeat draft\n"
                f"created: {now.isoformat()}\n"
                f"status: active\n"
                f"---\n\n"
                f"{body}\n"
            )
            filepath.write_text(frontmatter, encoding="utf-8")
            saved.append(filepath)
        return saved

    def _expire_old_drafts(self) -> list[Path]:
        """Move drafts older than DRAFT_EXPIRY_HOURS from active to expired."""
        moved: list[Path] = []
        if self.dry_run:
            return moved
        now = datetime.now(IST)
        cutoff = now - timedelta(hours=DRAFT_EXPIRY_HOURS)
        for draft in DRAFTS_ACTIVE.glob("*.md"):
            # Use filename prefix YYYY-MM-DD or file mtime
            try:
                mtime = datetime.fromtimestamp(draft.stat().st_mtime, tz=IST)
                if mtime < cutoff:
                    dest = DRAFTS_EXPIRED / draft.name
                    draft.rename(dest)
                    moved.append(dest)
            except Exception:
                pass
        return moved

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _append_to_daily_log(self, diff: dict, drafts: dict, habits: dict[str, bool]) -> None:
        if self.dry_run:
            return
        now = datetime.now(IST)
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.strftime("%H:%M IST")
        daily_file = self._ensure_daily_file(date_str)

        lines = [
            f"\n## Heartbeat — {timestamp}\n",
            "### New Items\n",
        ]
        lines.append(f"- **Emails:** {len(diff['new_gmail'])} new unread\n")
        lines.append(f"- **GitHub:** {len(diff['new_github'])} new notifications\n")
        slack_total = sum(len(v) for v in diff["new_slack"].values())
        lines.append(f"- **Slack:** {slack_total} new messages\n")

        if diff["new_gmail"]:
            lines.append("\n#### Emails\n")
            for m in diff["new_gmail"][:5]:
                lines.append(f"- *{m['subject']}* from {m['from_addr']}\n")

        if diff["new_github"]:
            lines.append("\n#### GitHub Notifications\n")
            for n in diff["new_github"][:5]:
                lines.append(f"- [{n['repo']}] {n['title']}\n")

        if diff["new_slack"]:
            lines.append("\n#### Slack Activity\n")
            for ch, msgs in diff["new_slack"].items():
                lines.append(f"- #{ch}: {len(msgs)} messages\n")

        if drafts.get("attention_items"):
            lines.append("\n### Attention Items\n")
            for item in drafts["attention_items"]:
                lines.append(f"- {item}\n")

        if drafts.get("slack_summary"):
            lines.append(f"\n### Slack Summary\n{drafts['slack_summary']}\n")

        if drafts.get("github_flags"):
            lines.append("\n### GitHub Flags\n")
            for flag in drafts["github_flags"]:
                lines.append(f"- {flag}\n")

        lines.append("\n### Habits Auto-Detection\n")
        for pillar, done in habits.items():
            status = "✅" if done else "❌"
            lines.append(f"- {status} {pillar}\n")

        if drafts.get("email_drafts"):
            lines.append(f"\n### Drafts Generated\n")
            for d in drafts["email_drafts"]:
                lines.append(f"- Draft: *{d.get('subject', '')}* → `Memory/drafts/active/`\n")

        with open(daily_file, "a", encoding="utf-8") as f:
            f.write("".join(lines))

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _send_notification(self, title: str, message: str) -> None:
        if self.dry_run or not self.notify:
            print(f"[notification] {title}: {message}")
            return
        # Windows toast via PowerShell
        try:
            escaped_msg = message.replace('"', '`"').replace("'", "`'")
            escaped_title = title.replace('"', '`"').replace("'", "`'")
            ps = (
                f'Add-Type -AssemblyName System.Windows.Forms;'
                f'[System.Windows.Forms.MessageBox]::Show("{escaped_msg}", "{escaped_title}")'
            )
            subprocess.run(["powershell.exe", "-Command", ps], capture_output=True, timeout=5)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Main Run
    # ------------------------------------------------------------------
    def run(self, force: bool = False) -> None:
        self._ensure_dirs()
        now = datetime.now(IST)
        print(f"[heartbeat] Run started at {now.isoformat()}")

        # Gather
        current = self.build_snapshot()
        print(f"[heartbeat] Gathered: {len(current.gmail_unread)} emails, "
              f"{len(current.github_notifications)} GitHub notifications, "
              f"{len(current.slack_activity)} Slack channels")

        # Load previous and diff
        previous = self._load_state()
        diff = self.compute_diff(previous, current)
        print(f"[heartbeat] Diff: {len(diff['new_gmail'])} new emails, "
              f"{len(diff['new_github'])} new notifications, "
              f"{sum(len(v) for v in diff['new_slack'].values())} new Slack messages")

        if not diff["has_changes"] and not force:
            print("[heartbeat] No changes detected. Exiting.")
            # Still save state for timestamp update
            self._save_state(current)
            return

        # Habits
        habits = self.detect_habits(current)
        print(f"[heartbeat] Habits: {habits}")

        # Drafts (optional LLM)
        drafts = self.generate_drafts(diff)
        saved_drafts = self._save_email_drafts(drafts.get("email_drafts", []))
        if saved_drafts:
            print(f"[heartbeat] Saved {len(saved_drafts)} drafts to Memory/drafts/active/")

        # Expire old drafts
        expired = self._expire_old_drafts()
        if expired:
            print(f"[heartbeat] Expired {len(expired)} old drafts")

        # Log
        self._append_to_daily_log(diff, drafts, habits)
        self._update_habits_file(habits)

        # Notify for urgent items
        urgent_count = len(drafts.get("attention_items", []))
        if urgent_count > 0 and self.notify:
            self._send_notification(
                "Second Brain Heartbeat",
                f"{urgent_count} items need attention. Check Memory/drafts/active/"
            )

        # Save state
        current.habits_status = habits
        self._save_state(current)
        print("[heartbeat] Run complete.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Second Brain Heartbeat")
    parser.add_argument("--dry-run", action="store_true", help="Gather only, no writes")
    parser.add_argument("--llm", action="store_true", help="Enable LLM drafting")
    parser.add_argument("--force", action="store_true", help="Run even if no changes")
    parser.add_argument("--notify", action="store_true", help="Send Windows toast notifications")
    args = parser.parse_args()

    runner = HeartbeatRunner(
        dry_run=args.dry_run,
        use_llm=args.llm,
        notify=args.notify,
    )
    runner.run(force=args.force)


if __name__ == "__main__":
    main()
