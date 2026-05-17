#!/usr/bin/env python3
"""
Standalone hook verification runner for Riparna's Second Brain.
Produces PASS/FAIL evidence per phase and exits non-zero on failure.

Usage:
    python .claude/scripts/verify_hooks.py
"""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    test_files = sorted(project_root.glob("tests/test_hooks_*.py"))
    test_files += sorted(project_root.glob("tests/test_shared_extract.py"))

    if not test_files:
        print("[FAIL] No hook test files found in tests/")
        return 1

    cmd = [
        sys.executable, "-m", "pytest",
        *[str(f) for f in test_files],
        "-v", "--tb=short",
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_root))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
