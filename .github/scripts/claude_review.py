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
import re
import sys
import time
from pathlib import Path
from typing import List

import requests
from github import Github


# ── Helpers ────────────────────────────────────────────────────────────


def get_timeout() -> int:
    """Read LLM_TIMEOUT from env (already set to 300 in .env), default 180."""
    try:
        return int(os.environ.get("LLM_TIMEOUT", "180"))
    except ValueError:
        return 180


def load_diff(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    # Soft cap: if a single diff is > 50k chars we chunk it later instead of
    # silently truncating. 50k is the per-chunk budget, not the total.
    return text


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


# ── Ollama API ───────────────────────────────────────────────────────


def call_ollama_raw(prompt: str, model: str, timeout: int) -> str:
    """Single Ollama API call. Raises on any failure."""
    base = os.environ["OLLAMA_URL"].rstrip("/")
    if base.endswith("/api"):
        url = base + "/generate"
    else:
        url = base + "/api/generate"

    headers = {"Content-Type": "application/json"}
    if os.environ.get("OLLAMA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OLLAMA_API_KEY']}"

    payload = {
        "model": model,
        "prompt": prompt,
        "system": "You are a senior staff engineer. Direct, no filler, strong opinions.",
        "stream": False,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data.get("response", data.get("message", {}).get("content", ""))


def call_ollama_with_retry(prompt: str, max_retries: int = 3) -> str:
    """
    Strategy: Kimi K2.6 (primary) with exponential backoff.
    If all retries fail → Nemotron 3 ultra (fallback) once.
    """
    timeout = get_timeout()
    primary = "kimi-k2.6:cloud"
    fallback = "nemotron-3-ultra:cloud"

    # ── Primary retries ──
    for attempt in range(max_retries):
        try:
            print(
                f"[INFO] Ollama call ({primary}) attempt {attempt + 1}/{max_retries} ...",
                file=sys.stderr,
            )
            return call_ollama_raw(prompt, primary, timeout)
        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            print(
                f"[WARNING] Timeout on attempt {attempt + 1}. Backing off {wait}s ...",
                file=sys.stderr,
            )
            time.sleep(wait)
        except requests.exceptions.RequestException as e:
            print(
                f"[WARNING] Request error on attempt {attempt + 1}: {e}",
                file=sys.stderr,
            )
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"[WARNING] Retrying in {wait}s ...", file=sys.stderr)
                time.sleep(wait)

    # ── Fallback ──
    print(
        f"[WARNING] Primary model {primary} failed after {max_retries} attempts. "
        f"Falling back to {fallback} ...",
        file=sys.stderr,
    )
    try:
        return call_ollama_raw(prompt, fallback, timeout)
    except Exception as e:
        print(f"[ERROR] Fallback model {fallback} also failed: {e}", file=sys.stderr)
        raise


# ── Chunking ───────────────────────────────────────────────────────────


def chunk_diff(diff: str, max_chunk_chars: int = 40000) -> List[str]:
    """
    Split a large diff into chunks by file boundaries (diff --git lines).
    If a single file still exceeds the limit, hard-split it.
    """
    if len(diff) <= max_chunk_chars:
        return [diff]

    files = re.split(r"(?=diff --git)", diff)
    chunks: List[str] = []
    current = ""

    for f in files:
        if not f.strip():
            continue
        if len(current) + len(f) > max_chunk_chars:
            if current:
                chunks.append(current)
            current = f
        else:
            current += f
    if current:
        chunks.append(current)

    # Guard: any single file still too large → split into rough halves
    result: List[str] = []
    for chunk in chunks:
        if len(chunk) > max_chunk_chars:
            mid = len(chunk) // 2
            result.append(chunk[:mid])
            result.append(chunk[mid:])
        else:
            result.append(chunk)
    return result


def merge_chunk_reviews(reviews: List[str]) -> str:
    """Combine per-chunk reviews into one markdown comment."""
    if len(reviews) == 1:
        return reviews[0]

    merged = "## Automated Review (chunked due to large diff)\n\n"
    for i, r in enumerate(reviews, 1):
        merged += f"### Chunk {i}\n\n{r}\n\n---\n\n"
    return merged


# ── GitHub ────────────────────────────────────────────────────────────


def post_review(repo_name: str, pr_number: int, body: str) -> None:
    gh = Github(os.environ["GITHUB_TOKEN"])
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(body)


# ── Main ───────────────────────────────────────────────────────────────


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
        reply = call_ollama_with_retry(prompt)
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

    chunks = chunk_diff(diff)
    if len(chunks) == 1:
        prompt = build_review_prompt(chunks[0])
        review = call_ollama_with_retry(prompt)
    else:
        print(
            f"[INFO] Diff split into {len(chunks)} chunks (max ~40k chars each).",
            file=sys.stderr,
        )
        reviews = []
        for i, chunk in enumerate(chunks, 1):
            print(f"[INFO] Reviewing chunk {i}/{len(chunks)} ...", file=sys.stderr)
            prompt = build_review_prompt(chunk)
            reviews.append(call_ollama_with_retry(prompt))
        review = merge_chunk_reviews(reviews)

    print("=== Review ===")
    print(review)
    print("==============")
    post_review(args.repo, args.pr, review)
    print(f"[INFO] Review posted to PR #{args.pr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
