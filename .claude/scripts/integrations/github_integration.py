"""GitHub integration — notifications, issues, commits via PyGithub."""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class GHNotification:
    id: str
    title: str
    type: str
    repo: str
    reason: str
    unread: bool
    url: str


@dataclass
class GHIssue:
    number: int
    title: str
    state: str
    user: str
    url: str


@dataclass
class GHCommit:
    sha: str
    message: str
    author: str
    date: str


def _get_client():
    """Lazy-load authenticated PyGithub client."""
    from github import Auth, Github

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set in .env", file=sys.stderr)
        return None
    return Github(auth=Auth.Token(token))


def list_notifications() -> List[GHNotification]:
    g = _get_client()
    if g is None:
        return []
    try:
        notifs = g.get_user().get_notifications()
        out: List[GHNotification] = []
        for n in notifs:
            out.append(
                GHNotification(
                    id=str(n.id),
                    title=n.subject.title,
                    type=n.subject.type,
                    repo=n.repository.full_name,
                    reason=n.reason,
                    unread=n.unread,
                    url=n.subject.url or "",
                )
            )
        return out
    except Exception as e:
        print(f"GitHub list_notifications error: {e}", file=sys.stderr)
        return []


def list_issues(repo_name: str, state: str = "open", limit: int = 30) -> List[GHIssue]:
    g = _get_client()
    if g is None:
        return []
    try:
        repo = g.get_repo(repo_name)
        issues = repo.get_issues(state=state)
        out: List[GHIssue] = []
        for issue in issues[:limit]:
            out.append(
                GHIssue(
                    number=issue.number,
                    title=issue.title,
                    state=issue.state,
                    user=issue.user.login if issue.user else "",
                    url=issue.html_url,
                )
            )
        return out
    except Exception as e:
        print(f"GitHub list_issues error: {e}", file=sys.stderr)
        return []


def list_commits(repo_name: str, limit: int = 10) -> List[GHCommit]:
    g = _get_client()
    if g is None:
        return []
    try:
        repo = g.get_repo(repo_name)
        commits = repo.get_commits()
        out: List[GHCommit] = []
        for commit in commits[:limit]:
            out.append(
                GHCommit(
                    sha=commit.sha[:7],
                    message=commit.commit.message.split("\n")[0],
                    author=commit.commit.author.name if commit.commit.author else "",
                    date=str(commit.commit.author.date) if commit.commit.author else "",
                )
            )
        return out
    except Exception as e:
        print(f"GitHub list_commits error: {e}", file=sys.stderr)
        return []


def get_rate_limit() -> Optional[dict]:
    g = _get_client()
    if g is None:
        return None
    try:
        rate = g.get_rate_limit()
        return {
            "remaining": rate.rate.remaining,
            "limit": rate.rate.limit,
            "reset": str(rate.rate.reset),
        }
    except Exception as e:
        print(f"GitHub get_rate_limit error: {e}", file=sys.stderr)
        return None


def format_notifications(notifications: List[GHNotification]) -> str:
    if not notifications:
        return "_No notifications._"
    lines = []
    for n in notifications:
        status = "🔴" if n.unread else "🟢"
        lines.append(
            f"{status} **{n.repo}** — {n.title} ({n.type})\n   Reason: {n.reason}"
        )
    return "\n".join(lines)


def format_issues(issues: List[GHIssue]) -> str:
    if not issues:
        return "_No issues._"
    lines = [f"#{i.number}: {i.title} [{i.state}] by {i.user}" for i in issues]
    return "\n".join(lines)


def format_commits(commits: List[GHCommit]) -> str:
    if not commits:
        return "_No commits._"
    lines = [f"`{c.sha}` — {c.message} by {c.author} ({c.date})" for c in commits]
    return "\n".join(lines)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("github", help="GitHub integration commands")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("notifications", help="List notifications")

    p_issues = sub.add_parser("issues", help="List issues for a repo")
    p_issues.add_argument("repo", help="Repo name (owner/repo)")
    p_issues.add_argument("--state", default="open", choices=["open", "closed", "all"])
    p_issues.add_argument("--limit", type=int, default=30)

    p_commits = sub.add_parser("commits", help="List recent commits for a repo")
    p_commits.add_argument("repo", help="Repo name (owner/repo)")
    p_commits.add_argument("--limit", type=int, default=10)


def handle_cli(args: argparse.Namespace) -> None:
    if args.command == "notifications":
        notifs = list_notifications()
        print(format_notifications(notifs))
    elif args.command == "issues":
        issues = list_issues(args.repo, state=args.state, limit=args.limit)
        print(format_issues(issues))
    elif args.command == "commits":
        commits = list_commits(args.repo, limit=args.limit)
        print(format_commits(commits))
    else:
        print("Unknown command. Use: notifications, issues <repo>, commits <repo>")
