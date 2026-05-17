"""Unit tests for shared_extract.py — pure logic, no I/O."""

import time

import pytest

from shared_extract import (
    extract_all_insights,
    extract_structural_insights,
    extract_text_from_entry,
    extract_text_insights,
    _find_tool_uses,
)


class TestExtractTextFromEntry:
    def test_string_content(self):
        assert extract_text_from_entry({"content": "hello world"}) == "hello world"

    def test_list_of_strings(self):
        assert extract_text_from_entry({"content": ["a", "b"]}) == "a b"

    def test_list_of_dicts_with_text(self):
        assert extract_text_from_entry({"content": [{"text": "x"}]}) == "x"

    def test_nested_dict_values(self):
        assert extract_text_from_entry({"output": {"inner": "val"}}) == "val"

    def test_empty_entry(self):
        assert extract_text_from_entry({}) == ""

    def test_multiple_keys(self):
        entry = {"content": "first", "text": "second", "message": "third"}
        result = extract_text_from_entry(entry)
        assert "first" in result
        assert "second" in result
        assert "third" in result


class TestFindToolUses:
    def test_claude_code_style(self):
        obj = {"type": "tool_use", "name": "Write", "input": {"file_path": "a.md"}}
        assert _find_tool_uses(obj) == [("Write", {"file_path": "a.md"})]

    def test_openai_style(self):
        obj = {"function": {"name": "Edit", "arguments": {"path": "b.md"}}}
        assert _find_tool_uses(obj) == [("Edit", {"path": "b.md"})]

    def test_deeply_nested(self):
        obj = {
            "outer": {
                "inner": {
                    "type": "tool_use",
                    "name": "TaskCreate",
                    "input": {"subject": "X"},
                }
            }
        }
        assert _find_tool_uses(obj) == [("TaskCreate", {"subject": "X"})]

    def test_multiple_tools(self):
        obj = {
            "items": [
                {"type": "tool_use", "name": "Write", "input": {}},
                {"type": "tool_use", "name": "Bash", "input": {}},
            ]
        }
        names = [name for name, _ in _find_tool_uses(obj)]
        assert names == ["Write", "Bash"]

    def test_no_tools(self):
        assert _find_tool_uses({"role": "user", "content": "hello"}) == []


class TestExtractStructuralInsights:
    def test_write_file_change(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "src/db.py"}}
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **File Change: src/db.py**" in result

    def test_write_memory_update(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "Memory/SOUL.md"}}
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Memory Update: Memory/SOUL.md**" in result

    def test_bash_git_commit_with_message(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": 'git commit -m "fix bug"'},
                    }
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Commit: fix bug**" in result

    def test_bash_git_commit_no_message(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "git commit"}}
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Commit: git commit**" in result

    def test_task_create(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "TaskCreate",
                        "input": {"subject": "Refactor auth"},
                    }
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Task Created: Refactor auth**" in result

    def test_task_update(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "TaskUpdate",
                        "input": {"subject": "Update docs"},
                    }
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Task Updated: Update docs**" in result

    def test_exit_plan_mode(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "ExitPlanMode", "input": {}}
                ],
            }
        ]
        result = extract_structural_insights(transcript)
        assert "- **Plan Finalized**" in result

    def test_deduplication(self):
        transcript = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "a.md"}}
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "a.md"}}
                ],
            },
        ]
        result = extract_structural_insights(transcript)
        assert len(result) == 1
        assert "File Change: a.md" in result[0]


class TestExtractTextInsights:
    def test_decision(self):
        transcript = [{"role": "assistant", "content": "I decided to use PostgreSQL."}]
        result = extract_text_insights(transcript)
        assert "- **Decision:** use PostgreSQL." in result

    def test_lesson(self):
        transcript = [{"role": "assistant", "content": "lesson learned: test early"}]
        result = extract_text_insights(transcript)
        assert "- **Lesson:** test early" in result

    def test_action_item(self):
        transcript = [{"role": "assistant", "content": "action item: review PR"}]
        result = extract_text_insights(transcript)
        assert "- **Action Item:** review PR" in result

    def test_key_fact(self):
        transcript = [{"role": "assistant", "content": "key fact: Python 3.12"}]
        result = extract_text_insights(transcript)
        assert "- **Key Fact:** Python 3.12" in result

    def test_important(self):
        transcript = [{"role": "assistant", "content": "important: deploy before 5pm"}]
        result = extract_text_insights(transcript)
        assert "- **Important:** deploy before 5pm" in result

    def test_case_insensitive(self):
        transcript = [{"role": "assistant", "content": "DECIDED TO use Redis"}]
        result = extract_text_insights(transcript)
        assert "- **Decision:** use Redis" in result

    def test_no_false_positive(self):
        transcript = [{"role": "assistant", "content": "I decided without colon here"}]
        result = extract_text_insights(transcript)
        assert result == []


class TestExtractAllInsights:
    def test_combines_structural_and_textual(self):
        transcript = [
            {
                "role": "assistant",
                "content": "I decided to use PostgreSQL.",
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "src/db.py"}}
                ],
            },
        ]
        result = extract_all_insights(transcript)
        assert any("Decision" in r for r in result)
        assert any("File Change" in r for r in result)

    def test_structural_comes_first(self):
        transcript = [
            {
                "role": "assistant",
                "content": "I decided to use PostgreSQL.",
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "a.md"}}
                ],
            },
        ]
        result = extract_all_insights(transcript)
        assert result[0].startswith("- **File Change")

    def test_deduplication_across_both(self):
        transcript = [
            {
                "role": "assistant",
                "content": "action item: verify hooks",
            },
            {
                "role": "assistant",
                "content": "action item: verify hooks",
            },
        ]
        result = extract_all_insights(transcript)
        assert result.count("- **Action Item:** verify hooks") == 1

    def test_empty_transcript(self):
        assert extract_all_insights([]) == []

    def test_scale_1000_entries(self):
        transcript = []
        for i in range(500):
            transcript.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {"file_path": f"src/file_{i}.py"},
                        }
                    ],
                }
            )
            transcript.append(
                {"role": "assistant", "content": f"decided to option {i}"}
            )

        start = time.perf_counter()
        result = extract_all_insights(transcript)
        elapsed = time.perf_counter() - start

        assert len(result) == 1000
        assert elapsed < 1.0
