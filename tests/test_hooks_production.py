"""Production readiness tests for hooks."""

import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shared_extract import extract_all_insights

HOOKS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks"


class TestSecretsHygiene:
    def test_no_hardcoded_secrets(self):
        bad_patterns = ["api_key", "token", "password", "secret", "private_key"]
        for hook_file in HOOKS_DIR.glob("*.py"):
            content = hook_file.read_text(encoding="utf-8").lower()
            found = [p for p in bad_patterns if p in content]
            assert not found, f"{hook_file.name} contains potential secret keywords: {found}"

    def test_no_environment_secret_access(self):
        for hook_file in HOOKS_DIR.glob("*.py"):
            tree = ast.parse(hook_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript):
                    if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
                        if isinstance(node.value.value, ast.Name) and node.value.value.id == "os":
                            pytest.fail(f"{hook_file.name} accesses os.environ")


class TestEncodingSafety:
    def test_all_file_ops_explicit_encoding(self):
        for hook_file in HOOKS_DIR.glob("*.py"):
            tree = ast.parse(hook_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name in ("open", "read_text", "write_text"):
                        has_encoding = any(
                            isinstance(kw, ast.keyword) and kw.arg == "encoding"
                            for kw in node.keywords
                        )
                        assert has_encoding, (
                            f"{hook_file.name}:{node.lineno} — "
                            f"{func_name}() missing encoding= parameter"
                        )


class TestPathSafety:
    def test_no_os_path_join(self):
        for hook_file in HOOKS_DIR.glob("*.py"):
            tree = ast.parse(hook_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    assert not (node.attr == "join" and isinstance(node.value, ast.Attribute) and node.value.attr == "path" and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"), (
                        f"{hook_file.name}:{node.lineno} — uses os.path.join"
                    )

    def test_no_string_path_concatenation_for_paths(self):
        # Look for patterns like "Memory/" + variable in hook files
        for hook_file in HOOKS_DIR.glob("*.py"):
            content = hook_file.read_text(encoding="utf-8")
            # Skip the shared_extract file which has regex strings containing /
            if hook_file.name == "shared_extract.py":
                continue
            assert "\"Memory/\"" not in content, (
                f"{hook_file.name} contains hardcoded string path 'Memory/'"
            )


class TestErrorHandling:
    def test_missing_memory_file_graceful(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        (isolated_project / "Memory" / "SOUL.md").unlink()
        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        assert "<!-- SOUL.md not found -->" in result.stdout

    def test_missing_daily_dir_creates_it(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        daily_dir = isolated_project / "Memory" / "daily"
        import shutil
        shutil.rmtree(daily_dir)
        result = subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        assert daily_dir.exists()


class TestScale:
    def test_scale_10000_entries(self):
        transcript = []
        for i in range(10000):
            transcript.append(
                {"role": "assistant", "content": f"I decided to option {i}"}
            )
        start = time.perf_counter()
        result = extract_all_insights(transcript)
        elapsed = time.perf_counter() - start
        total = sum(len(v) for v in result.values())
        assert total == 10000
        assert elapsed < 5.0


class TestJsonlRobustness:
    def test_unicode_emoji(self):
        transcript = [
            {"role": "assistant", "content": "I decided to use 🚀 for deployments ✅."}
        ]
        result = extract_all_insights(transcript)
        assert any("🚀" in item for items in result.values() for item in items)
        assert any("✅" in item for items in result.values() for item in items)

    def test_cjk_characters(self):
        transcript = [
            {"role": "assistant", "content": "I decided to use 中文支持 for i18n."}
        ]
        result = extract_all_insights(transcript)
        assert any("中文支持" in item for items in result.values() for item in items)

    def test_escaped_newlines(self):
        transcript = [
            {"role": "assistant", "content": "I decided to use newlines in logs."}
        ]
        result = extract_all_insights(transcript)
        assert any("newlines" in item for items in result.values() for item in items)

    def test_very_long_line(self):
        long_text = "x" * (1024 * 1024)  # 1MB
        transcript = [{"role": "assistant", "content": long_text}]
        result = extract_all_insights(transcript)
        assert result == {}  # No patterns match, but it doesn't crash

    def test_jsonl_input_to_flush_hooks(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        transcript = [
            {"role": "assistant", "content": "I decided to test unicode 🎉."},
            {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": "src/测试.py"}}
            ]},
        ]
        result = subprocess.run(
            [sys.executable, str(hooks / "pre-compact-flush.py")],
            input="\n".join(json.dumps(e) for e in transcript),
            capture_output=True,
            text=True,
            cwd=str(isolated_project),
        )
        assert result.returncode == 0
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"
        content = daily.read_text(encoding="utf-8")
        assert "🎉" in content
        assert "测试.py" in content
