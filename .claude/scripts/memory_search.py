import argparse
from pathlib import Path

from db import SQLiteBackend
from embeddings import Embedder


DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / ".claude" / "data" / "memory.db"


def main():
    parser = argparse.ArgumentParser(description="Hybrid search over memory chunks.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--path-prefix", default=None, help="Filter results by file path prefix")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    args = parser.parse_args()

    embedder = Embedder()
    query_embedding = embedder.embed_query(args.query)

    with SQLiteBackend(str(args.db)) as db:
        results = db.search_hybrid(
            query_embedding=query_embedding,
            query_text=args.query,
            top_k=args.top_k,
            path_prefix=args.path_prefix,
        )

    if not results:
        print("No results found.")
        return

    print(f"{'Score':>8}  {'File':<40}  Preview")
    print("-" * 90)
    for row in results:
        score = row["combined_score"]
        file_path = row["file_path"]
        preview = row["chunk_text"].replace("\n", " ")[:120]
        print(f"{score:>8.4f}  {file_path:<40}  {preview}...")


if __name__ == "__main__":
    main()
