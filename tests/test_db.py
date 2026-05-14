"""Unit tests for SQLite backend and hybrid search."""

import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pytest

from db import SQLiteBackend


@pytest.fixture
def backend():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with SQLiteBackend(str(db_path)) as db:
            yield db


def test_insert_and_search(backend):
    embedding = np.random.rand(384).astype(np.float32)
    chunk_id = backend.insert_chunk(
        file_path="test.md",
        chunk_text="hello world",
        embedding=embedding,
        file_hash="abc123",
        updated_at="2026-05-14T00:00:00+05:30",
    )
    assert chunk_id == 1

    results = backend.search_hybrid(embedding, "hello", top_k=5)
    assert len(results) == 1
    assert results[0]["file_path"] == "test.md"


def test_delete_by_file(backend):
    emb = np.random.rand(384).astype(np.float32)
    backend.insert_chunk("a.md", "text a", emb, "h1", "2026-05-14")
    backend.insert_chunk("b.md", "text b", emb, "h2", "2026-05-14")

    backend.delete_by_file("a.md")
    results = backend.search_hybrid(emb, "text", top_k=10)
    assert len(results) == 1
    assert results[0]["file_path"] == "b.md"


def test_file_hash_roundtrip(backend):
    backend.set_file_hash("x.md", "hash1", "2026-05-14")
    assert backend.get_file_hash("x.md") == "hash1"
