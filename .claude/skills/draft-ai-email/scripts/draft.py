"""Helper to draft an AI-related email in Riparna's voice.

Usage:
    python draft.py "Reply to the team about the LoRA results" \
        --recipient team@example.com \
        --subject "LoRA Fine-Tuning Results" \
        --context "We achieved 95% accuracy with QLoRA on the benchmark."

The script searches Memory/drafts/sent/ for tone-matching examples,
composes a draft, and saves it to Memory/drafts/active/.
"""

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
MEMORY_ROOT = Path("Memory")
DRAFTS_ACTIVE = MEMORY_ROOT / "drafts" / "active"
DRAFTS_SENT = MEMORY_ROOT / "drafts" / "sent"


def _slugify(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def _find_voice_examples(topic: str, top_k: int = 5) -> str:
    """Search sent drafts for tone-matching examples."""
    cmd = [
        "python",
        ".claude/scripts/memory_search.py",
        topic,
        "--path-prefix",
        str(DRAFTS_SENT),
        "--top-k",
        str(top_k),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception:
        return ""


def _compose_draft(recipient: str, subject: str, context: str, voice_examples: str) -> str:
    """Build the markdown draft with frontmatter."""
    now = datetime.now(IST).isoformat()
    slug = _slugify(subject)

    body = f"""---
type: email
source_id: pending
recipient: {recipient}
subject: {subject}
context: {context}
created: {now}
status: active
---

# Draft: {subject}

**To:** {recipient}
**Subject:** {subject}
**Context:** {context}

---

[Compose your reply here. Match Riparna's voice: technical, concise, action-oriented.]

Best,
Riparna

---

## Voice-Matching Examples

{voice_examples if voice_examples else "_No sent drafts found for this topic._"}
"""
    return body


def main():
    parser = argparse.ArgumentParser(description="Draft an email in Riparna's voice.")
    parser.add_argument("topic", help="Brief topic or instruction for the draft")
    parser.add_argument("--recipient", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--context", default="", help="Additional context or original email text")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output file path",
    )
    args = parser.parse_args()

    DRAFTS_ACTIVE.mkdir(parents=True, exist_ok=True)

    voice = _find_voice_examples(args.topic)
    draft_md = _compose_draft(args.recipient, args.subject, args.context, voice)

    now = datetime.now(IST)
    slug = _slugify(args.subject)
    filename = f"{now.strftime('%Y-%m-%d')}_email_{slug}.md"
    out_path = args.output or (DRAFTS_ACTIVE / filename)

    out_path.write_text(draft_md, encoding="utf-8")
    print(f"Draft saved to: {out_path}")


if __name__ == "__main__":
    main()
