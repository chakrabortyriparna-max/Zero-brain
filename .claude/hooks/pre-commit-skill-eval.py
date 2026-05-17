#!/usr/bin/env python3
"""
Pre-commit hook: run 10-point skill evaluation on any modified skill.

Install:
    cp .claude/hooks/pre-commit-skill-eval.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Behavior:
    - Detects which SKILL.md files are modified (staged)
    - Runs `python .claude/scripts/skill_eval_full.py <skill> --trials 3 --groq`
    - Blocks commit if any skill fails evaluation
    - Skips eval if a skill has no prompt coverage yet (warns)
"""
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(".claude/skills")
EVAL_SCRIPT = Path(".claude/scripts/skill_eval_full.py")


def get_staged_skill_names() -> list[str]:
    """Return skill names whose SKILL.md is staged for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True
    )
    staged = result.stdout.strip().split("\n")
    skills = []
    for path in staged:
        if not path.startswith(".claude/skills/"):
            continue
        parts = Path(path).parts
        if len(parts) >= 3 and parts[2] == "SKILL.md":
            skills.append(parts[1])
    return skills


def main():
    skills = get_staged_skill_names()
    if not skills:
        print("[pre-commit-skill-eval] No skills modified. Skipping.")
        sys.exit(0)

    print(f"[pre-commit-skill-eval] Modified skills: {', '.join(skills)}")

    all_passed = True
    for skill in skills:
        print(f"\n[pre-commit-skill-eval] Running 10-point eval for: {skill}")
        proc = subprocess.run(
            [sys.executable, str(EVAL_SCRIPT), skill, "--trials", "3", "--groq"],
            capture_output=False,
        )
        if proc.returncode != 0:
            print(f"[pre-commit-skill-eval] SKILL EVAL FAILED: {skill}")
            all_passed = False

    if not all_passed:
        print("\n[pre-commit-skill-eval] Commit blocked due to skill evaluation failure.")
        print("Fix the skill or run with --skill-only for static-only checks.")
        sys.exit(1)

    print("[pre-commit-skill-eval] All skill evaluations passed. Commit allowed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
