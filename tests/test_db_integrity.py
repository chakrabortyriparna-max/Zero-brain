"""DB integrity check — run standalone or in CI."""

import sqlite3
import sqlite_vec
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / ".claude" / "data" / "memory.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"[SKIP] Database not found at {DB_PATH}")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    cursor = conn.cursor()

    # 1. Integrity check
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    if result != "ok":
        print(f"[FAIL] integrity_check: {result}")
        return 1
    print("[PASS] integrity_check: ok")

    # 2. Rowcount alignment
    tables = [
        ("chunks", "SELECT COUNT(*) FROM chunks"),
        ("chunks_vec", "SELECT COUNT(*) FROM chunks_vec"),
    ]
    counts = {}
    for name, sql in tables:
        cursor.execute(sql)
        counts[name] = cursor.fetchone()[0]
        print(f"[INFO] {name}: {counts[name]} rows")

    if counts["chunks"] != counts["chunks_vec"]:
        print(
            f"[FAIL] Rowcount mismatch: chunks={counts['chunks']}, "
            f"chunks_vec={counts['chunks_vec']}"
        )
        return 1

    print("[PASS] Rowcount alignment: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
