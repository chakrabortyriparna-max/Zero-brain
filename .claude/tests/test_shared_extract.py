#!/usr/bin/env python3
"""
Unit tests for shared_extract.py.
Run: python .claude/tests/test_shared_extract.py
"""
import sys
from pathlib import Path

# Ensure hooks dir is on path
HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from shared_extract import (
    extract_text_from_entry,
    extract_structural_insights,
    extract_text_insights,
    extract_all_insights,
    format_insights,
)


def test_extract_text_from_user_message():
    entry = {
        "type": "user",
        "message": {
            "role": "user",
            "content": "We decided to rewrite the extraction logic.",
        },
    }
    text = extract_text_from_entry(entry)
    assert "We decided to rewrite the extraction logic." in text


def test_extract_text_from_assistant_text_blocks():
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "The fix is straightforward."},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "foo.py"}},
                {"type": "text", "text": "We should proceed with the rewrite."},
            ],
        },
    }
    text = extract_text_from_entry(entry)
    assert "The fix is straightforward." in text
    assert "We should proceed with the rewrite." in text


def test_extract_text_skips_thinking_blocks():
    """Thinking blocks are skipped entirely to avoid internal reasoning noise."""
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "The user has decided to change the architecture. This is a key decision.",
                },
            ],
        },
    }
    text = extract_text_from_entry(entry)
    assert "decided to change the architecture" not in text


def test_extract_text_from_tool_result():
    entry = {
        "type": "tool_result",
        "content": [
            {"type": "text", "text": "File updated successfully."},
        ],
    }
    text = extract_text_from_entry(entry)
    assert "File updated successfully." in text


def test_extract_text_insights_decision():
    entry = {
        "type": "user",
        "message": {
            "role": "user",
            "content": "We decided to use SQLite for the local database.",
        },
    }
    insights = extract_text_insights([entry])
    assert any(cat == "Decision" and "SQLite" in text for cat, text in insights)


def test_extract_text_insights_action_item():
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "**Action Item:** Riparna to test the new hook tomorrow."},
            ],
        },
    }
    insights = extract_text_insights([entry])
    assert any(cat == "Action Item" and "test the new hook" in text for cat, text in insights)


def test_extract_text_insights_natural_language():
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let's go with option B for the caching layer."},
            ],
        },
    }
    insights = extract_text_insights([entry])
    assert any(cat == "Decision" and "option B" in text for cat, text in insights)


def test_extract_structural_insights_file_edit():
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Edit",
                    "input": {"file_path": "Memory/daily/2026-05-14.md"},
                },
            ],
        },
    }
    insights = extract_structural_insights([entry])
    assert any(cat == "Memory Updates" and "Memory" in text for cat, text in insights)


def test_extract_structural_insights_task_completed():
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "TaskUpdate",
                    "input": {"subject": "Fix hooks", "status": "completed"},
                },
            ],
        },
    }
    insights = extract_structural_insights([entry])
    assert any(cat == "Tasks" and "completed" in text for cat, text in insights)


def test_extract_all_insights_combines_both():
    transcript = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "**Decision:** We will use FastEmbed for embeddings.",
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "src/embeddings.py"},
                    },
                ],
            },
        },
    ]
    categorized = extract_all_insights(transcript)
    assert "Decisions" in categorized
    assert "File Changes" in categorized
    assert any("FastEmbed" in i for i in categorized["Decisions"])
    assert any("embeddings.py" in i for i in categorized["File Changes"])


def test_format_insights_groups_by_category():
    categorized = {
        "Decisions": ["Use SQLite"],
        "Action Items": ["Test tomorrow"],
    }
    markdown = format_insights(categorized, title="Test Flush")
    assert "## Test Flush" in markdown
    assert "### Decisions" in markdown
    assert "### Action Items" in markdown
    assert "- Use SQLite" in markdown
    assert "- Test tomorrow" in markdown


def test_format_insights_empty():
    markdown = format_insights({}, title="Empty")
    assert "_No insights captured._" in markdown


def main():
    tests = [
        test_extract_text_from_user_message,
        test_extract_text_from_assistant_text_blocks,
        test_extract_text_skips_thinking_blocks,
        test_extract_text_from_tool_result,
        test_extract_text_insights_decision,
        test_extract_text_insights_action_item,
        test_extract_text_insights_natural_language,
        test_extract_structural_insights_file_edit,
        test_extract_structural_insights_task_completed,
        test_extract_all_insights_combines_both,
        test_format_insights_groups_by_category,
        test_format_insights_empty,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
