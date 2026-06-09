"""
Resume real-project multi-hop evaluation from already-ingested data.
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

data_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_real"
system_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_real_system"

cfg = CogneeBackendConfig(
    relational_provider="sqlite",
    relational_db_name="eval_real_db",
    graph_provider="kuzu",
    vector_provider="lancedb",
    data_root_directory=data_root,
    system_root_directory=system_root,
    dataset_name="real_project",
    llm_model="qwen2.5-coder:1.5b",
)
mem = CogneeMemory.create(config=cfg)

async def main():
    print("Building graph via cognify()...")
    try:
        await mem.cognify()
        print("Graph built successfully.")
    except Exception as e:
        print(f"Graph build FAILED: {e}")
        return

    queries = [
        "What is the status of the Cognee graph-vector hybrid memory project and what blockers remain?",
        "Which person leads the project that uses PostgreSQL and had an outage on Tuesday?",
        "What skills are built for the Second Brain and which ones are still blocked by rate limits?",
        "What was decided about memory storage migration and has it been completed?",
        "Which integrations are built for the Second Brain and what is their authentication method?",
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n[Q{i}] {q}")
        try:
            results = await mem.search(q, SearchType.GRAPH_COMPLETION, top_k=5)
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
        print(f"  RESULTS ({len(results)} items, meaningful={meaningful}):")
        for j, r in enumerate(results[:3], 1):
            preview = r.replace('\n', ' ')[:200]
            print(f"    {j}. {preview}...")

    print("\nEvaluation complete.")


if __name__ == "__main__":
    asyncio.run(main())
