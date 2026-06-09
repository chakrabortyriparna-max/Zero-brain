#!/usr/bin/env python3
"""
File utilities for Second Brain scripts.

Provides:
  - Atomic file writes (temp file + rename)
  - Cross-platform file locking (read / write locks)
  - Safe JSON state persistence

Usage:
    from file_utils import atomic_write, locked_open
    atomic_write(path, "content")

    with locked_open(path, "r") as f:
        data = json.load(f)
"""
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import portalocker
except ImportError:
    portalocker = None  # type: ignore


@contextmanager
def locked_open(path: Path | str, mode: str = "r", lock_mode: str = "write") -> Iterator[Any]:
    """
    Open a file with an advisory lock.

    lock_mode: 'write' (exclusive) or 'read' (shared)
    """
    path = Path(path)
    # Ensure directory exists for write modes
    if "w" in mode or "a" in mode:
        path.parent.mkdir(parents=True, exist_ok=True)

    f = open(path, mode, encoding="utf-8")
    try:
        if portalocker:
            if lock_mode == "write" or "w" in mode or "a" in mode:
                portalocker.lock(f, portalocker.LOCK_EX)
            else:
                portalocker.lock(f, portalocker.LOCK_SH)
        yield f
    finally:
        if portalocker:
            portalocker.unlock(f)
        f.close()


def atomic_write(path: Path | str, content: str) -> None:
    """Write content to a temp file and atomically rename it to path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path | str, data: dict | list) -> None:
    """Atomically write JSON data."""
    content = json.dumps(data, indent=2, ensure_ascii=False)
    atomic_write(path, content)


def safe_load_json(path: Path | str, default: Any = None) -> Any:
    """Load JSON with a safe default on failure."""
    path = Path(path)
    if not path.exists():
        return default
    try:
        with locked_open(path, "r", lock_mode="read") as f:
            return json.load(f)
    except Exception:
        return default
