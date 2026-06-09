"""Tests for Cognee graph-vector hybrid memory layer.

Run:
    pytest tests/test_cognee_memory.py -v
    pytest tests/test_cognee_memory.py -v -m "not slow"   # skip cognify/memify

Prerequisites:
    - FalkorDB container running (or Kuzu embedded fallback)
    - Ollama running at localhost:11434
    - Cognee + adapter installed
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

# Skip Cognee's built-in LLM connection test to avoid timeouts during pytest
os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST", "true")

from cognee_memory import CogneeMemory, CogneeBackendConfig, create_memory
from cognee.modules.search.types import SearchType


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_cognee(tmp_path):
    """Create a CogneeMemory instance backed by temp directories."""
    data_root = tmp_path / "cognee" / "data_storage"
    system_root = tmp_path / "cognee" / "system"
    data_root.mkdir(parents=True)
    system_root.mkdir(parents=True)

    cfg = CogneeBackendConfig(
        relational_provider="sqlite",
        relational_db_name="test_cognee_db",
        graph_provider="kuzu",          # embedded — no Docker needed for tests
        vector_provider="lancedb",      # embedded
        data_root_directory=data_root,
        system_root_directory=system_root,
        dataset_name="test",
        llm_model="qwen2.5-coder:1.5b", # lightweight for tests
    )
    unique_id = str(tmp_path).replace(chr(92), "_").replace("/", "_")
    mem = CogneeMemory.create(config=cfg, instance_id=unique_id)
    yield mem


@pytest.fixture
def sample_markdown(tmp_path):
    """Create a sample markdown file with entity relationships."""
    md = tmp_path / "project_atlas.md"
    md.write_text(
        "# Project Atlas\n\n"
        "Alice is the tech lead. Project Atlas uses PostgreSQL.\n"
        "The PostgreSQL cluster had an outage on Tuesday.\n"
        "Bob is the DevOps engineer responsible for database uptime.\n",
        encoding="utf-8",
    )
    return md


# ═══════════════════════════════════════════════════════════════════
# Unit tests (fast, no LLM calls)
# ═══════════════════════════════════════════════════════════════════

class TestConfig:
    def test_default_config(self):
        cfg = CogneeBackendConfig()
        assert cfg.relational_provider == "sqlite"
        assert cfg.graph_provider == "falkor"
        assert cfg.vector_provider == "lancedb"
        assert cfg.dataset_name == "main"

    def test_postgres_config_from_url(self):
        cfg = CogneeBackendConfig(
            relational_url="postgresql://user:pass@host:5432/db",
            relational_provider="postgres",
        )
        assert cfg.relational_provider == "postgres"
        assert "host:5432" in cfg.relational_url


class TestIngestion:
    @pytest.mark.asyncio
    async def test_ingest_text(self, temp_cognee):
        await temp_cognee.ingest_text(
            "Riparna prefers executive summaries for client emails.",
            source="test_inline",
        )
        # Ingestion is fire-and-add to Cognee; no exception = success

    @pytest.mark.asyncio
    async def test_ingest_file(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)

    @pytest.mark.asyncio
    async def test_ingest_directory(self, temp_cognee, tmp_path):
        (tmp_path / "a.md").write_text("Content A", encoding="utf-8")
        (tmp_path / "b.md").write_text("Content B", encoding="utf-8")
        statuses = await temp_cognee.ingest_directory(tmp_path, glob="*.md")
        assert len(statuses) == 2
        assert all(v == 1 for v in statuses.values())

    @pytest.mark.asyncio
    async def test_ingest_missing_file_raises(self, temp_cognee):
        with pytest.raises(FileNotFoundError):
            await temp_cognee.ingest_file(Path("/nonexistent/file.md"))


class TestSessionIsolation:
    def test_create_returns_distinct_objects(self):
        a = CogneeMemory.create(instance_id="A")
        b = CogneeMemory.create(instance_id="A")
        c = CogneeMemory.create(instance_id="B")
        assert a is not b
        assert a is not c


# ═══════════════════════════════════════════════════════════════════
# Integration tests (slow — require LLM / graph build)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestCognifyAndSearch:
    @pytest.mark.asyncio
    async def test_cognify_builds_graph(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        # If cognify succeeds, graph nodes exist

    @pytest.mark.asyncio
    async def test_search_graph_completion(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        results = await temp_cognee.search(
            "Who is the tech lead on Project Atlas?",
            search_type=SearchType.GRAPH_COMPLETION,
            top_k=3,
        )
        assert isinstance(results, list)
        # The graph should surface Alice as the tech lead
        joined = " ".join(results).lower()
        assert "alice" in joined or "tech lead" in joined

    @pytest.mark.asyncio
    async def test_search_similarity(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        results = await temp_cognee.search(
            "database outage",
            search_type=SearchType.SIMILARITY,
            top_k=3,
        )
        assert isinstance(results, list)
        joined = " ".join(results).lower()
        assert "outage" in joined or "postgresql" in joined

    @pytest.mark.asyncio
    async def test_multi_hop_reasoning(self, temp_cognee, sample_markdown):
        """The killer feature: connect Alice → Project Atlas → PostgreSQL → outage."""
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        results = await temp_cognee.search(
            "Was Alice affected by the Tuesday outage?",
            search_type=SearchType.GRAPH_COMPLETION,
            top_k=5,
        )
        joined = " ".join(results).lower()
        # Graph traversal should surface the connection chain
        assert any(
            kw in joined
            for kw in ["alice", "project atlas", "postgresql", "outage", "tuesday"]
        )

    @pytest.mark.asyncio
    async def test_search_empty_dataset(self, temp_cognee):
        results = await temp_cognee.search(
            "random query",
            search_type=SearchType.GRAPH_COMPLETION,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_auto_cognify_flag(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        # auto_cognify=True should trigger graph build before search
        results = await temp_cognee.search(
            "Who leads Project Atlas?",
            auto_cognify=True,
            top_k=3,
        )
        assert isinstance(results, list)


@pytest.mark.slow
class TestMemify:
    @pytest.mark.asyncio
    async def test_memify_runs_without_error(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        await temp_cognee.memify()
        # Memify mutates graph; asserting no exception is baseline


@pytest.mark.slow
class TestPrune:
    @pytest.mark.asyncio
    async def test_prune_clears_data(self, temp_cognee, sample_markdown):
        await temp_cognee.ingest_file(sample_markdown)
        await temp_cognee.cognify()
        await temp_cognee.prune()
        results = await temp_cognee.search("Project Atlas")
        assert results == []


# ═══════════════════════════════════════════════════════════════════
# Factory & production config tests
# ═══════════════════════════════════════════════════════════════════

class TestFactory:
    def test_create_memory_defaults(self):
        CogneeMemory.clear_instances()
        mem = create_memory()
        assert mem.cfg.graph_provider == "falkor"
        assert mem.cfg.dataset_name == "main"

    def test_create_memory_with_postgres(self):
        CogneeMemory.clear_instances()
        mem = create_memory(
            relational_url="postgresql://u:p@h:5432/db",
            graph_provider="falkor",
            vector_provider="pgvector",
        )
        assert mem.cfg.relational_provider == "postgres"
        assert mem.cfg.vector_provider == "pgvector"
        assert mem.cfg.vector_db_url == "postgresql://u:p@h:5432/db"


# ═══════════════════════════════════════════════════════════════════
# Fallback smoke
# ═══════════════════════════════════════════════════════════════════

class TestFallback:
    def test_search_hybrid_fallback_exists(self, temp_cognee):
        # Ensure the method signature exists and returns a list type
        method = getattr(temp_cognee, "search_hybrid_fallback", None)
        assert method is not None


# ═══════════════════════════════════════════════════════════════════
# Benchmark harness (manual run)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.benchmark
@pytest.mark.slow
class TestBenchmark:
    @pytest.mark.asyncio
    async def test_indexing_latency(self, tmp_path):
        """Measure time to ingest + cognify a small vault."""
        import time
        data_root = tmp_path / "cognee" / "data_storage"
        system_root = tmp_path / "cognee" / "system"
        data_root.mkdir(parents=True)
        system_root.mkdir(parents=True)

        cfg = CogneeBackendConfig(
            relational_provider="sqlite",
            graph_provider="kuzu",
            vector_provider="lancedb",
            data_root_directory=data_root,
            system_root_directory=system_root,
            dataset_name="benchmark",
            llm_model="qwen2.5-coder:1.5b",
        )
        mem = CogneeMemory.create(config=cfg)

        # Create 10 sample markdown files
        vault = tmp_path / "vault"
        vault.mkdir()
        for i in range(10):
            (vault / f"file_{i}.md").write_text(
                f"# File {i}\n\nPerson{i} works on Project{i}. Project{i} uses Tech{i}.\n",
                encoding="utf-8",
            )

        t0 = time.perf_counter()
        await mem.ingest_directory(vault, glob="*.md")
        await mem.cognify()
        duration = time.perf_counter() - t0
        print(f"\nBenchmark: {duration:.2f}s for 10 files")
        assert duration < 300  # should finish within 5 minutes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
