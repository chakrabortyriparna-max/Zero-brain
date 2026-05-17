#!/usr/bin/env python3
"""
Shared extraction logic for PreCompact and SessionEnd hooks.
Parses JSONL transcript entries for both regex-based text insights
and structural heuristics from tool_use blocks.

Transcript schema (Claude Code JSONL):
  {
    "type": "user" | "assistant" | "attachment" | ...,
    "message": {
      "role": "user" | "assistant",
      "content": "raw string" | [
        {"type": "text", "text": "..."},
        {"type": "thinking", "thinking": "..."},
        {"type": "tool_use", "name": "...", "input": {...}},
        {"type": "tool_result", "content": "..." | [...]}
      ]
    },
    ...
  }
"""
import re
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns for literal / natural-language phrases in conversation text
# Order matters: more specific patterns first.
# ---------------------------------------------------------------------------

def _clean_match(raw: str) -> str:
    """Post-process a regex capture: strip, truncate at sentence boundary, limit length."""
    text = raw.strip()
    # Truncate at first sentence-ending punctuation followed by space or end
    m = re.search(r"[.!?](?:\s|$)", text)
    if m:
        text = text[: m.end() - 1]
    # Hard cap
    if len(text) > 200:
        text = text[:200].rsplit(" ", 1)[0] + "..."
    # Minimum meaningful length
    if len(text) < 5:
        return ""
    return text


