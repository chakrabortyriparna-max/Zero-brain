"""Dark Factory configuration."""

import json
import os
from pathlib import Path
from typing import Any

# Base paths
MODULE_DIR = Path(__file__).parent.resolve()
COMMANDS_DIR = MODULE_DIR / "commands"
WORKFLOWS_DIR = MODULE_DIR / "workflows"
TEMPLATES_DIR = MODULE_DIR / "templates"
STATE_DB_PATH = MODULE_DIR / "state.db"
LOGS_DIR = MODULE_DIR / "logs"

# Decision mapping path (existing Second Brain registry)
DECISION_MAPPING_PATH = (
    Path.home()
    / "OneDrive"
    / "Desktop"
    / "zero BRAIN"
    / "second-brain-starter"
    / ".claude"
    / "data"
    / "decision-mapping.json"
)

# Defaults
DEFAULT_POLL_INTERVAL_MINUTES = 30
DEFAULT_MAX_ISSUES_PER_RUN = 3
DEFAULT_MAX_PRS_PER_RUN = 2
DEFAULT_DRY_RUN = False

# Env / file config keys
ENV_PREFIX = "DARK_FACTORY_"


class Config:
    """Runtime configuration for the Dark Factory orchestrator."""

    def __init__(self) -> None:
        self.archon_path: str = self._get("ARCHON_PATH", "archon")
        self.poll_interval_minutes: int = int(
            self._get("POLL_INTERVAL_MINUTES", str(DEFAULT_POLL_INTERVAL_MINUTES))
        )
        self.max_issues_per_run: int = int(
            self._get("MAX_ISSUES_PER_RUN", str(DEFAULT_MAX_ISSUES_PER_RUN))
        )
        self.max_prs_per_run: int = int(
            self._get("MAX_PRS_PER_RUN", str(DEFAULT_MAX_PRS_PER_RUN))
        )
        self.dry_run: bool = self._get("DRY_RUN", "false").lower() in ("1", "true", "yes")
        self.github_token: str = os.environ.get("GITHUB_TOKEN", "")
        self.openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")

    def _get(self, key: str, default: str) -> str:
        """Read env var with DARK_FACTORY_ prefix, fallback to default."""
        return os.environ.get(f"{ENV_PREFIX}{key}", default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archon_path": self.archon_path,
            "poll_interval_minutes": self.poll_interval_minutes,
            "max_issues_per_run": self.max_issues_per_run,
            "max_prs_per_run": self.max_prs_per_run,
            "dry_run": self.dry_run,
            "github_token_present": bool(self.github_token),
            "openrouter_api_key_present": bool(self.openrouter_api_key),
        }


def load_decision_mapping() -> dict[str, Any]:
    """Load the Second Brain decision-mapping.json registry.

    Returns only entries where dark_factory is not explicitly false.
    Entries missing the dark_factory key default to enabled.
    """
    if not DECISION_MAPPING_PATH.exists():
        return {}
    with open(DECISION_MAPPING_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    filtered: dict[str, Any] = {}
    for tag, meta in raw.items():
        if tag.startswith("_"):
            continue
        if not isinstance(meta, dict):
            continue
        if not meta.get("github"):
            continue
        # dark_factory defaults to True unless explicitly set to false
        if meta.get("dark_factory", True) is False:
            continue
        filtered[tag] = meta
    return filtered
