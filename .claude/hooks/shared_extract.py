#!/usr/bin/env python3
"""
Shared extraction logic for PreCompact and SessionEnd hooks.
Parses JSONL transcript entries for both regex-based text insights
and structural heuristics from tool_use blocks.
"""
import re
from typing import Any

# Regex patterns for literal phrases in conversation text
TEXT_PATTERNS = [
    (r"(?i)(?:decided to|decision:)\s+(.+)", "Decision"),
    (r"(?i)(?:learned that|lesson learned:)\s+(.+)", "Lesson"),
    (r"(?i)(?:action item:?)\s+(.+)", "Action Item"),
    (r"(?i)(?:key fact:?)\s+(.+)", "Key Fact"),
    (r"(?i)(?:important:?)\s+(.+)", "Important"),
]


def extract_text_from_entry(entry: dict) -> str:
    """Extract all text from a transcript entry recursively."""
    texts = []
    for key in ("content", "text", "message", "output", "result"):
        val = entry.get(key)
        if isinstance(val, str):
            texts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    texts.append(str(item["text"]))
        elif isinstance(val, dict):
            for subval in val.values():
                if isinstance(subval, str):
                    texts.append(subval)
    return " ".join(texts)


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


def extract_structural_insights(transcript: list[dict]) -> list[str]:
    """Extract insights from tool_use blocks in the transcript."""
    insights = []
    seen = set()

    for entry in transcript:
        tools = _find_tool_uses(entry)
        for name, input_data in tools:
            insight = None

            if name in ("Write", "Edit"):
                file_path = _safe_get_str(input_data, "file_path", "path")
                if "Memory/" in file_path or "MEMORY.md" in file_path:
                    insight = f"Memory Update: {file_path}"
                elif file_path:
                    insight = f"File Change: {file_path}"
                else:
                    insight = "File Change"

            elif name == "Bash":
                cmd = _safe_get_str(input_data, "command", "cmd")
                if "git commit" in cmd:
                    # Extract commit message if present
                    m = re.search(r'-m\s+["\'](.+?)["\']', cmd)
                    msg = m.group(1) if m else ""
                    insight = f"Commit: {msg}" if msg else f"Commit: {cmd.strip()[:60]}"

            elif name == "TaskCreate":
                subject = _safe_get_str(input_data, "subject")
                insight = f"Task Created: {subject}" if subject else "Task Created"

            elif name == "TaskUpdate":
                subject = _safe_get_str(input_data, "subject")
                insight = f"Task Updated: {subject}" if subject else "Task Updated"

            elif name == "ExitPlanMode":
                insight = "Plan Finalized"

            if insight and insight not in seen:
                seen.add(insight)
                insights.append(f"- **{insight}**")

    return insights


def extract_text_insights(transcript: list[dict]) -> list[str]:
    """Extract insights from literal phrases in conversation text."""
    insights = []
    seen = set()
    for entry in transcript:
        text = extract_text_from_entry(entry)
        if not text:
            continue
        for pattern, label in TEXT_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                insight = f"- **{label}:** {m.strip()}"
                if insight not in seen:
                    seen.add(insight)
                    insights.append(insight)
    return insights


def extract_all_insights(transcript: list[dict]) -> list[str]:
    """Combine structural and text-based insights, deduplicated."""
    structural = extract_structural_insights(transcript)
    textual = extract_text_insights(transcript)
    # Deduplicate while preserving order (structural first)
    seen = set(structural)
    combined = list(structural)
    for insight in textual:
        if insight not in seen:
            seen.add(insight)
            combined.append(insight)
    return combined
