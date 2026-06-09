"""
Focused multi-hop evaluation — only the files needed for 2 specific queries.
Proves whether multi-hop reasoning works without waiting for the full vault.
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


data_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_focused"
system_root = PROJECT_ROOT / ".claude" / "data" / "cognee_eval_focused_system"
data_root.mkdir(parents=True, exist_ok=True)
system_root.mkdir(parents=True, exist_ok=True)


cfg = CogneeBackendConfig(
    relational_provider="sqlite",
    relational_db_name="eval_focused_db",
    graph_provider="kuzu",
    vector_provider="lancedb",
    data_root_directory=data_root,
    system_root_directory=system_root,
    dataset_name="focused",
    llm_model="qwen2.5-coder:1.5b",
)
mem = CogneeMemory.create(config=cfg)


FILES_TO_INGEST = [
    PROJECT_ROOT / "CLAUDE.md",
    PROJECT_ROOT / "tasks" / "todo.md",
    PROJECT_ROOT / "Memory" / "MEMORY.md",
]


async def main():
    print("=" * 70)
    print("Focused multi-hop evaluation")
    print("=" * 70)
    print(f"LLM:  {cfg.llm_model} (Ollama)")
    print(f"Graph: {cfg.graph_provider} | Vector: {cfg.vector_provider} | Relational: {cfg.relational_provider}")
    print("=" * 70)

    # Ingest focused files
    batch = ""
    for fp in FILES_TO_INGEST:
        if not fp.exists():
            print(f"SKIP: {fp} not found")
            continue
        text = fp.read_text(encoding="utf-8")
        batch += f"\n\n<!-- source: {fp} -->\n{text}"
        print(f"Ingested: {fp} ({len(text)} chars)")

    print(f"\nTotal batch size: {len(batch)} chars")
    print("Adding batch...")
    await mem.ingest_text(batch, source="focused_batch")
    print("Ingestion complete.")

    print("\nBuilding graph via cognify()...")
    try:
        await mem.cognify()
        print("Graph built successfully.")
    except Exception as e:
        print(f"Graph build FAILED: {e}")
        return

    queries = [
        {
            "id": "q_focused_1",
            "text": "What skills are built for the Second Brain and which ones are still blocked by rate limits?",
            "keywords": ["skill", "rate limit", "built", "blocked"],
            "hops": 2,
        },
        {
            "id": "q_focused_2",
            "text": "What was decided about memory storage migration and has it been completed?",
            "keywords": ["memory", "migration", "storage", "completed", "decided"],
            "hops": 2,
        },
        {
            "id": "q_focused_3",
            "text": "Which integrations are built for the Second Brain and what is their authentication method?",
            "keywords": ["integration", "authentication", "oauth", "pat", "token"],
            "hops": 2,
        },
    ]

    print("\n" + "=" * 70)
    print("QUERY RESULTS")
    print("=" * 70)

    for q in queries:
        print(f"\n[{q['id']}] {q['text']}")
        print(f"  Expected hops: {q['hops']}")

        try:
            results = await mem.search(q["text"], SearchType.GRAPH_COMPLETION, top_k=5)
        except Exception as e:
            print(f"  SEARCH FAILED: {e}")
            continue

        if not results:
            print("  RESULT: No results returned.")
            continue

        joined = " ".join(results).lower()
        keyword_hits = [kw for kw in q["keywords"] if kw.lower() in joined]
        meaningful = len(joined) > 20 and len(keyword_hits) >= 1

        print(f"  RESULTS ({len(results)} items, keyword hits: {keyword_hits}):")
        for i, r in enumerate(results[:3], 1):
            preview = r.replace('\n', ' ')[:200]
            print(f"    {i}. {preview}...")

        if meaningful:
            print(f"  VERDICT: Meaningful multi-hop result")
        else:
            print(f"  VERDICT: Generic or empty (length={len(joined)})")

    print("\n" + "=" * 70)
    print("Evaluation complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
