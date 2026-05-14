"""
Claude Code Review — posts senior-engineer-level feedback as PR comments.

Usage:
    python claude_review.py --diff pr_diff.patch --pr 42 --repo owner/repo

Requires:
    ANTHROPIC_API_KEY env var
    GITHUB_TOKEN env var (needs pull-requests:write)
"""

import argparse
import os
import re
import sys
from pathlib import Path

from anthropic import Anthropic
from github import Github


def load_diff(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def build_prompt(diff: str) -> str:
    return f"""You are a senior staff engineer reviewing a pull request.
Review the following diff thoroughly. For each issue you find:
1. Describe the problem concretely with file and line references.
2. Rate severity: critical / warning / nit.
3. Suggest a fix or improvement.

Focus on:
- Security vulnerabilities (secrets, injection, unsafe defaults)
- Logic errors and edge cases
- Performance concerns
- Maintainability and readability
- DRY violations

Be direct. No filler. If something is good, say so briefly. If something is bad, say why and how to fix it.

Diff:
```diff
{diff}
```

Format your review as markdown with sections per file. Include a summary at the top.
"""


def call_claude(prompt: str) -> str:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6-20251001",
        max_tokens=4096,
        system="You are a senior staff engineer. Direct, no filler, strong opinions.",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def post_review(repo_name: str, pr_number: int, body: str) -> None:
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", required=True, help="Path to diff file")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--repo", required=True, help="Repo name (owner/repo)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    if not os.environ.get("GITHUB_TOKEN"):
        print("[ERROR] GITHUB_TOKEN not set", file=sys.stderr)
        return 1

    diff = load_diff(args.diff)
    if not diff.strip():
        print("[INFO] Empty diff — nothing to review.")
        return 0

    prompt = build_prompt(diff)
    review = call_claude(prompt)

    print("=== Claude Review ===")
    print(review)
    print("=====================")

    post_review(args.repo, args.pr, review)
    print(f"[INFO] Review posted to PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