TEXT_PATTERNS = [
    # Explicit tags (assistant-protocol friendly)
    (r"(?i)\*\*Decision:\*\*\s*(.+?)(?:\n|$)", "Decision"),
    (r"(?i)\*\*Action Item:\*\*\s*(.+?)(?:\n|$)", "Action Item"),
    (r"(?i)\*\*Lesson:\*\*\s*(.+?)(?:\n|$)", "Lesson"),
    (r"(?i)\*\*Key Fact:\*\*\s*(.+?)(?:\n|$)", "Key Fact"),
    (r"(?i)\*\*Important:\*\*\s*(.+?)(?:\n|$)", "Important"),
    (r"(?i)\*\*Next Step:\*\*\s*(.+?)(?:\n|$)", "Next Step"),
    (r"(?i)\*\*Follow-up:\*\*\s*(.+?)(?:\n|$)", "Follow-up"),
    # Natural-language decisions — with word boundaries and non-greedy capture
    (r"(?i)\b(?:we |I |you |they )(?:decided to|decided that|have decided to|have decided that)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\b(?:we |I |you |they )(?:concluded that|conclude that)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\b(?:we |I |you |they )(?:agreed to|agree that|agreed that)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\b(?:we |I |you |they )(?:resolved to|resolve that)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\b(?:we |I |you |they )(?:will|won['\u2019]t|will not)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\blet['\u2019]s\s+(?:do|implement|skip|use|go with|move to|switch to)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    (r"(?i)\b(?:we |I |you )should\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    # Plan / approval
    (r"(?i)\b(?:plan |approach |design )?(?:looks good|approved|proceed with|go ahead with|moving forward with)\b\s*(.+?)(?:[.!?](?:\s|$)|\n|$)", "Decision"),
    # Action items
    (r"(?i)\b(?:action item|todo|task|next step|follow-up|follow up|reminder):?\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Action Item"),
    (r"(?i)\b(?:Riparna|you|we)\s+(?:need to|must|should|will)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Action Item"),
    # Lessons
    (r"(?i)\b(?:lesson learned|key takeaway|insight|realization):?\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Lesson"),
    (r"(?i)\blearned\s+(?:that|from this)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Lesson"),
    # Facts
    (r"(?i)\b(?:key fact|important fact|note to self|note):?\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Key Fact"),
    (r"(?i)\b(?:remember that|keep in mind|don['\u2019]t forget)\s+(.+?)(?:[.!?](?:\s|$)|\n|$)", "Key Fact"),
]

# ---------------------------------------------------------------------------
# Thinking-block filter: only extract thinking blocks that contain
# decision-like keywords, to avoid dumping internal reasoning noise.
# ---------------------------------------------------------------------------

THINKING_KEYWORDS = [
    "decided", "decision", "concluded", "conclusion", "agreed", "agree",
    "resolved", "resolution", "action item", "next step", "follow-up",
    "lesson", "learned", "key fact", "important", "should", "will",
    "won't", "proceed with", "plan approved", "go with",
]


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _extract_text_from_blocks(blocks: Any) -> list[str]:
    """Recursively extract text strings from Claude Code content blocks."""
    texts: list[str] = []
    if isinstance(blocks, str):
        texts.append(blocks)
    elif isinstance(blocks, list):
        for block in blocks:
            texts.extend(_extract_text_from_blocks(block))
    elif isinstance(blocks, dict):
        block_type = blocks.get("type")
        if block_type == "text":
            t = blocks.get("text")
            if isinstance(t, str):
                texts.append(t)
        elif block_type == "thinking":
            # Skip thinking blocks entirely. Important decisions should be
            # stated explicitly in assistant text blocks (per session-capture
            # protocol), not buried in internal reasoning.
            pass
        elif block_type == "tool_result":
            # Skip tool_result blocks to avoid extracting raw file contents,
            # command output, and system reminders. Structural extraction
            # already captures that a tool was used; decisions/action items
            # should come from assistant/user text, not raw tool output.
            pass
        elif block_type == "tool_use":
            # skip tool_use blocks for text extraction (handled structurally)
            pass
        else:
            # Generic dict: recurse into values
            for v in blocks.values():
                texts.extend(_extract_text_from_blocks(v))
    return texts


def _thinking_is_relevant(thinking_text: str) -> bool:
    """Return True if thinking text contains decision-like keywords."""
    lower = thinking_text.lower()
    return any(kw in lower for kw in THINKING_KEYWORDS)


def extract_text_from_entry(entry: dict) -> str:
    """Extract all human-readable text from a transcript entry."""
    texts: list[str] = []

    # Claude Code stores message payload under "message"
    message = entry.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        texts.extend(_extract_text_from_blocks(content))

    # Fallback: some attachment / hook entries have flat "content"
    flat_content = entry.get("content")
    if isinstance(flat_content, str):
        texts.append(flat_content)
    elif isinstance(flat_content, list):
        texts.extend(_extract_text_from_blocks(flat_content))
    elif isinstance(flat_content, dict):
        for v in flat_content.values():
            if isinstance(v, str):
                texts.append(v)

    # Legacy fallbacks
    for key in ("text", "output", "result"):
        val = entry.get(key)
        if isinstance(val, str):
            texts.append(val)

    return "\n".join(texts)


# ---------------------------------------------------------------------------
# Structural insight extraction (tool_use blocks)
# ---------------------------------------------------------------------------

def _find_tool_uses(obj: Any, found: list | None = None) -> list[tuple[str, Any]]:
    """Recursively find tool_use blocks in a transcript entry."""
    if found is None:
        found = []
    if isinstance(obj, dict):
        # Case 1: explicit tool_use block (Claude Code format)
        if obj.get("type") == "tool_use" or "tool_use_id" in obj:
            name = obj.get("name")
            input_data = obj.get("input", obj.get("arguments", {}))
            if name:
                found.append((name, input_data))
            return found
        # Case 2: OpenAI-style function call
        if "function" in obj:
            func = obj["function"]
            if isinstance(func, dict):
                name = func.get("name", obj.get("name"))
                arguments = func.get("arguments", {})
                if name:
                    found.append((name, arguments))
            return found
        # Recurse into values
        for v in obj.values():
            _find_tool_uses(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _find_tool_uses(item, found)
    return found


def _safe_get_str(data: Any, *keys: str) -> str:
    """Safely extract a string value from nested dicts."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in keys:
            val = data.get(key)
            if isinstance(val, str):
                return val
    return ""


def _classify_file_path(path: str) -> str:
    """Classify a file path into a human-readable category."""
    if not path:
        return "File"
    lower = path.lower()
    if "memory/" in lower.replace("\\", "/") or "memory\\" in lower:
        return "Memory"
    if ".claude/" in lower.replace("\\", "/") or ".claude\\" in lower:
        return "Config"
    if any(lower.endswith(ext) for ext in (".py", ".js", ".ts", ".rs", ".go", ".java")):
        return "Code"
    if any(lower.endswith(ext) for ext in (".md", ".txt", ".rst")):
        return "Doc"
    return "File"


def extract_structural_insights(transcript: list[dict]) -> list[tuple[str, str]]:
    """Extract insights from tool_use blocks in the transcript.
    Returns list of (category, insight_text) tuples."""
    insights: list[tuple[str, str]] = []
    seen: set[str] = set()

    for entry in transcript:
        tools = _find_tool_uses(entry)
        for name, input_data in tools:
            insight: str | None = None
            category = "File Changes"

            if name in ("Write", "Edit"):
                file_path = _safe_get_str(input_data, "file_path", "path")
                cls = _classify_file_path(file_path)
                if cls == "Memory":
                    category = "Memory Updates"
                    insight = f"Updated memory file: {file_path}"
                elif cls == "Config":
                    category = "Config Changes"
                    insight = f"Updated config: {file_path}"
                elif cls == "Code":
                    insight = f"Edited code: {file_path}"
                elif file_path:
                    insight = f"Edited {cls.lower()}: {file_path}"
                else:
                    insight = "File change"

            elif name == "Bash":
                cmd = _safe_get_str(input_data, "command", "cmd")
                if "git commit" in cmd:
                    m = re.search(r'-m\s+["\'](.+?)["\']', cmd)
                    msg = m.group(1) if m else ""
                    category = "Commits"
                    insight = f"Git commit: {msg}" if msg else f"Git commit: {cmd.strip()[:60]}"
                elif "git push" in cmd:
                    category = "Commits"
                    insight = "Pushed commits"
                elif cmd:
                    category = "Commands"
                    insight = f"Ran command: {cmd.strip()[:80]}"

            elif name == "TaskCreate":
                subject = _safe_get_str(input_data, "subject")
                category = "Tasks"
                insight = f"Created task: {subject}" if subject else "Created task"

            elif name == "TaskUpdate":
                subject = _safe_get_str(input_data, "subject")
                status = _safe_get_str(input_data, "status")
                category = "Tasks"
                if status:
                    insight = f"Task '{subject}' → {status}" if subject else f"Task updated → {status}"
                else:
                    insight = f"Updated task: {subject}" if subject else "Updated task"

            elif name == "ExitPlanMode":
                category = "Plans"
                insight = "Plan finalized and approved"

            elif name == "AskUserQuestion":
                # User responses to questions often contain decisions
                pass  # Text extraction handles the actual response content

            if insight:
                # Deduplicate using a normalized key
                norm = re.sub(r"\s+", " ", insight.lower().strip())
                if norm not in seen:
                    seen.add(norm)
                    insights.append((category, insight))

    return insights


# ---------------------------------------------------------------------------
# Text-based insight extraction
# ---------------------------------------------------------------------------

def extract_text_insights(transcript: list[dict]) -> list[tuple[str, str]]:
    """Extract insights from literal/natural-language phrases in conversation text.
    Returns list of (category, insight_text) tuples."""
    insights: list[tuple[str, str]] = []
    seen: set[str] = set()

    for entry in transcript:
        text = extract_text_from_entry(entry)
        if not text:
            continue
        for pattern, label in TEXT_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                # Some patterns have multiple capture groups
                if isinstance(m, tuple):
                    m = " ".join(part for part in m if part)
                insight_text = _clean_match(str(m))
                if insight_text:
                    norm = f"{label.lower()}:{insight_text.lower()}"
                    if norm not in seen:
                        seen.add(norm)
                        insights.append((label, insight_text))

    return insights


# ---------------------------------------------------------------------------
# Combined extraction with categorization
# ---------------------------------------------------------------------------

def extract_all_insights(transcript: list[dict]) -> dict[str, list[str]]:
    """Combine structural and text-based insights into categorized groups.
    Returns dict: {category: [insight, ...]}
    """
    structural = extract_structural_insights(transcript)
    textual = extract_text_insights(transcript)

    # Initialize categories
    categories: dict[str, list[str]] = {
        "Decisions": [],
        "Action Items": [],
        "Tasks": [],
        "File Changes": [],
        "Memory Updates": [],
        "Config Changes": [],
        "Commits": [],
        "Plans": [],
        "Commands": [],
        "Lessons": [],
        "Key Facts": [],
        "Important": [],
        "Next Steps": [],
        "Follow-ups": [],
    }

    seen: set[str] = set()

    # Helper to add deduplicated
    def add(cat: str, text: str) -> None:
        norm = re.sub(r"\s+", " ", text.lower().strip())
        if norm not in seen and text not in categories[cat]:
            seen.add(norm)
            categories[cat].append(text)

    # Structural insights already have categories
    for cat, text in structural:
        if cat in categories:
            add(cat, text)

    # Map text labels to canonical categories
    label_to_cat = {
        "Decision": "Decisions",
        "Action Item": "Action Items",
        "Task": "Tasks",
        "Lesson": "Lessons",
        "Key Fact": "Key Facts",
        "Important": "Important",
        "Next Step": "Next Steps",
        "Follow-up": "Follow-ups",
    }

    for label, text in textual:
        cat = label_to_cat.get(label, "Important")
        add(cat, text)

    # Remove empty categories
    return {k: v for k, v in categories.items() if v}


def format_insights(categorized: dict[str, list[str]], title: str = "Session Summary") -> str:
    """Format categorized insights into a markdown block for the daily log."""
    lines: list[str] = [f"\n## {title}\n"]
    # Preferred display order
    order = [
        "Decisions", "Plans", "Action Items", "Next Steps", "Follow-ups",
        "Tasks", "Commits", "File Changes", "Memory Updates", "Config Changes",
        "Commands", "Lessons", "Key Facts", "Important",
    ]
    for cat in order:
        items = categorized.get(cat)
        if not items:
            continue
        lines.append(f"\n### {cat}\n")
        for item in items:
            lines.append(f"- {item}")
    if len(lines) == 1:
        lines.append("\n_No insights captured._\n")
    return "\n".join(lines) + "\n"
