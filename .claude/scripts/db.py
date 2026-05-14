import sqlite3
import sqlite_vec
from pathlib import Path
from typing import List, Optional
import numpy as np


class SQLiteBackend:
    """SQLite + sqlite-vec + FTS5 backend for hybrid memory search."""

    _default_db = None

    def __init__(self, db_path: str = None):
        if db_path is None:
            if SQLiteBackend._default_db is None:
                # Anchor to project root (three levels up from .claude/scripts/db.py)
                SQLiteBackend._default_db = str(
                    Path(__file__).resolve().parent.parent.parent
                    / ".claude"
                    / "data"
                    / "memory.db"
                )
            db_path = SQLiteBackend._default_db
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self._init_tables()

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                file_hash TEXT,
                updated_at TEXT
            )
        """)
        # External content FTS5: index stored here, text read from chunks table
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(chunk_text, content='chunks', content_rowid='id')
        """)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
            USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[384])
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT,
                updated_at TEXT
            )
        """)
        self.conn.commit()

    def insert_chunk(
        self,
        file_path: str,
        chunk_text: str,
        embedding: np.ndarray,
        file_hash: str,
        updated_at: str,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO chunks (file_path, chunk_text, file_hash, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (file_path, chunk_text, file_hash, updated_at),
        )
        chunk_id = cursor.lastrowid
        # Store embedding as float32 binary blob (little-endian)
        emb_blob = embedding.astype(np.float32).tobytes()
        self.conn.execute(
            "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, emb_blob),
        )
        # Tell FTS5 to index this rowid (external content table)
        self.conn.execute(
            "INSERT INTO chunks_fts (rowid) VALUES (?)",
            (chunk_id,),
        )
        return chunk_id

    def delete_by_file(self, file_path: str):
        rows = self.conn.execute(
            "SELECT id FROM chunks WHERE file_path = ?", (file_path,)
        ).fetchall()
        for row in rows:
            chunk_id = row["id"]
            self.conn.execute(
                "DELETE FROM chunks_vec WHERE chunk_id = ?", (chunk_id,)
            )
            try:
                self.conn.execute(
                    "DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,)
                )
            except sqlite3.DatabaseError:
                # FTS5 virtual table can become malformed on Windows.
                # Skip FTS5 deletion to avoid crashing; stale index entries
                # are harmless until the next full rebuild.
                pass
            self.conn.execute(
                "DELETE FROM chunks WHERE id = ?", (chunk_id,)
            )
        self.conn.execute(
            "DELETE FROM file_hashes WHERE file_path = ?", (file_path,)
        )
        self.conn.commit()

    def get_file_hash(self, file_path: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT file_hash FROM file_hashes WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        return row["file_hash"] if row else None

    def set_file_hash(self, file_path: str, file_hash: str, updated_at: str):
        self.conn.execute(
            """
            INSERT INTO file_hashes (file_path, file_hash, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                updated_at = excluded.updated_at
            """,
            (file_path, file_hash, updated_at),
        )
        self.conn.commit()

    def search_hybrid(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        top_k: int = 10,
        path_prefix: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        """Hybrid search using RRF: 0.7 vector + 0.3 keyword."""
        emb_blob = query_embedding.astype(np.float32).tobytes()
        params: List = [emb_blob, top_k, query_text, top_k]

        path_filter = ""
        if path_prefix:
            path_filter = "WHERE c.file_path LIKE ?"
            params.append(f"{path_prefix}%")

        sql = f"""
        WITH vec_matches AS (
            SELECT chunk_id, distance,
                   row_number() OVER (ORDER BY distance) AS rank_num
            FROM chunks_vec
            WHERE embedding MATCH ? AND k = ?
        ),
        fts_matches AS (
            SELECT rowid AS chunk_id, rank,
                   row_number() OVER (ORDER BY rank DESC) AS rank_num
            FROM chunks_fts
            WHERE chunk_text MATCH ?
            LIMIT ?
        ),
        all_ids AS (
            SELECT chunk_id FROM vec_matches
            UNION
            SELECT chunk_id FROM fts_matches
        )
        SELECT
            c.id,
            c.file_path,
            c.chunk_text,
            (COALESCE(1.0 / (60 + fts.rank_num), 0.0) * 0.3 +
             COALESCE(1.0 / (60 + vec.rank_num), 0.0) * 0.7) AS combined_score
        FROM all_ids
        LEFT JOIN fts_matches fts ON fts.chunk_id = all_ids.chunk_id
        LEFT JOIN vec_matches vec ON vec.chunk_id = all_ids.chunk_id
        JOIN chunks c ON c.id = all_ids.chunk_id
        {path_filter}
        ORDER BY combined_score DESC
        LIMIT ?
        """
        params.append(top_k)

        cursor = self.conn.execute(sql, params)
        return cursor.fetchall()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
