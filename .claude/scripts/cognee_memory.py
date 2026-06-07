#!/usr/bin/env python3
"""
Cognee Memory Wrapper for Second Brain.

Graph-vector hybrid persistent memory layer. Sits adjacent to the existing
sqlite-vec + FTS5 stack (db.py / memory_index.py / memory_search.py).

Production stack (configurable):
  - Relational: Supabase PostgreSQL  (or SQLite for dev)
  - Vector:     pgvector             (or LanceDB for dev)
  - Graph:      FalkorDB             (or Kuzu embedded for dev)
  - LLM:        Ollama (nemotron-3-super:cloud)
  - Embeddings: FastEmbed (all-MiniLM-L6-v2, 384-dim)

Usage:
    import asyncio
    from cognee_memory import CogneeMemory

    mem = CogneeMemory()
    asyncio.run(mem.ingest_file(Path("Memory/projects/foo.md")))
    asyncio.run(mem.cognify())
    results = asyncio.run(mem.search("Who leads Project Atlas?"))
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List, Optional

# Optional python-dotenv for loading .env files safely
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False
    load_dotenv = None  # type: ignore

# ═══════════════════════════════════════════════════════════════════
# Environment guard — MUST be set before importing cognee
# ═══════════════════════════════════════════════════════════════════
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
os.environ.setdefault("CACHING", "false")

import cognee

# Register FalkorDB adapter (must happen before engine creation)
try:
    import cognee_community_hybrid_adapter_falkor.register  # noqa: F401
except Exception:
    pass

from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
from cognee.modules.search.types import SearchType

# ═══════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_DATA_ROOT = PROJECT_ROOT / ".claude" / "data" / "cognee"
DEFAULT_SQLITE_DB = PROJECT_ROOT / ".claude" / "data" / "memory.db"
PENDING_COGNIFY_FILE = PROJECT_ROOT / ".claude" / "data" / "state" / "pending-cognify.json"

IST = timezone(timedelta(hours=5, minutes=30))

# ═══════════════════════════════════════════════════════════════════
# Async runner safe for sync contexts
# ═══════════════════════════════════════════════════════════════════


def run_sync(coro) -> Any:
    """Run an async coroutine safely from a synchronous context.

    Uses asyncio.run() when possible. Falls back to a fresh event loop
    if one is already running (e.g. Jupyter, async web servers).
    """
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already inside a running event loop — create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ═══════════════════════════════════════════════════════════════════
# Config dataclass
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CogneeBackendConfig:
    """Backend selection for Cognee."""

    # Relational
    relational_provider: str = "sqlite"          # "sqlite" | "postgres"
    relational_db_name: str = "cognee_db"
    relational_url: Optional[str] = None       # e.g. postgresql://...

    # Vector
    vector_provider: str = "lancedb"           # "lancedb" | "pgvector"
    vector_db_url: Optional[str] = None
    vector_db_port: int = 5432

    # Graph
    graph_provider: str = "falkor"             # "kuzu" | "falkor" | "neo4j"
    graph_db_url: str = "localhost"
    graph_db_port: int = 6379                    # FalkorDB default; Kuzu ignores this

    llm_model: str = "nemotron-3-super:cloud"
    llm_endpoint: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_provider: str = "ollama"

    # Embeddings (FastEmbed)
    embedding_provider: str = "fastembed"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # Data paths
    data_root_directory: Path = field(default_factory=lambda: DEFAULT_DATA_ROOT / "data_storage")
    system_root_directory: Path = field(default_factory=lambda: DEFAULT_DATA_ROOT / "system")

    # Behaviour
    dataset_name: str = "main"
    top_k: int = 5
    session_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# CogneeMemory class
# ═══════════════════════════════════════════════════════════════════

class CogneeMemory:
    """Async wrapper around Cognee with Second Brain-specific defaults."""

    _instances: dict[str, CogneeMemory] = {}
    _lock = None  # initialized lazily

    @classmethod
    def create(cls, config: Optional[CogneeBackendConfig] = None, instance_id: str = "default") -> CogneeMemory:
        """Factory that returns a fresh instance (not cached)."""
        return cls(config=config, instance_id=instance_id)

    @classmethod
    def get_or_create(cls, config: Optional[CogneeBackendConfig] = None) -> CogneeMemory:
        """Return a cached instance for the given config hash (singleton per config)."""
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()
        cfg = config or CogneeBackendConfig()
        key = cfg.dataset_name
        with cls._lock:
            if key not in cls._instances:
                instance = cls.__new__(cls)
                instance.__init__(config=config)
                cls._instances[key] = instance
            return cls._instances[key]

    @classmethod
    def clear_instances(cls):
        """Backward-compat helper; no longer required for isolation."""
        cls._instances.clear()

    def __init__(self, config: Optional[CogneeBackendConfig] = None, instance_id: str = "default"):
        self.cfg = config or CogneeBackendConfig()
        self._pending_cognify = self._read_pending_flag()
        self._apply_config()

    @staticmethod
    def _pending_path() -> Path:
        PENDING_COGNIFY_FILE.parent.mkdir(parents=True, exist_ok=True)
        return PENDING_COGNIFY_FILE

    def _read_pending_flag(self) -> bool:
        """Check if any process has ingested data without cognifying."""
        path = self._pending_path()
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Only consider pending if it matches our dataset
            return data.get("dataset") == self.cfg.dataset_name and data.get("pending", False)
        except Exception:
            return False

    def _set_pending_flag(self, pending: bool = True) -> None:
        """Persist the pending flag so other processes see it."""
        path = self._pending_path()
        try:
            path.write_text(
                json.dumps({"dataset": self.cfg.dataset_name, "pending": pending, "ts": datetime.now(IST).isoformat()}),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[cognee_memory] Failed to write pending flag: {exc}", file=sys.stderr)

    def _apply_config(self) -> None:
        """Push config into Cognee's global config object."""
        cfg = self.cfg

        # Relational
        if cfg.relational_url and cfg.relational_provider == "postgres":
            import urllib.parse
            parsed = urllib.parse.urlparse(cfg.relational_url)
            connect_args = {}
            for k, v in urllib.parse.parse_qsl(parsed.query):
                connect_args[k] = v
            db_config = {
                "db_provider": "postgres",
                "db_host": parsed.hostname,
                "db_port": str(parsed.port) if parsed.port else "5432",
                "db_username": urllib.parse.unquote(parsed.username) if parsed.username else parsed.username,
                "db_password": urllib.parse.unquote(parsed.password) if parsed.password else parsed.password,
                "db_name": parsed.path.lstrip("/") if parsed.path else cfg.relational_db_name,
            }
            if connect_args:
                db_config["database_connect_args"] = connect_args
            cognee.config.set_relational_db_config(db_config)
        else:
            cognee.config.set_relational_db_config({
                "db_provider": cfg.relational_provider,
                "db_name": cfg.relational_db_name,
            })

        # Vector
        cognee.config.set_vector_db_provider(cfg.vector_provider)
        if cfg.vector_db_url:
            cognee.config.set_vector_db_config({
                "vector_db_url": cfg.vector_db_url,
                "vector_db_port": cfg.vector_db_port,
            })

        # Graph
        cognee.config.set_graph_database_provider(cfg.graph_provider)
        cognee.config.set_graph_db_config({
            "graph_database_url": cfg.graph_db_url,
            "graph_database_port": cfg.graph_db_port,
        })

        # LLM
        cognee.config.set_llm_provider(cfg.llm_provider)
        cognee.config.set_llm_model(cfg.llm_model)
        cognee.config.set_llm_endpoint(cfg.llm_endpoint)
        cognee.config.set_llm_api_key(cfg.llm_api_key)

        # Embeddings
        emb = get_embedding_config()
        emb.embedding_provider = cfg.embedding_provider
        emb.embedding_model = cfg.embedding_model
        emb.embedding_dimensions = cfg.embedding_dimensions

        # Paths
        cognee.config.data_root_directory(str(cfg.data_root_directory))
        cognee.config.system_root_directory(str(cfg.system_root_directory))

        # Enable WAL mode for SQLite concurrency
        if cfg.relational_provider == "sqlite":
            db_path = Path(cfg.system_root_directory) / "databases" / f"{cfg.relational_db_name}.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.close()

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    async def ingest_file(self, file_path: Path, dataset: Optional[str] = None) -> None:
        """Ingest a single markdown file into Cognee."""
        if not file_path.exists():
            raise FileNotFoundError(file_path)
        text = file_path.read_text(encoding="utf-8")
        await self.ingest_text(text, source=str(file_path), dataset=dataset)

    async def ingest_text(
        self,
        text: str,
        source: str = "inline",
        dataset: Optional[str] = None,
    ) -> None:
        """Ingest raw text with provenance tracking."""
        ds = dataset or self.cfg.dataset_name
        payload = f"<!-- source: {source} -->\n{text}"
        await cognee.add(payload, ds)
        self._pending_cognify = True
        self._set_pending_flag(True)

    async def cognify(self, datasets: Optional[List[str]] = None) -> None:
        """Build graph + embeddings. Incremental by default (only new data)."""
        ds = datasets or [self.cfg.dataset_name]
        await cognee.cognify(ds)

    async def memify(self, dataset: Optional[str] = None) -> None:
        """Self-improve the graph (prune stale, strengthen useful paths)."""
        ds = dataset or self.cfg.dataset_name
        await cognee.memify(dataset=ds)

    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.GRAPH_COMPLETION,
        dataset: Optional[str] = None,
        top_k: Optional[int] = None,
        auto_cognify: bool = False,
    ) -> List[str]:
        """Retrieve from graph-vector hybrid memory.

        Lazy-cognify: if any process has ingested data since last cognify,
        rebuild graph first. Set auto_cognify=True to force rebuild.
        """
        ds = dataset or self.cfg.dataset_name
        k = top_k or self.cfg.top_k

        # Check persisted flag in case another process ingested data
        pending = self._pending_cognify or self._read_pending_flag()
        if pending or auto_cognify:
            await cognee.cognify([ds])
            self._pending_cognify = False
            self._set_pending_flag(False)

        results = await cognee.search(
            query_text=query,
            query_type=search_type,
            datasets=[ds],
            top_k=k,
            session_id=self.cfg.session_id,
        )
        return [str(r) for r in results] if results else []

    async def prune(self) -> None:
        """Wipe all Cognee data + system state. Destructive."""
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)

    # ──────────────────────────────────────────────────────────────
    # Batch helpers
    # ──────────────────────────────────────────────────────────────

    async def ingest_directory(
        self,
        root: Path,
        glob: str = "**/*.md",
        dataset: Optional[str] = None,
    ) -> dict[str, int]:
        """Walk a directory and ingest all matching files. Returns {path: status}."""
        ds = dataset or self.cfg.dataset_name
        files = sorted(root.glob(glob))
        statuses: dict[str, int] = {}
        for fp in files:
            try:
                await self.ingest_file(fp, ds)
                statuses[str(fp)] = 1
            except Exception as exc:
                statuses[str(fp)] = 0
                print(f"[cognee ingest error] {fp}: {exc}", file=sys.stderr)
        return statuses

    # ──────────────────────────────────────────────────────────────
    # Fallback to legacy sqlite-vec
    # ──────────────────────────────────────────────────────────────

    def search_hybrid_fallback(
        self,
        query: str,
        top_k: int = 10,
        path_prefix: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        """Fallback to existing sqlite-vec + FTS5 hybrid search."""
        from db import SQLiteBackend
        from embeddings import Embedder

        embedder = Embedder()
        qemb = embedder.embed_query(query)
        with SQLiteBackend(str(DEFAULT_SQLITE_DB)) as db:
            return db.search_hybrid(qemb, query, top_k, path_prefix)


# ═══════════════════════════════════════════════════════════════════
# Convenience factory
# ═══════════════════════════════════════════════════════════════════


def _resolve_postgres_url() -> Optional[str]:
    """Find a valid PostgreSQL connection string from env.

    Priority:
    1. SUPABASE_DB_URL (direct PostgreSQL connection string)
    2. SUPABASE_URL if it contains postgresql://
    3. None -> fall back to SQLite
    """
    if _HAS_DOTENV:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)

    # Primary: dedicated PostgreSQL connection string
    db_url = os.environ.get("SUPABASE_DB_URL")
    if db_url and "postgresql://" in db_url:
        return db_url

    # Secondary: SUPABASE_URL only if it looks like a PostgreSQL string
    url = os.environ.get("SUPABASE_URL")
    if url and "postgresql://" in url:
        return url

    return None


