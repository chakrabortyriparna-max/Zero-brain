"""Tests for .claude/dark-factory/orchestrator.py."""
import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

DF_DIR = Path(__file__).resolve().parent.parent / ".claude" / "dark-factory"
sys.path.insert(0, str(DF_DIR))

from config import Config  # noqa: E402
from orchestrator import StateDB, load_repos, _github_api_call, dispatch_archon  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.poll_interval_minutes == 30
        assert c.max_issues_per_run == 3
        assert c.max_prs_per_run == 2
        assert c.dry_run is False

    @patch.dict(
        "os.environ",
        {
            "DARK_FACTORY_POLL_INTERVAL_MINUTES": "60",
            "DARK_FACTORY_MAX_ISSUES_PER_RUN": "5",
            "DARK_FACTORY_DRY_RUN": "true",
        },
    )
    def test_env_override(self):
        c = Config()
        assert c.poll_interval_minutes == 60
        assert c.max_issues_per_run == 5
        assert c.dry_run is True


class TestLoadDecisionMapping:
    def test_filters_disabled_repos(self, tmp_path: Path):
        from config import load_decision_mapping
        mapping = {
            "enabled": {"github": "riparna/enabled", "dark_factory": True},
            "default": {"github": "riparna/default"},
            "disabled": {"github": "riparna/disabled", "dark_factory": False},
            "no-github": {"slack": "C123"},
        }
        fake_path = tmp_path / "decision-mapping.json"
        fake_path.write_text(json.dumps(mapping), encoding="utf-8")
        with patch("config.DECISION_MAPPING_PATH", fake_path):
            result = load_decision_mapping()
        assert "enabled" in result
        assert "default" in result
        assert "disabled" not in result
        assert "no-github" not in result


class TestLoadRepos:
    def test_empty_when_file_missing(self):
        with patch("orchestrator.load_decision_mapping", return_value={}):
            repos = load_repos()
            assert repos == []

    def test_loads_enabled_repos(self):
        mapping = {
            "second-brain": {
                "github": "riparna/second-brain-starter",
                "slack": "C123",
            },
            "archon": {
                "github": "riparna/archon",
                "slack": "C456",
            },
        }
        with patch("orchestrator.load_decision_mapping", return_value=mapping):
            repos = load_repos()
        assert len(repos) == 2
        assert ("riparna", "second-brain-starter") in repos
        assert ("riparna", "archon") in repos

    def test_skips_missing_github(self):
        mapping = {
            "no-repo": {"slack": "C123"},
            "valid": {"github": "riparna/valid", "slack": "C456"},
        }
        with patch("orchestrator.load_decision_mapping", return_value=mapping):
            repos = load_repos()
        assert repos == [("riparna", "valid")]


class TestStateDB:
    def test_tables_created(self, tmp_path: Path):
        db_path = tmp_path / "state.db"
        db = StateDB(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "runs" in tables
        assert "tracked_issues" in tables
        assert "tracked_prs" in tables
        conn.close()
        db.close()

    def test_insert_and_fetch_run(self, tmp_path: Path):
        db_path = tmp_path / "state.db"
        db = StateDB(db_path)
        db.record_run(
            run_id="r1",
            repo_owner="riparna",
            repo_name="repo",
            workflow="triage",
            target_number=42,
            status="success",
        )
        stats = db.get_stats()
        assert stats["total_runs"] == 1
        assert stats["success_runs"] == 1
        db.close()

    def test_issue_tracking(self, tmp_path: Path):
        db_path = tmp_path / "state.db"
        db = StateDB(db_path)
        db.update_issue_status("riparna", "repo", 42, "dispatched", run_id="r1")
        rows = db.conn.execute(
            "SELECT * FROM tracked_issues WHERE issue_number = 42"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["repo_owner"] == "riparna"
        db.close()

    def test_pr_tracking(self, tmp_path: Path):
        db_path = tmp_path / "state.db"
        db = StateDB(db_path)
        db.update_pr_status("riparna", "repo", 7, "dispatched", run_id="r1")
        rows = db.conn.execute(
            "SELECT * FROM tracked_prs WHERE pr_number = 7"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["repo_owner"] == "riparna"
        db.close()


class TestGitHubAPICall:
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"})
    @patch("urllib.request.urlopen")
    def test_successful_call(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([{"id": 1, "title": "Bug"}]).encode()
        mock_response.status = 200
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = _github_api_call("https://api.github.com/repos/riparna/repo/issues", "test-token")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Bug"

    def test_raises_without_token(self):
        result = _github_api_call("https://api.github.com/repos/riparna/repo/issues", "")
        assert result is None


class TestDispatchArchon:
    @patch("subprocess.run")
    def test_dry_run_skips_execution(self, mock_run, tmp_path: Path):
        db = StateDB(tmp_path / "state.db")
        cfg = Config()
        result = dispatch_archon(
            "dark-factory-triage",
            "riparna",
            "repo",
            number=42,
            config=cfg,
            state_db=db,
            dry_run=True,
        )
        mock_run.assert_not_called()
        assert result["status"] == "dry_run"
        db.close()

    @patch("subprocess.run")
    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"})
    def test_executes_archon(self, mock_run, tmp_path: Path):
        db = StateDB(tmp_path / "state.db")
        cfg = Config()
        mock_run.return_value = MagicMock(returncode=0, stdout="Done", stderr="")
        result = dispatch_archon(
            "dark-factory-triage",
            "riparna",
            "repo",
            number=42,
            config=cfg,
            state_db=db,
            dry_run=False,
        )
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "dark-factory-triage" in call_args[0][0]
        assert result["status"] == "success"
        db.close()
