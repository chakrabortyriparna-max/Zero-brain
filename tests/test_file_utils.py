"""Tests for .claude/scripts/file_utils.py."""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from file_utils import atomic_write, locked_open, safe_load_json, atomic_write_json  # noqa: E402


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write(target, "hello")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "hello"

    def test_atomic_write_replaces_existing(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_atomic_write_json(self, tmp_path: Path):
        target = tmp_path / "data.json"
        atomic_write_json(target, {"key": "value"})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["key"] == "value"


class TestLockedOpen:
    def test_locked_read(self, tmp_path: Path):
        target = tmp_path / "file.txt"
        target.write_text("content", encoding="utf-8")
        with locked_open(target, "r", lock_mode="read") as f:
            assert f.read() == "content"

    def test_locked_write(self, tmp_path: Path):
        target = tmp_path / "file.txt"
        with locked_open(target, "w", lock_mode="write") as f:
            f.write("locked content")
        assert target.read_text(encoding="utf-8") == "locked content"

    def test_concurrent_writes_no_corruption(self, tmp_path: Path):
        target = tmp_path / "shared.txt"
        errors: list[str] = []
        results: list[str] = []

        def writer(name: str):
            try:
                with locked_open(target, "a", lock_mode="write") as f:
                    f.write(f"{name}\n")
                    time.sleep(0.05)
                results.append(name)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(f"t{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        content = target.read_text(encoding="utf-8")
        lines = [l for l in content.strip().splitlines() if l]
        assert len(lines) == 10


class TestSafeLoadJson:
    def test_load_existing(self, tmp_path: Path):
        target = tmp_path / "data.json"
        target.write_text('{"a": 1}', encoding="utf-8")
        data = safe_load_json(target, default={})
        assert data["a"] == 1

    def test_missing_returns_default(self, tmp_path: Path):
        target = tmp_path / "missing.json"
        data = safe_load_json(target, default={"fallback": True})
        assert data["fallback"] is True

    def test_corrupt_returns_default(self, tmp_path: Path):
        target = tmp_path / "bad.json"
        target.write_text("not json", encoding="utf-8")
        data = safe_load_json(target, default={"fallback": True})
        assert data["fallback"] is True