def create_memory(
    relational_url: Optional[str] = None,
    graph_provider: str = "falkor",
    vector_provider: str = "lancedb",
    llm_model: str = "nemotron-3-super:cloud",
    dataset: str = "main",
    use_supabase: bool = True,
) -> CogneeMemory:
    """Factory for common configurations.

    Production stack (Supabase PostgreSQL + pgvector + FalkorDB) is the default.
    Falls back to local SQLite + LanceDB + Kuzu if PostgreSQL URL is missing.
    """
    if relational_url is None and (use_supabase or os.environ.get("USE_PRODUCTION_DB") == "1"):
        relational_url = _resolve_postgres_url()

    cfg = CogneeBackendConfig(
        relational_url=relational_url,
        relational_provider="postgres" if relational_url else "sqlite",
        graph_provider=graph_provider,
        vector_provider=vector_provider,
        llm_model=llm_model,
        dataset_name=dataset,
    )
    if relational_url and "postgresql://" in relational_url:
        cfg.vector_db_url = relational_url
        cfg.vector_provider = "pgvector"

    if cfg.relational_provider == "postgres":
        print("[PRODUCTION] Supabase PostgreSQL configured")

    return CogneeMemory.get_or_create(config=cfg)


# ═══════════════════════════════════════════════════════════════════
# CLI smoke test
# ═══════════════════════════════════════════════════════════════════

async def _smoke():
    print("CogneeMemory smoke test")
    mem = create_memory()
    await mem.ingest_text(
        "Alice is the tech lead on Project Atlas. Project Atlas uses PostgreSQL.",
        source="smoke_test",
    )
    await mem.cognify()
    results = await mem.search("Who leads Project Atlas?")
    print("Results:", results)
    return results


if __name__ == "__main__":
    asyncio.run(_smoke())
