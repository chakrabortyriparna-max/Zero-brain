"""
Fetch previous bot review comments on a PR for follow-up context.

Usage:
    python fetch_review_comments.py --pr 42 --repo owner/repo --output reviews.md
"""

import argparse
import os
import sys

from github import Github


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gh = Github(os.environ["GITHUB_TOKEN"])
    repo = gh.get_repo(args.repo)
    pr = repo.get_pull(args.pr)

    lines = ["# Previous Review Comments\n"]
    for comment in pr.get_issue_comments():
        # Skip comments from non-bot users (heuristic: skip the PR author)
        lines.append(f"**{comment.user.login}** at {comment.created_at}:")
        lines.append(comment.body)
        lines.append("")

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[INFO] Wrote {len(lines)} lines to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
