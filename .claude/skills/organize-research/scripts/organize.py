"""Helper to index and cross-link a research note.

Usage:
    python organize.py Memory/research/papers/qlora.md

This script:
1. Reads the note
2. Extracts tags from frontmatter
3. Runs memory_search for related notes
4. Appends a "Related Notes" section with [[wikilinks]]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def extract_tags(frontmatter: str) -> list:
    """Extract tags list from YAML frontmatter."""
    match = re.search(r"tags:\s*\[(.*?)\]", frontmatter, re.S)
    if match:
        raw = match.group(1)
        return [t.strip().strip('"').strip("'") for t in raw.split(",")]
    return []


def find_related(query: str, top_k: int = 5) -> list:
    """Search for related notes in Memory/research."""
    cmd = [
        "python",
        ".claude/scripts/memory_search.py",
        query,
        "--path-prefix",
        "Memory/research",
        "--top-k",
        str(top_k),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = result.stdout.strip().split("\n")
        related = []
        for line in lines[2:]:  # skip header and separator
            parts = line.split(None, 2)
            if len(parts) >= 3:
                file_path = parts[1]
                related.append(file_path)
        return related
    except Exception:
        return []


def add_related_section(content: str, related: list) -> str:
    """Append or update a Related Notes section with wikilinks."""
    if not related:
        return content

    section = "\n\n## Related Notes\n\n"
    for path in related:
        # Convert file path to wikilink name
        name = Path(path).stem.replace("-", " ").title()
        section += f"- [[{name}]]\n"

    # If section already exists, replace it
    if "## Related Notes" in content:
        content = re.sub(
            r"## Related Notes\n.*?\n(?=## |\Z)",
            section.strip() + "\n\n",
            content,
            flags=re.S,
        )
    else:
        content = content.rstrip() + section

    return content


def main():
    parser = argparse.ArgumentParser(description="Organize and cross-link a research note.")
    parser.add_argument("file", type=Path, help="Path to the markdown note")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    content = args.file.read_text(encoding="utf-8")

    # Extract tags from frontmatter
    fm_match = re.match(r"---\n(.*?)\n---\n", content, re.S)
    tags = []
    if fm_match:
        tags = extract_tags(fm_match.group(1))

    query = " ".join(tags) if tags else Path(args.file).stem.replace("-", " ")
    related = find_related(query)

    # Filter out self-reference
    related = [r for r in related if Path(r).resolve() != args.file.resolve()]

    if not related:
        print("No related notes found.")
        sys.exit(0)

    new_content = add_related_section(content, related)

    if args.dry_run:
        print("--- New Related Notes Section ---")
        for r in related:
            print(f"  [[{Path(r).stem.replace('-', ' ').title()}]]")
    else:
        args.file.write_text(new_content, encoding="utf-8")
        print(f"Updated {args.file} with {len(related)} related notes.")


if __name__ == "__main__":
    main()
