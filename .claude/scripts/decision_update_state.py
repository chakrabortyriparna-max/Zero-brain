#!/usr/bin/env python3
"""Update idempotency state so decisions are not re-processed on subsequent runs."""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))


def _safe_load_json(path: str, default: dict | None = None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _atomic_write_json(path: str, data: dict):
    """Write JSON atomically to avoid corruption on crash."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser(description="Update decision validator state")
    parser.add_argument("--decisions", required=True, help="Path to decisions JSON")
    parser.add_argument("--state-file", required=True, help="Path to state JSON")
    args = parser.parse_args()

    with open(args.decisions, "r", encoding="utf-8") as f:
        decisions = json.load(f)

    state = _safe_load_json(args.state_file, {"processed_hashes": [], "feedback_log": []})

    added = 0
    for d in decisions:
        h = d.get("decision_hash")
        if h and h not in state["processed_hashes"]:
            state["processed_hashes"].append(h)
            added += 1

    # Trim to last 500 hashes to prevent unbounded growth
    if len(state["processed_hashes"]) > 500:
        state["processed_hashes"] = state["processed_hashes"][-500:]

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(args.state_file)), exist_ok=True)
    _atomic_write_json(args.state_file, state)

    print(f"Added {added} new decision hash(es). Total tracked: {len(state['processed_hashes'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
