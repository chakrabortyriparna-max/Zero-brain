"""Unified CLI for all integrations.

Usage:
    python query.py gmail unread
    python query.py slack channels
    python query.py github notifications
"""

import argparse
import sys
from pathlib import Path

# Windows console encoding fix for non-ASCII output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Load .env if present
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    import dotenv
    dotenv.load_dotenv(_env_path)

try:
    from . import registry
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import registry


def main():
    parser = argparse.ArgumentParser(description="Second Brain — Integration Query CLI")
    subparsers = parser.add_subparsers(dest="platform")

    for name in ["gmail", "slack", "github"]:
        module = registry.get_integration(name)
        module.add_subparser(subparsers)

    args = parser.parse_args()

    if not args.platform:
        parser.print_help()
        sys.exit(1)

    if not registry.is_enabled(args.platform):
        print(
            f"Integration '{args.platform}' is not enabled. Check .env and credentials.",
            file=sys.stderr,
        )
        sys.exit(1)

    module = registry.get_integration(args.platform)
    module.handle_cli(args)


if __name__ == "__main__":
    main()
