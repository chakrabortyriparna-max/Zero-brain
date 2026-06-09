#!/usr/bin/env python3
"""
Cognee Indexer CLI for Second Brain.

Incrementally indexes the Memory/ vault into Cognee's graph-vector hybrid store.
Mirrors the behaviour of memory_index.py (SHA-256 hashing, incremental updates)
but targets Cognee instead of sqlite-vec.

Usage:
    python cognee_index.py                    # normal run
    python cognee_index.py --dry-run          # preview only
    python cognee_index.py --cognify          # index + build graph
    python cognee_index.py --prune            # wipe all Cognee data
    python cognee_index.py --benchmark        # measure indexing latency
    python cognee_index.py --postgres-url ... # production stack
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from cognee_memory import CogneeMemory, CogneeBackendConfig, create_memory

IST = timezone(timedelta(hours=5, minutes=30))
MEMORY_ROOT = PROJECT_ROOT / "Memory"
STATE_FILE = PROJECT_ROOT / ".claude" / "data" / "state" / "cognee-index-state.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_state() -> dict[str, str]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


async def index_vault(
    mem: CogneeMemory,
    memory_root: Path,
    dry_run: bool = False,
    cognify: bool = False,
    benchmark: bool = False,
) -> dict[str, int]:
    """Walk Memory/ and ingest changed files."""
    state = load_state()
    files = sorted(memory_root.rglob("*.md"))

    total_new = 0
    total_updated = 0
    total_unchanged = 0
    ingest_count = 0

    t0 = time.perf_counter()

    for fp in files:
        rel = fp.relative_to(PROJECT_ROOT).as_posix()
        current_hash = sha256_file(fp)
        stored_hash = state.get(rel)

        if stored_hash == current_hash:
            total_unchanged += 1
            continue

        if dry_run:
            action = "new" if stored_hash is None else "updated"
            print(f"[{action}] {rel}")
            total_new += 1
            continue

        try:
            await mem.ingest_file(fp)
            state[rel] = current_hash
            ingest_count += 1
            if stored_hash is None:
                total_new += 1
                print(f"[ingested] {rel}")
            else:
                total_updated += 1
                print(f"[re-ingested] {rel}")
        except Exception as exc:
            print(f"[ERROR] {rel}: {exc}", file=sys.stderr)

    if not dry_run and ingest_count > 0:
        save_state(state)

    if cognify and not dry_run and ingest_count > 0:
        print("\n[COGNIFY] Building graph + embeddings...")
        c0 = time.perf_counter()
        await mem.cognify()
        c1 = time.perf_counter()
        print(f"[COGNIFY] Done in {c1 - c0:.2f}s")

    t1 = time.perf_counter()
    duration = t1 - t0

    stats = {
        "new": total_new,
        "updated": total_updated,
        "unchanged": total_unchanged,
        "ingested": ingest_count,
        "duration_sec": round(duration, 2),
    }

    if benchmark:
        print(f"\nBenchmark: {duration:.2f}s for {len(files)} files ({ingest_count} ingested)")

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Index Memory/ vault into Cognee.")
    parser.add_argument("--memory-root", type=Path, default=MEMORY_ROOT, help="Path to Memory directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
    parser.add_argument("--cognify", action="store_true", help="Run cognify() after indexing")
    parser.add_argument("--prune", action="store_true", help="Wipe all Cognee data before indexing")
    parser.add_argument("--benchmark", action="store_true", help="Measure and report latency")
    parser.add_argument("--postgres-url", default=None, help="Production PostgreSQL connection string")
    parser.add_argument("--no-supabase", dest="use_supabase", action="store_false", default=True, help="Force local SQLite instead of Supabase")
    parser.add_argument("--graph-provider", default="falkor", help="Graph DB: kuzu | falkor | neo4j")
    parser.add_argument("--vector-provider", default="lancedb", help="Vector DB: lancedb | pgvector")
    parser.add_argument("--llm-model", default="nemotron-3-super:cloud", help="Ollama model tag")
    parser.add_argument("--dataset", default="main", help="Cognee dataset name")
    args = parser.parse_args()

    # Isolate Cognee env to prevent reading project .env tokens
    os.environ.setdefault("COGNEE_ENV_FILE", str(PROJECT_ROOT / ".claude" / "data" / "cognee" / ".env"))

    if args.prune:
        mem = create_memory()
        print("[PRUNE] Wiping Cognee data + system state...")
        await mem.prune()
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        print("[PRUNE] Done.")
        return

    mem = create_memory(
        relational_url=args.postgres_url,
        graph_provider=args.graph_provider,
        vector_provider=args.vector_provider,
        llm_model=args.llm_model,
        dataset=args.dataset,
        use_supabase=args.use_supabase,
    )

    memory_root = args.memory_root.resolve()
    if not memory_root.exists():
        print(f"Memory root not found: {memory_root}")
        sys.exit(1)

    stats = await index_vault(
        mem,
        memory_root,
        dry_run=args.dry_run,
        cognify=args.cognify,
        benchmark=args.benchmark,
    )

    print(
        f"\nDone: {stats['new']} new, {stats['updated']} updated, {stats['unchanged']} unchanged."
        f" Ingested: {stats['ingested']} files in {stats['duration_sec']}s."
    )


if __name__ == "__main__":
    asyncio.run(main())
