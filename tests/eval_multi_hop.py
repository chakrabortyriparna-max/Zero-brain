"""
Multi-hop evaluation harness for Cognee graph-vector hybrid memory.

Tests the ability to answer relational questions that require traversing
multiple hops across the knowledge graph.

Usage:
    python -m pytest tests/eval_multi_hop.py -v -m "not slow"
    python -m pytest tests/eval_multi_hop.py -v -m slow          # requires Cognee + LLM

Metrics:
    - Accuracy: did the result contain the expected connection?
    - Baseline comparison: sqlite-vec hybrid search vs Cognee GRAPH_COMPLETION
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "scripts"))

from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
from cognee.modules.search.types import SearchType

from cognee_memory import CogneeMemory, CogneeBackendConfig  # noqa: E402

os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")


# ═══════════════════════════════════════════════════════════════════
# Test data: synthetic vault for controlled evaluation
# ═══════════════════════════════════════════════════════════════════

SAMPLE_VAULT = [
    {
        "path": "Memory/team/alice.md",
        "text": (
            "# Alice\n\n"
            "Alice is the tech lead on Project Atlas.\n"
            "She reports to Carol, the VP of Engineering.\n"
            "Alice specializes in distributed systems and PostgreSQL.\n"
        ),
    },
    {
        "path": "Memory/projects/project_atlas.md",
        "text": (
            "# Project Atlas\n\n"
            "Project Atlas is the flagship AI platform.\n"
            "It uses PostgreSQL as its primary datastore.\n"
            "The infrastructure runs on AWS us-east-1.\n"
            "Alice is the tech lead; Bob is the DevOps engineer.\n"
        ),
    },
    {
        "path": "Memory/daily/2026-05-20.md",
        "text": (
            "# Daily Log — 2026-05-20\n\n"
            "## Incidents\n"
            "- The PostgreSQL cluster in AWS us-east-1 experienced a 15-minute outage at 14:30 UTC.\n"
            "- Bob was paged and resolved the issue by failing over to the replica.\n"
            "- Carol approved the post-mortem.\n"
        ),
    },
    {
        "path": "Memory/research/rag_papers.md",
        "text": (
            "# RAG Research\n\n"
            "Recent papers show that multi-hop reasoning improves retrieval accuracy by 40%.\n"
            "Project Atlas is evaluating Cognee for graph-vector hybrid memory.\n"
            "Alice presented the findings to Carol last Tuesday.\n"
        ),
    },
    {
        "path": "Memory/drafts/sent/client_alpha.md",
        "text": (
            "# Sent Email — Client Alpha\n\n"
            "Hi Alpha team,\n\n"
            "Following Tuesday's outage, we have hardened the PostgreSQL failover automation.\n"
            "Project Atlas is now resilient to replica lag.\n"
            "Best,\nAlice\n"
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════
# Evaluation questions
# ═══════════════════════════════════════════════════════════════════

EVAL_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "q1",
        "query": "Was Alice affected by the Tuesday outage?",
        "expected": {"alice", "outage", "tuesday", "postgresql"},
        "required_hops": 3,  # Alice -> Project Atlas -> PostgreSQL -> outage
    },
    {
        "id": "q2",
        "query": "Who resolved the database outage on Tuesday?",
        "expected": {"bob"},
        "required_hops": 2,  # outage -> PostgreSQL -> Bob
    },
    {
        "id": "q3",
        "query": "What project uses PostgreSQL and had an outage?",
        "expected": {"project atlas", "atlas"},
        "required_hops": 2,
    },
    {
        "id": "q4",
        "query": "Who approved the post-mortem for the outage?",
        "expected": {"carol"},
        "required_hops": 2,
    },
    {
        "id": "q5",
        "query": "What technology does Alice specialize in that is also used by Project Atlas?",
        "expected": {"postgresql"},
        "required_hops": 2,
    },
    {
        "id": "q6",
        "query": "Which client was told about the PostgreSQL failover hardening?",
        "expected": {"alpha"},
        "required_hops": 2,
    },
    {
        "id": "q7",
        "query": "What AWS region runs the infrastructure for the project Alice leads?",
        "expected": {"us-east-1", "aws"},
        "required_hops": 2,
    },
    {
        "id": "q8",
        "query": "Who is the VP that Alice reports to?",
        "expected": {"carol"},
        "required_hops": 1,
    },
    {
        "id": "q9",
        "query": "What system had an outage that involved Bob?",
        "expected": {"postgresql", "database"},
        "required_hops": 2,
    },
    {
        "id": "q10",
        "query": "Which project is evaluating graph-vector hybrid memory?",
        "expected": {"project atlas", "atlas"},
        "required_hops": 1,
    },
    {
        "id": "q11",
        "query": "Who presented RAG research findings to Carol?",
        "expected": {"alice"},
        "required_hops": 2,
    },
    {
        "id": "q12",
        "query": "What datastore does Project Atlas use?",
        "expected": {"postgresql"},
        "required_hops": 1,
    },
    {
        "id": "q13",
        "query": "Who was paged when the PostgreSQL cluster had issues?",
        "expected": {"bob"},
        "required_hops": 2,
    },
    {
        "id": "q14",
        "query": "What day did the PostgreSQL outage happen?",
        "expected": {"tuesday"},
        "required_hops": 1,
    },
    {
        "id": "q15",
        "query": "Who leads the project that runs on AWS?",
        "expected": {"alice"},
        "required_hops": 2,
    },
    {
        "id": "q16",
        "query": "What did Alice tell Client Alpha about?",
        "expected": {"postgresql", "outage", "failover"},
        "required_hops": 2,
    },
    {
        "id": "q17",
        "query": "Who is responsible for infrastructure on Project Atlas?",
        "expected": {"bob"},
        "required_hops": 2,
    },
    {
        "id": "q18",
        "query": "What project involves both Alice and Bob?",
        "expected": {"project atlas", "atlas"},
        "required_hops": 2,
    },
    {
        "id": "q19",
        "query": "Which VP oversees the project that had the outage?",
        "expected": {"carol"},
        "required_hops": 3,  # VP -> Alice -> Project Atlas -> outage -> post-mortem -> Carol
    },
    {
        "id": "q20",
        "query": "What research topic is relevant to Project Atlas's memory evaluation?",
        "expected": {"rag", "multi-hop", "graph-vector", "cognee"},
        "required_hops": 2,
    },
]


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def eval_cognee(tmp_path_factory):
    """Create a CogneeMemory instance with synthetic vault data."""
    tmp_path = tmp_path_factory.mktemp("eval_cognee")
    data_root = tmp_path / "data_storage"
    system_root = tmp_path / "system"
    data_root.mkdir(parents=True)
    system_root.mkdir(parents=True)

    cfg = CogneeBackendConfig(
        relational_provider="sqlite",
        relational_db_name="eval_cognee_db",
        graph_provider="kuzu",
        vector_provider="lancedb",
        data_root_directory=data_root,
        system_root_directory=system_root,
        dataset_name="eval",
        llm_model="qwen2.5-coder:1.5b",
    )
    mem = CogneeMemory.create(config=cfg)

    # Build temporary vault directory
    vault_dir = tmp_path / "vault" / "Memory"
    vault_dir.mkdir(parents=True)
    for item in SAMPLE_VAULT:
        fp = vault_dir / item["path"]
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(item["text"], encoding="utf-8")

    return mem, vault_dir


# ═══════════════════════════════════════════════════════════════════
# Baseline: sqlite-vec hybrid search
# ═══════════════════════════════════════════════════════════════════

def _score_results(results: list[str], expected: set[str]) -> float:
    """Score 0.0–1.0 based on how many expected keywords appear in results."""
    if not results:
        return 0.0
    joined = " ".join(results).lower()
    hits = sum(1 for kw in expected if kw.lower() in joined)
    return hits / len(expected)


@pytest.mark.baseline
class TestBaselineHybrid:
    """Evaluate the legacy sqlite-vec + FTS5 stack as a baseline."""

    def test_baseline_q1(self):
        from db import SQLiteBackend
        from embeddings import Embedder

        q = EVAL_QUESTIONS[0]
        embedder = Embedder()
        # Baseline uses a minimal in-memory DB populated from sample text
        db_path = Path(__file__).resolve().parent / ".eval_baseline.db"
        with SQLiteBackend(str(db_path)) as db:
            # Insert a single aggregated chunk
            text = "\n\n".join(item["text"] for item in SAMPLE_VAULT)
            emb = embedder.embed_query(text)
            db.insert_chunk(
                file_path="eval/all.md",
                chunk_text=text,
                embedding=emb,
                file_hash="eval",
                updated_at="2026-05-26T00:00:00",
            )
            qemb = embedder.embed_query(q["query"])
            results = db.search_hybrid(qemb, q["query"], top_k=5)
            score = _score_results([r["chunk_text"] for r in results], q["expected"])
            print(f"\n[q1 baseline] score={score:.2f}")
            # Baseline is expected to struggle with multi-hop; record the score
            assert score >= 0.0  # always true; we record the metric

        # Cleanup
        db_path.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
# Cognee GRAPH_COMPLETION evaluation
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestCogneeMultiHop:
    """Evaluate Cognee GRAPH_COMPLETION on multi-hop questions."""

    @pytest.mark.asyncio
    async def test_cognee_setup(self, eval_cognee):
        mem, vault_dir = eval_cognee
        await mem.ingest_directory(vault_dir)
        await mem.cognify()

    @pytest.mark.asyncio
    async def test_q1_alice_outage(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[0]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5, f"Expected at least 50% keyword coverage, got {score}"

    @pytest.mark.asyncio
    async def test_q2_bob_resolved(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[1]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q3_project_postgres(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[2]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q4_carol_approved(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[3]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q5_alice_specialty(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[4]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q6_client_alpha(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[5]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q7_aws_region(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[6]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q8_vp_alice(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[7]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q9_bob_system(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[8]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q10_hybrid_memory(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[9]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q11_alice_rag(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[10]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q12_datastore(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[11]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q13_bob_paged(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[12]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q14_outage_day(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[13]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q15_alice_aws(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[14]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q16_alpha_topic(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[15]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q17_bob_infra(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[16]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q18_alice_bob(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[17]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q19_vp_outage(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[18]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_q20_research_topic(self, eval_cognee):
        mem, _ = eval_cognee
        q = EVAL_QUESTIONS[19]
        results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
        score = _score_results(results, q["expected"])
        print(f"\n[{q['id']}] score={score:.2f}")
        assert score >= 0.5


# ═══════════════════════════════════════════════════════════════════
# Benchmark summary
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
class TestBenchmarkSummary:
    @pytest.mark.asyncio
    async def test_run_all_and_report(self, eval_cognee):
        """Run all 20 questions and print a summary report."""
        mem, _ = eval_cognee
        scores: list[float] = []
        print("\n" + "=" * 60)
        print("Multi-Hop Eval Summary")
        print("=" * 60)
        for q in EVAL_QUESTIONS:
            results = await mem.search(q["query"], SearchType.GRAPH_COMPLETION, top_k=5)
            score = _score_results(results, q["expected"])
            scores.append(score)
            status = "PASS" if score >= 0.5 else "FAIL"
            print(f"  [{q['id']}] {status}  score={score:.2f}  hops={q['required_hops']}  \"{q['query'][:50]}...\"")

        avg = sum(scores) / len(scores)
        passed = sum(1 for s in scores if s >= 0.5)
        print("-" * 60)
        print(f"  Average score: {avg:.2f}")
        print(f"  Passed:        {passed}/{len(scores)}")
        print(f"  Accuracy:      {passed / len(scores) * 100:.1f}%")
        print("=" * 60)

        assert avg >= 0.4, f"Expected average score >= 0.4, got {avg}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
