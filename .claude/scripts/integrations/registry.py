import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Callable

# Support both `python -m integrations.query` and `python query.py` execution modes
if __name__ == "__main__" or not __package__:
    _INTEGRATIONS_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(_INTEGRATIONS_DIR))


def _import_gmail():
    try:
        from . import gmail_integration
    except ImportError:
        import gmail_integration
    return gmail_integration


def _import_slack():
    try:
        from . import slack_integration
    except ImportError:
        import slack_integration
    return slack_integration


def _import_github():
    try:
        from . import github_integration
    except ImportError:
        import github_integration
    return github_integration


def _gmail_enabled() -> bool:
    return Path("credentials.json").exists() or Path(".claude/data/token.json").exists()


def _slack_enabled() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


def _github_enabled() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN"))


_INTEGRATIONS: Dict[str, Tuple[Any, Callable[[], bool]]] = {
    "gmail": (_import_gmail, _gmail_enabled),
    "slack": (_import_slack, _slack_enabled),
    "github": (_import_github, _github_enabled),
}


def list_integrations() -> List[Tuple[str, bool]]:
    """Return (name, enabled) for every known integration."""
    return [(name, check()) for name, (_, check) in _INTEGRATIONS.items()]


def is_enabled(name: str) -> bool:
    name = name.lower()
    if name not in _INTEGRATIONS:
        return False
    _, check = _INTEGRATIONS[name]
    return check()


def get_integration(name: str):
    name = name.lower()
    if name not in _INTEGRATIONS:
        raise ValueError(f"Unknown integration '{name}'. Available: {list(_INTEGRATIONS.keys())}")
    loader, _ = _INTEGRATIONS[name]
    return loader()
