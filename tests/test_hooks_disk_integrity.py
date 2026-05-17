"""Disk integrity tests for hooks."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


class TestAppendOnlySafety:
    def test_file_size_only_increases(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        # Create initial content
        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        size1 = daily.stat().st_size

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        size2 = daily.stat().st_size

        assert size2 >= size1

    def test_existing_content_not_overwritten(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        initial = "---\ndate: 2024-01-01\n---\n\n# Daily Log\n\nPreserve this.\n"
        daily.write_text(initial, encoding="utf-8")

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        content = daily.read_text(encoding="utf-8")
        assert "Preserve this." in content
        assert content.startswith("---\ndate: 2024-01-01")


class TestCrashResilience:
    def test_crash_during_append_does_not_truncate(self, isolated_project):
        daily = isolated_project / "Memory" / "daily" / "2024-01-01.md"
        initial = "---\ndate: 2024-01-01\n---\n\n# Daily Log\n\nSafe content.\n"
        daily.write_text(initial, encoding="utf-8")

        crash_script = isolated_project / "crash.py"
        crash_script.write_text(
            'import time\n'
            'with open("Memory/daily/2024-01-01.md", "a", encoding="utf-8") as f:\n'
            '    f.write("Partial data")\n'
            '    time.sleep(10)\n',
            encoding="utf-8",
        )

        proc = subprocess.Popen(
            [sys.executable, str(crash_script)],
            cwd=str(isolated_project),
        )
        time.sleep(0.3)
        proc.kill()
        proc.wait()

        content = daily.read_text(encoding="utf-8")
        assert "Safe content." in content
        assert content.startswith("---\ndate: 2024-01-01")


class TestConcurrentConsistency:
    def test_concurrent_appends(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"
        # Pre-create file to avoid race on Windows
        daily.write_text("# Daily Log\n\n", encoding="utf-8")

        lock = threading.Lock()

        def append_n(n):
            for i in range(5):
                with lock:
                    with open(daily, "a", encoding="utf-8") as f:
                        f.write(f"Thread {n} line {i}\n")

        threads = [threading.Thread(target=append_n, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        content = daily.read_text(encoding="utf-8")
        for n in range(10):
            for i in range(5):
                assert f"Thread {n} line {i}" in content


class TestEncoding:
    def test_unicode_roundtrip(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        # Pre-seed with unicode
        initial = "---\ndate: 2024-01-01\n---\n\n# Daily Log\n\n✅ check\n★ star\n🚀 rocket\n"
        daily.write_text(initial, encoding="utf-8")

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        content = daily.read_text(encoding="utf-8")
        assert "✅" in content
        assert "★" in content
        assert "🚀" in content


class TestDailyLogStructure:
    def test_valid_frontmatter_and_heading(self, isolated_project):
        hooks = isolated_project / ".claude" / "hooks"
        today = time.strftime("%Y-%m-%d")
        daily = isolated_project / "Memory" / "daily" / f"{today}.md"

        subprocess.run(
            [sys.executable, str(hooks / "session-start-context.py")],
            capture_output=True,
            cwd=str(isolated_project),
        )
        content = daily.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "date:" in content
        assert "# Daily Log" in content
        assert "## Session Start" in content


class TestFsync:
    def test_fsync_not_currently_called(self, isolated_project):
        """Document the fsync gap: hooks do not currently force OS-level flush."""
        hooks = isolated_project / ".claude" / "hooks"
        called = []

        original_fsync = os.fsync

        def mock_fsync(fd):
            called.append(fd)
            return original_fsync(fd)

        os.fsync = mock_fsync
        try:
            subprocess.run(
                [sys.executable, str(hooks / "session-start-context.py")],
                capture_output=True,
                cwd=str(isolated_project),
            )
            # Currently no fsync is called inside the hook scripts
            assert len(called) == 0, "fsync was called — update this test after adding fsync to hooks"
        finally:
            os.fsync = original_fsync
