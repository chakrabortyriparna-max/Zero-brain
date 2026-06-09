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


def run_pytest_tests(project_root: Path) -> int:
    """Run pytest on tests/ directory."""
    test_files = sorted(project_root.glob("tests/test_hooks_*.py"))
    test_files += sorted(project_root.glob("tests/test_shared_extract.py"))

    if not test_files:
        print("[WARN] No pytest test files found in tests/")
        return 0

    cmd = [
        sys.executable, "-m", "pytest",
        *[str(f) for f in test_files],
        "-v", "--tb=short",
    ]
    print(f"Running pytest: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_root))
    return result.returncode


def run_custom_tests(project_root: Path) -> int:
    """Run custom test scripts in .claude/tests/ directly with python."""
    custom_tests = sorted(project_root.glob(".claude/tests/test_*.py"))
    if not custom_tests:
        print("[WARN] No custom test files found in .claude/tests/")
        return 0

    failed = 0
    for test_file in custom_tests:
        print(f"\nRunning custom test: {test_file}")
        result = subprocess.run([sys.executable, str(test_file)], cwd=str(project_root))
        if result.returncode != 0:
            failed += 1
    return failed


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    pytest_rc = run_pytest_tests(project_root)
    custom_rc = run_custom_tests(project_root)
    return pytest_rc or custom_rc


if __name__ == "__main__":
    sys.exit(main())
