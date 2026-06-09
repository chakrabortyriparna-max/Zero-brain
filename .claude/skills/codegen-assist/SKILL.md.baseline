---
name: codegen-assist
description: Assist in generating code snippets, automation workflows, and agentic AI patterns. Triggers on "write a script for", "generate code to", "help me build", or when asked to create automation, CLI tools, or agentic workflows.
argument-hint: <task-description-or-requirements>
---

# Codegen Assist

## Workflow

1. **Understand the task** — Clarify inputs, outputs, constraints, error handling needs
2. **Search existing code** — Run `python .claude/scripts/memory_search.py "<task>" --path-prefix Memory --top-k 5` to find related scripts or patterns
3. **Design** — Choose the right pattern (see below)
4. **Generate** — Write clean, well-typed Python code
5. **Save** — Write to `Memory/projects/<current-project>/scripts/<filename>.py` or `Memory/research/experiments/`
6. **Index** — Remind user to run `python .claude/scripts/memory_index.py` so the new code is searchable

## Code Patterns

### Pattern 1: Claude Agent SDK Script

For scripts that use the Claude Agent SDK to reason over data:

```python
"""Description of what this script does."""
import argparse
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file or query")
    args = parser.parse_args()

    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant...",
        allowed_tools=["Read", "Write", "Bash"],
    )
    client = ClaudeSDKClient(options=options)

    # Your logic here
    result = client.query(prompt=f"Process: {args.input}")
    print(result)

if __name__ == "__main__":
    main()
```

### Pattern 2: Integration Wrapper

For scripts that wrap platform APIs and format output for the LLM:

```python
"""Fetch data from <platform> and return markdown summary."""
from integrations.registry import get_integration

def fetch_and_format():
    module = get_integration("<platform>")
    data = module.list_items()
    return module.format_items(data)
```

### Pattern 3: RAG Pipeline Script

For scripts that chunk, embed, and search memory:

```python
from embeddings import Embedder
from db import SQLiteBackend

def search_memory(query: str, top_k: int = 10):
    embedder = Embedder()
    query_emb = embedder.embed_query(query)
    with SQLiteBackend() as db:
        return db.search_hybrid(query_emb, query, top_k=top_k)
```

### Pattern 4: Hook Script

For Claude Code lifecycle hooks:

```python
"""SessionStart hook — injects context into every conversation."""
import json
import sys

def main():
    data = json.load(sys.stdin)
    # Read memory files, format context
    context = load_context()
    print(context)

def load_context():
    # Implementation
    pass

if __name__ == "__main__":
    main()
```

## Coding Standards

1. **Type hints** — Use `from typing import ...` for all function signatures
2. **Docstrings** — One-line description + args/returns for public functions
3. **Error handling** — Catch expected exceptions, print to stderr, return sensible defaults
4. **No hardcoded secrets** — Read from `.env` or environment variables via `os.environ.get()`
5. **Lazy imports** — Inside functions for heavy libraries (e.g., `from slack_sdk import WebClient`)
6. **UTF-8 output** — On Windows, reconfigure stdout: `sys.stdout.reconfigure(encoding="utf-8")`

## File Naming

- **CLI tools** → `snake_case.py`
- **Libraries/modules** → `snake_case.py` with clear public API
- **Experiments** → `YYYY-MM-DD_experiment_<name>.py`
- **Hooks** → `event-name-context.py` (e.g., `session-start-context.py`)

## Save Location Rules

| Type | Location |
|------|----------|
| Project script | `Memory/projects/<project>/scripts/<name>.py` |
| Experiment | `Memory/research/experiments/YYYY-MM-DD_<name>.py` |
| Reusable utility | `.claude/scripts/<name>.py` |
| Hook | `.claude/hooks/<event>-<purpose>.py` |

## After Generating Code

1. Run `python -m py_compile <file.py>` to check syntax
2. If it's a script, show the user how to run it
3. Remind: "Run `python .claude/scripts/memory_index.py` to make this searchable"

## GPS Quality Check

Before finalizing any generated code or script, optionally apply the GPS Framework (from `.claude/skills/gps-prompt-engineer/SKILL.md`):

1. **Gaslight:** Raise stakes in the code generation prompt. ("This runs in production. If it fails, it corrupts the database. Write it with that consequence in mind.")
2. **Push Back:** Challenge generic patterns. ("That's a standard pattern. What would a senior engineer who's seen this fail in production do differently?")
3. **Stress Test:**
   - **Gap Check:** Did I specify error handling, concurrency, input validation?
   - **Bias Sweep:** Check for survivorship bias — am I only modeling the happy path?
   - **Stakes Injection:** "If this script crashes at 2am, what's the rollback plan?"
