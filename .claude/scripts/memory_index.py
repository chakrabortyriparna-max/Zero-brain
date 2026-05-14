import argparse
import hashlib
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from db import SQLiteBackend
from embeddings import Embedder


IST = timezone(timedelta(hours=5, minutes=30))
# Anchor paths relative to this script so it works from any cwd
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent.parent
MEMORY_ROOT = PROJECT_ROOT / "Memory"
DB_PATH = PROJECT_ROOT / ".claude" / "data" / "memory.db"
# ~400 tokens ≈ 1500 chars (approximation), ~50 token overlap ≈ 200 chars
MAX_CHUNK_CHARS = 1500
OVERLAP_CHARS = 200


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            # Search backward for a clean break point
            bp = text.rfind("\n\n", end - overlap, end)
            if bp == -1:
                bp = text.rfind("\n", end - overlap // 2, end)
            if bp == -1:
                bp = text.rfind(" ", end - overlap // 4, end)
            if bp != -1 and bp > start:
                end = bp
        segment = text[start:end].strip()
        if segment:
            chunks.append(segment)
        start = end - overlap if end < length else end
        if start >= end:
            start = end
    return chunks


def index_file(db: SQLiteBackend, embedder: Embedder, file_path: Path, rel_path: str) -> int:
    """Index a single markdown file. Returns number of chunks inserted."""
    current_hash = sha256_file(file_path)
    stored_hash = db.get_file_hash(rel_path)

    if stored_hash == current_hash:
        return 0  # No change

    # Delete old chunks for this file if any
    db.delete_by_file(rel_path)

    text = file_path.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    if not chunks:
        db.set_file_hash(rel_path, current_hash, datetime.now(IST).isoformat())
        return 0

    embeddings = embedder.embed_texts(chunks)
    now = datetime.now(IST).isoformat()
    for chunk, emb in zip(chunks, embeddings):
        db.insert_chunk(rel_path, chunk, emb, current_hash, now)
    db.set_file_hash(rel_path, current_hash, now)
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Incrementally index Memory/ markdown files.")
    parser.add_argument("--memory-root", type=Path, default=MEMORY_ROOT, help="Path to Memory directory")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed without writing")
    args = parser.parse_args()

    memory_root = args.memory_root.resolve()
    if not memory_root.exists():
        print(f"Memory root not found: {memory_root}")
        return

    project_root = PROJECT_ROOT
    embedder = Embedder()
    total_new = 0
    total_updated = 0
    total_unchanged = 0

    try:
        db_backend = SQLiteBackend(str(args.db))
    except sqlite3.DatabaseError as exc:
        print(f"[ERROR] Database corrupt: {exc}")
        backup_path = args.db.with_suffix(f".db.corrupt.{datetime.now(IST).strftime('%Y-%m-%d')}")
        args.db.rename(backup_path)
        print(f"[INFO] Renamed corrupt DB to {backup_path}")
        db_backend = SQLiteBackend(str(args.db))

    with db_backend as db:
        for md_file in sorted(memory_root.rglob("*.md")):
            rel_path = md_file.relative_to(project_root).as_posix()
            current_hash = sha256_file(md_file)
            stored_hash = db.get_file_hash(rel_path)

            if stored_hash == current_hash:
                total_unchanged += 1
                continue

            if args.dry_run:
                action = "new" if stored_hash is None else "updated"
                print(f"[{action}] {rel_path}")
                total_new += 1
                continue

            count = index_file(db, embedder, md_file, rel_path)
            if stored_hash is None:
                total_new += 1
                print(f"[indexed {count} chunks] {rel_path}")
            else:
                total_updated += 1
                print(f"[re-indexed {count} chunks] {rel_path}")

    print(
        f"\nDone: {total_new} new, {total_updated} updated, {total_unchanged} unchanged files."
    )


if __name__ == "__main__":
    main()
