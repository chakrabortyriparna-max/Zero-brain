"""Template for adding a new integration.

Copy this file, rename it to <platform>_integration.py, and fill in:
- dataclass model(s)
- auth function
- query functions
- context formatter
- add_subparser() + handle_cli()

Then register it in registry.py.
"""

import argparse
from dataclasses import dataclass
from typing import List


@dataclass
class ExampleItem:
    id: str
    title: str
    body: str


def get_client():
    """Authenticate and return an API client."""
    raise NotImplementedError("Fill in auth logic here.")


def list_items() -> List[ExampleItem]:
    """Fetch items from the platform."""
    raise NotImplementedError("Fill in query logic here.")


def format_items(items: List[ExampleItem]) -> str:
    """Return a markdown-formatted summary for the LLM."""
    lines = [f"### {item.title}\n{item.body}\n" for item in items]
    return "\n".join(lines)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser("example", help="Example integration commands")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List items")


def handle_cli(args: argparse.Namespace) -> None:
    if args.command == "list":
        items = list_items()
        print(format_items(items))
    else:
        print("Unknown command. Use: list")
