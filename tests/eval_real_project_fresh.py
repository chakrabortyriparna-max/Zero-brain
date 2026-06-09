"""
Real-project multi-hop evaluation — fresh paths to avoid SQLite lock from orphaned processes.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "scripts"))

os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
os.environ.setdefault("CACHING", "false")

from cognee.modules.search.types import SearchType
from cognee_memory import CogneeMemory, CogneeBackendConfig


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_ROOT = PROJECT_ROOT / "Memory"


data_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_real_v2"
system_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_real_system_v2"
data_root.mkdir(parents=True, exist_ok=True)
system_root.mkdir(parents=True, exist_ok=True)


cfg = CogneeBackendConfig(
    relational_provider="sqlite",
    relational_db_name="eval_real_db_v2",
    graph_provider="kuzu",
    vector_provider="lancedb",
    data_root_directory=data_root,
    system_root_directory=system_root,
    dataset_name="real_project",
    llm_model="qwen2.5-coder:1.5b",
)
mem = CogneeMemory.create(config=cfg)


async def main():
    print("=" * 70)
    print("Ingesting real project vault...")
    print(f"Root: {MEMORY_ROOT}")
    if not MEMORY_ROOT.exists():
        print("ERROR: Memory/ directory not found")
        return

    files = sorted(MEMORY_ROOT.glob("**/*.md"))
    print(f"Found {len(files)} markdown files.")

    # Batch ingestion: concatenate all files with provenance headers to avoid N pipeline runs
    batch_text = ""
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
            batch_text += f"\n\n<!-- source: {fp} -->\n{text}"
        except Exception as exc:
            print(f"[read error] {fp}: {exc}", file=sys.stderr)

    print(f"Batch text size: {len(batch_text)} chars")
    print("Adding batch to Cognee dataset...")
    await mem.ingest_text(batch_text, source="batch_vault")
    print("Batch ingestion complete.")

    print("\nBuilding graph via cognify()...")
    try:
        await mem.cognify()
        print("Graph built successfully.")
    except Exception as e:
        print(f"Graph build FAILED: {e}")
        return

    queries = [
        {
            "id": "q_real_1",
            "text": "What is the status of the Cognee graph-vector hybrid memory project and what blockers remain?",
            "required_files": ["Memory/projects/cognee-memory-prd.md", "Memory/projects/cognee-fixes-prd.md", "tasks/todo.md"],
            "hops": 3,
        },
        {
            "id": "q_real_2",
            "text": "Which person leads the project that uses PostgreSQL and had an outage on Tuesday?",
            "required_files": ["Memory/team/", "Memory/projects/", "Memory/daily/"],
            "hops": 3,
        },
        {
            "id": "q_real_3",
            "text": "What skills are built for the Second Brain and which ones are still blocked by rate limits?",
            "required_files": ["CLAUDE.md", "tasks/todo.md"],
            "hops": 2,
        },
        {
            "id": "q_real_4",
            "text": "What was decided about memory storage migration and has it been completed?",
            "required_files": ["Memory/MEMORY.md", "CLAUDE.md"],
            "hops": 2,
        },
        {
            "id": "q_real_5",
            "text": "Which integrations are built for the Second Brain and what is their authentication method?",
            "required_files": ["CLAUDE.md", ".env"],
            "hops": 2,
        },
    ]

    print("\n" + "=" * 70)
    print("Multi-Hop Query Results — REAL PROJECT DATA")
    print("=" * 70)
    print(f"LLM Config: provider=ollama, model={cfg.llm_model}, endpoint={cfg.llm_endpoint}")
    print(f"Graph: {cfg.graph_provider}, Vector: {cfg.vector_provider}, Relational: {cfg.relational_provider}")
    print("=" * 70)

    for q in queries:
        print(f"\n[{q['id']}] {q['text']}")
        print(f"  Expected hops: {q['hops']} | Files: {', '.join(q['required_files'])}")

        try:
            results = await mem.search(q["text"], SearchType.GRAPH_COMPLETION, top_k=5)
        except Exception as e:
            print(f"  SEARCH FAILED: {e}")
            continue

        if not results:
            print("  RESULT: No results returned.")
            continue

        joined = " ".join(results).lower()
        meaningful = len(joined) > 20 and any(
            kw in joined
            for kw in ["project", "memory", "cognee", "skill", "integration", "outage", "alice", "bob", "status"]
        )

        print(f"  RESULTS ({len(results)} items):")
        for i, r in enumerate(results[:3], 1):
            preview = r.replace('\n', ' ')[:120]
            print(f"    {i}. {preview}...")

        if meaningful:
            print(f"  VERDICT: Returned meaningful content (length={len(joined)})")
        else:
            print(f"  VERDICT: Returned generic or empty content (length={len(joined)})")

    print("\n" + "=" * 70)
    print("Evaluation complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
