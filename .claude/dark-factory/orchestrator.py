"""Dark Factory orchestrator — polls GitHub and dispatches Archon workflows."""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    COMMANDS_DIR,
    DECISION_MAPPING_PATH,
    LOGS_DIR,
    MODULE_DIR,
    STATE_DB_PATH,
    WORKFLOWS_DIR,
    Config,
    load_decision_mapping,
)

# Logging setup
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "orchestrator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("dark-factory")

# Project root (repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class StateDB:
    """SQLite state database for tracking Dark Factory runs, issues, and PRs."""

    def __init__(self, db_path: Path = STATE_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                workflow TEXT NOT NULL,
                target_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                error_message TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_issues (
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                current_status TEXT NOT NULL,
                last_processed_at TEXT NOT NULL,
                last_workflow_run_id TEXT,
                PRIMARY KEY (repo_owner, repo_name, issue_number)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_prs (
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                current_status TEXT NOT NULL,
                last_processed_at TEXT NOT NULL,
                last_workflow_run_id TEXT,
                PRIMARY KEY (repo_owner, repo_name, pr_number)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracked_issues_status ON tracked_issues(current_status)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracked_prs_status ON tracked_prs(current_status)
        """)
        self.conn.commit()

    def record_run(
        self,
        run_id: str,
        repo_owner: str,
        repo_name: str,
        workflow: str,
        target_number: int,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO runs (run_id, timestamp, repo_owner, repo_name, workflow, target_number, status, result_json, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                repo_owner,
                repo_name,
                workflow,
                target_number,
                status,
                json.dumps(result) if result else None,
                error,
            ),
        )
        self.conn.commit()

    def update_issue_status(
        self,
        repo_owner: str,
        repo_name: str,
        issue_number: int,
        status: str,
        run_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO tracked_issues (repo_owner, repo_name, issue_number, current_status, last_processed_at, last_workflow_run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_owner, repo_name, issue_number) DO UPDATE SET
                current_status=excluded.current_status,
                last_processed_at=excluded.last_processed_at,
                last_workflow_run_id=excluded.last_workflow_run_id
            """,
            (
                repo_owner,
                repo_name,
                issue_number,
                status,
                datetime.now(timezone.utc).isoformat(),
                run_id,
            ),
        )
        self.conn.commit()

    def update_pr_status(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        status: str,
        run_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO tracked_prs (repo_owner, repo_name, pr_number, current_status, last_processed_at, last_workflow_run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_owner, repo_name, pr_number) DO UPDATE SET
                current_status=excluded.current_status,
                last_processed_at=excluded.last_processed_at,
                last_workflow_run_id=excluded.last_workflow_run_id
            """,
            (
                repo_owner,
                repo_name,
                pr_number,
                status,
                datetime.now(timezone.utc).isoformat(),
                run_id,
            ),
        )
        self.conn.commit()

    def get_last_run_for_issue(
        self, repo_owner: str, repo_name: str, issue_number: int
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM runs WHERE repo_owner=? AND repo_name=? AND target_number=? AND workflow='dark-factory-fix-github-issue'
            ORDER BY timestamp DESC LIMIT 1
            """,
            (repo_owner, repo_name, issue_number),
        ).fetchone()
        return dict(row) if row else None

    def get_last_run_for_pr(
        self, repo_owner: str, repo_name: str, pr_number: int
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT * FROM runs WHERE repo_owner=? AND repo_name=? AND target_number=? AND workflow='dark-factory-validate-pr'
            ORDER BY timestamp DESC LIMIT 1
            """,
            (repo_owner, repo_name, pr_number),
        ).fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict[str, Any]:
        total_runs = self.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        success_runs = self.conn.execute("SELECT COUNT(*) FROM runs WHERE status='success'").fetchone()[0]
        failed_runs = self.conn.execute("SELECT COUNT(*) FROM runs WHERE status='failed'").fetchone()[0]
        tracked_issues = self.conn.execute("SELECT COUNT(*) FROM tracked_issues").fetchone()[0]
        tracked_prs = self.conn.execute("SELECT COUNT(*) FROM tracked_prs").fetchone()[0]
        return {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "tracked_issues": tracked_issues,
            "tracked_prs": tracked_prs,
        }

    def close(self) -> None:
        self.conn.close()


def load_repos() -> list[tuple[str, str]]:
    """Read decision-mapping.json and return list of (owner, repo) tuples."""
    mapping = load_decision_mapping()
    repos: list[tuple[str, str]] = []
    for tag, info in mapping.items():
        if isinstance(info, dict) and "github" in info:
            repo_full = info["github"]
            if "/" in repo_full:
                owner, repo = repo_full.split("/", 1)
                repos.append((owner, repo))
    logger.info("Loaded %d repo(s) from decision-mapping.json", len(repos))
    return repos


def _github_api_call(url: str, token: str) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Make a GitHub API call with rate-limit awareness."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            remaining = resp.headers.get("X-RateLimit-Remaining")
            reset_at = resp.headers.get("X-RateLimit-Reset")
            if remaining is not None and int(remaining) < 10:
                logger.warning("GitHub API rate limit low: %s remaining, resets at %s", remaining, reset_at)
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and "rate limit" in str(exc.reason).lower():
            logger.error("GitHub API rate limit exceeded. Retry after reset.")
        elif exc.code == 404:
            logger.warning("GitHub API 404 for %s", url)
        else:
            logger.error("GitHub API error %s for %s: %s", exc.code, url, exc.reason)
        return None
    except Exception as exc:
        logger.error("GitHub API call failed for %s: %s", url, exc)
        return None


def poll_github_issues(owner: str, repo: str, token: str, state: str = "open") -> list[dict[str, Any]]:
    """Fetch GitHub issues for a repo."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state={state}&per_page=100"
    data = _github_api_call(url, token)
    if data is None:
        return []
    if isinstance(data, list):
        issues = [i for i in data if "pull_request" not in i]
        logger.info("[%s/%s] Fetched %d issue(s)", owner, repo, len(issues))
        return issues
    return []


def poll_github_prs(owner: str, repo: str, token: str, label: str = "factory:needs-review") -> list[dict[str, Any]]:
    """Fetch open PRs with a specific label."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page=100"
    data = _github_api_call(url, token)
    if data is None:
        return []
    if isinstance(data, list):
        prs = [p for p in data if any(lbl["name"] == label for lbl in p.get("labels", []))]
        logger.info("[%s/%s] Fetched %d PR(s) with label '%s'", owner, repo, len(prs), label)
        return prs
    return []


def poll_github_prs_by_state(
    owner: str, repo: str, token: str, state: str = "open"
) -> list[dict[str, Any]]:
    """Fetch open PRs (all) for checking duplicates."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}&per_page=100"
    data = _github_api_call(url, token)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return []


def _generate_run_id() -> str:
    """Generate a unique run ID."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")[:-3]


def dispatch_archon(
    workflow: str,
    owner: str,
    repo: str,
    number: int,
    config: Config,
    state_db: StateDB,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Dispatch an Archon workflow via subprocess."""
    cwd = PROJECT_ROOT
    cmd = [
        config.archon_path,
        "workflow",
        "run",
        workflow,
        "--cwd",
        str(cwd),
        f"#{number}",
    ]
    run_id = _generate_run_id()
    logger.info(
        "[%s/%s] Dispatching %s for #%d (dry_run=%s, run_id=%s)",
        owner,
        repo,
        workflow,
        number,
        dry_run,
        run_id,
    )

    if dry_run:
        state_db.record_run(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            workflow=workflow,
            target_number=number,
            status="dry_run",
            result={"command": " ".join(cmd)},
        )
        return {"status": "dry_run", "command": " ".join(cmd), "run_id": run_id}

    env = {
        **os.environ,
        "ARCHON_SUPPRESS_NESTED_CLAUDE_WARNING": "1",
        "IS_SANDBOX": "1",
    }
    result = None
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            env=env,
            timeout=1800,  # 30 min max for complex workflows
        )
        success = proc.returncode == 0
        result = {
            "status": "success" if success else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",  # Truncate
            "stderr": proc.stderr[-4000:] if proc.stderr else "",
            "run_id": run_id,
        }
        state_db.record_run(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            workflow=workflow,
            target_number=number,
            status=result["status"],
            result=result,
        )
        return result
    except subprocess.TimeoutExpired:
        logger.error("[%s/%s] Workflow %s timed out", owner, repo, workflow)
        state_db.record_run(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            workflow=workflow,
            target_number=number,
            status="timeout",
            error="Workflow timed out after 30 minutes",
        )
        return {"status": "timeout", "run_id": run_id}
    except FileNotFoundError:
        logger.error("Archon CLI not found at '%s'", config.archon_path)
        state_db.record_run(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            workflow=workflow,
            target_number=number,
            status="archon_not_found",
            error=f"Archon CLI not found at {config.archon_path}",
        )
        return {"status": "archon_not_found", "run_id": run_id}
    except Exception as exc:
        logger.error("[%s/%s] Workflow dispatch error: %s", owner, repo, exc)
        state_db.record_run(
            run_id=run_id,
            repo_owner=owner,
            repo_name=repo,
            workflow=workflow,
            target_number=number,
            status="error",
            error=str(exc),
        )
        return {"status": "error", "error": str(exc), "run_id": run_id}


def _has_factory_label(labels: list[dict[str, str]]) -> bool:
    return any(lbl["name"].startswith("factory:") for lbl in labels)


def _has_accepted_label(labels: list[dict[str, str]]) -> bool:
    return any(lbl["name"] == "factory:accepted" for lbl in labels)


def _has_needs_review_label(labels: list[dict[str, str]]) -> bool:
    return any(lbl["name"] == "factory:needs-review" for lbl in labels)


def _has_in_progress_label(labels: list[dict[str, str]]) -> bool:
    return any(lbl["name"] == "factory:in-progress" for lbl in labels)


def _has_rate_limited_label(labels: list[dict[str, str]]) -> bool:
    return any(lbl["name"] == "factory:rate-limited" for lbl in labels)


def run_cycle(
    config: Config,
    state_db: StateDB,
    once: bool = False,
    test_repo: str | None = None,
) -> None:
    """Main orchestrator cycle."""
    logger.info("Dark Factory orchestrator starting (dry_run=%s)", config.dry_run)

    if not config.github_token:
        logger.error("GITHUB_TOKEN not set. Cannot poll GitHub.")
        return

    repos = load_repos()
    if test_repo:
        repos = [(o, r) for o, r in repos if r == test_repo]
        if not repos:
            logger.error("Test repo '%s' not found in decision-mapping.json", test_repo)
            return

    for owner, repo in repos:
        logger.info("=" * 50)
        logger.info("Processing repo: %s/%s", owner, repo)

        # ── Poll issues ──
        issues = poll_github_issues(owner, repo, config.github_token)
        untriaged = [i for i in issues if not _has_factory_label(i.get("labels", []))]
        accepted = [i for i in issues if _has_accepted_label(i.get("labels", []))]
        in_progress = [i for i in issues if _has_in_progress_label(i.get("labels", []))]
        rate_limited = [i for i in issues if _has_rate_limited_label(i.get("labels", []))]

        # Log summary
        logger.info(
            "[%s/%s] Issues: %d untriaged, %d accepted, %d in-progress, %d rate-limited",
            owner,
            repo,
            len(untriaged),
            len(accepted),
            len(in_progress),
            len(rate_limited),
        )

        # Dispatch triage for untriaged issues (batch via workflow)
        if untriaged and not config.dry_run:
            # For batch triage, we could dispatch a single triage workflow.
            # The triage workflow itself fetches issues from GitHub.
            # For now, we skip explicit triage dispatch here — the triage workflow
            # is designed to run standalone and batch-process issues.
            logger.info("[%s/%s] Untriaged issues exist — run dark-factory-triage separately", owner, repo)

        # Dispatch fix for accepted issues
        if accepted:
            for issue in accepted[: config.max_issues_per_run]:
                issue_number = issue["number"]
                last_run = state_db.get_last_run_for_issue(owner, repo, issue_number)
                if last_run and last_run["status"] in ("success", "in_progress"):
                    logger.info(
                        "[%s/%s] Issue #%d skipped — last run %s was %s",
                        owner,
                        repo,
                        issue_number,
                        last_run["run_id"],
                        last_run["status"],
                    )
                    continue

                result = dispatch_archon(
                    "dark-factory-fix-github-issue",
                    owner,
                    repo,
                    issue_number,
                    config,
                    state_db,
                    dry_run=config.dry_run,
                )
                state_db.update_issue_status(
                    owner, repo, issue_number, "dispatched", result.get("run_id")
                )

        # ── Poll PRs ──
        prs = poll_github_prs(owner, repo, config.github_token)
        if prs:
            for pr in prs[: config.max_prs_per_run]:
                pr_number = pr["number"]
                last_run = state_db.get_last_run_for_pr(owner, repo, pr_number)
                if last_run and last_run["status"] in ("success", "in_progress"):
                    logger.info(
                        "[%s/%s] PR #%d skipped — last run %s was %s",
                        owner,
                        repo,
                        pr_number,
                        last_run["run_id"],
                        last_run["status"],
                    )
                    continue

                result = dispatch_archon(
                    "dark-factory-validate-pr",
                    owner,
                    repo,
                    pr_number,
                    config,
                    state_db,
                    dry_run=config.dry_run,
                )
                state_db.update_pr_status(
                    owner, repo, pr_number, "dispatched", result.get("run_id")
                )

    logger.info("=" * 50)
    logger.info("Cycle complete.")

    stats = state_db.get_stats()
    logger.info(
        "Stats: %d total runs (%d success, %d failed), %d tracked issues, %d tracked PRs",
        stats["total_runs"],
        stats["success_runs"],
        stats["failed_runs"],
        stats["tracked_issues"],
        stats["tracked_prs"],
    )

    if once:
        return

    # Continuous mode
    logger.info("Sleeping %d minutes until next cycle...", config.poll_interval_minutes)
    time.sleep(config.poll_interval_minutes * 60)


def scaffold_governance(repo_tag: str) -> None:
    """Copy governance templates into the target repo's working directory."""
    mapping = load_decision_mapping()
    if repo_tag not in mapping:
        logger.error("Repo tag '%s' not found in decision-mapping.json", repo_tag)
        sys.exit(1)

    repo_full = mapping[repo_tag]["github"]
    if "/" not in repo_full:
        logger.error("Invalid GitHub repo format: %s", repo_full)
        sys.exit(1)

    owner, repo_name = repo_full.split("/", 1)

    # Determine the repo's local path. For repos registered in decision-mapping,
    # they may be cloned under Archon workspaces or elsewhere.
    # Default: look in the project root for a matching directory, or in the
    # Archon workspaces area.
    possible_paths = [
        PROJECT_ROOT / repo_name,
        Path.home() / ".archon" / "workspaces" / owner / repo_name / "source",
    ]
    repo_path = None
    for p in possible_paths:
        if p.exists():
            repo_path = p
            break

    if not repo_path:
        logger.error("Could not find local clone for %s. Clone it first.", repo_full)
        sys.exit(1)

    templates = {
        "FACTORY_RULES.md": TEMPLATES_DIR / "FACTORY_RULES.md",
        "MISSION.md": TEMPLATES_DIR / "MISSION.md",
        "CLAUDE.md": TEMPLATES_DIR / "CLAUDE.md",
    }

    for filename, template_path in templates.items():
        target = repo_path / filename
        if target.exists():
            logger.info("Skipping %s — already exists in %s", filename, repo_path)
            continue
        if template_path.exists():
            shutil.copy(str(template_path), str(target))
            logger.info("Copied %s -> %s", template_path, target)
        else:
            logger.warning("Template not found: %s", template_path)

    logger.info("Governance scaffolding complete for %s/%s", owner, repo_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dark Factory Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without dispatching")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--test-repo", type=str, help="Limit to a specific repo name")
    parser.add_argument("--scaffold-governance", type=str, metavar="REPO_TAG", help="Copy governance templates into the target repo")
    parser.add_argument("--stats", action="store_true", help="Show state DB stats and exit")
    args = parser.parse_args()

    if args.scaffold_governance:
        scaffold_governance(args.scaffold_governance)
        return

    config = Config()
    if args.dry_run:
        config.dry_run = True

    state_db = StateDB()

    if args.stats:
        stats = state_db.get_stats()
        print(json.dumps(stats, indent=2))
        state_db.close()
        return

    try:
        if args.once:
            run_cycle(config, state_db, once=True, test_repo=args.test_repo)
        else:
            while True:
                run_cycle(config, state_db, once=False, test_repo=args.test_repo)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down.")
    finally:
        state_db.close()


if __name__ == "__main__":
    main()
