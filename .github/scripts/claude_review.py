"""
Claude Code Review — posts senior-engineer-level feedback as PR comments.

Uses Ollama Cloud instead of Anthropic API.

Usage:
    python claude_review.py --diff pr_diff.patch --pr 42 --repo owner/repo

Requires:
    OLLAMA_URL env var   (e.g., https://ollama.com or your cloud instance)
    OLLAMA_API_KEY env var (if your cloud provider requires auth)
    GITHUB_TOKEN env var (needs pull-requests:write)
"""

import argparse
import os
import sys
from pathlib import Path

import requests
from github import Github


def load_diff(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def build_review_prompt(diff: str) -> str:
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


def build_reply_prompt(question: str, previous_reviews: str) -> str:
    return f"""You are a senior staff engineer who previously reviewed a pull request.
The user has asked a follow-up question about your review. Use the previous review context below to provide a deeper, more detailed explanation.

Previous review comments:
```markdown
{previous_reviews}
```

User's follow-up question:
"{question}"

Instructions:
- Answer the question directly and thoroughly.
- Include code examples or specific file references where helpful.
- If the question refers to a numbered issue from the previous review, expand on that exact point.
- Keep the same tone: direct, no filler, senior engineer level.
- If you need to correct or soften something you said earlier, do so explicitly.
"""


def call_ollama(prompt: str) -> str:
    base = os.environ["OLLAMA_URL"].rstrip("/")
    # If base already ends with /api, use /generate; otherwise use /api/generate
    if base.endswith("/api"):
        url = base + "/generate"
    else:
        url = base + "/api/generate"
    headers = {"Content-Type": "application/json"}
    if os.environ.get("OLLAMA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OLLAMA_API_KEY']}"

    payload = {
        "model": "kimi-k2.6:cloud",
        "prompt": prompt,
        "system": "You are a senior staff engineer. Direct, no filler, strong opinions.",
        "stream": False,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    return data.get("response", data.get("message", {}).get("content", ""))


def post_review(repo_name: str, pr_number: int, body: str) -> None:
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--repo", required=True, help="Repo name (owner/repo)")
    parser.add_argument("--diff", help="Path to diff file (for initial review)")
    parser.add_argument("--reply", action="store_true", help="Reply to a follow-up question")
    parser.add_argument("--question", help="User's follow-up question text")
    parser.add_argument("--previous-review", help="Path to file with previous review comments")
    args = parser.parse_args()

    if not os.environ.get("OLLAMA_URL"):
        print("[ERROR] OLLAMA_URL not set", file=sys.stderr)
        return 1
    if not os.environ.get("GITHUB_TOKEN"):
        print("[ERROR] GITHUB_TOKEN not set", file=sys.stderr)
        return 1

    if args.reply:
        if not args.question:
            print("[ERROR] --reply requires --question", file=sys.stderr)
            return 1
        previous = ""
        if args.previous_review:
            previous = Path(args.previous_review).read_text(encoding="utf-8")
        prompt = build_reply_prompt(args.question, previous)
        reply = call_ollama(prompt)
        print("=== Reply ===")
        print(reply)
        print("=============")
        post_review(args.repo, args.pr, reply)
        print(f"[INFO] Reply posted to PR #{args.pr}")
        return 0

    if not args.diff:
        print("[ERROR] Either --diff or --reply is required", file=sys.stderr)
        return 1

    diff = load_diff(args.diff)
    if not diff.strip():
        print("[INFO] Empty diff — nothing to review.")
        return 0

    prompt = build_review_prompt(diff)
    review = call_ollama(prompt)

    print("=== Review ===")
    print(review)
    print("==============")

    post_review(args.repo, args.pr, review)
    print(f"[INFO] Review posted to PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
