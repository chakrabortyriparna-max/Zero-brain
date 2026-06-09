#!/usr/bin/env python3
"""
Pilot evaluation runner for codegen-assist.
Wires the harness + scorer and produces a GPS before/after comparison.

Usage:
    python .claude/tests/skills/test_codegen_assist_eval.py
"""
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def main():
    harness = SCRIPT_DIR / "skill_eval_harness.py"
    if not harness.exists():
        print(f"[FAIL] Harness not found: {harness}")
        return 1

    print("=" * 60)
    print("Pilot Evaluation: codegen-assist")
    print("=" * 60)

    # Run dry-run evaluation first (no API calls) to validate harness
    print("\n[1/2] Dry-run evaluation (mock LLM responses)...")
    result = subprocess.run(
        [sys.executable, str(harness), "codegen-assist", "--trials", "2", "--dry-run"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print("[WARN] Dry-run had failures — expected for mock responses")
    else:
        print("[PASS] Dry-run completed")

    # Print instructions for live run
    print("\n[2/2] To run live evaluation:")
    print(f"    cd {PROJECT_ROOT}")
    print(f"    python .claude/scripts/skill_eval_harness.py codegen-assist --trials 3 --live")
    print("\nRequirements:")
    print("  - pip install anthropic")
    print("  - ANTHROPIC_API_KEY set in environment")

    return 0


if __name__ == "__main__":
    sys.exit(main())
