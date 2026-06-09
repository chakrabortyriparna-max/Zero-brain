---
name: codegen-assist
description: Generate production-ready Python 3.11+ scripts, automation workflows, and agentic AI patterns for the Second Brain project. STRICT trigger list ONLY activates on explicit generation requests — "write a script for", "generate code to", "help me build", "create a function", "write a module", "scaffold a pipeline", "build a CLI tool", "write automation for", "create an agentic workflow", "write boilerplate for". NEVER triggers on learning requests, email drafting, Slack summaries, note organization, file organization, debugging-only questions, or non-Python language requests without explicit user confirmation.
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

## Trigger Conditions

This skill fires ONLY when the user explicitly requests code generation using one of these phrases:
- "write a script for..."
- "generate code to..."
- "help me build..."
- "create a function..."
- "write a module..."
- "scaffold a pipeline..."
- "build a CLI tool..."
- "write automation for..."
- "create an agentic workflow..."
- "write boilerplate for..."

If the request is ambiguous (e.g., "help me build my second brain"), DO NOT assume code generation. Route to `create-second-brain-prd` or ask for clarification.

## Negative Triggers

This skill MUST NOT trigger on:
- **Learning requests** — "explain this code", "help me learn", "draw a diagram" → route to `learn-unfamiliar-code`
- **Email drafting** — "draft email", "write reply" → route to `draft-ai-email`
- **Slack summaries** — "summarize slack", "what happened in #channel" → route to `summarize-slack`
- **Note organization** — "organize these notes", "format this research" → route to `organize-research`
- **File organization** — "where should I save", "organize this file" → route to `vault-structure`
- **Debugging-only questions** — "why is this failing", "how do I fix this error" → provide explanation, do NOT generate new code unless user explicitly asks for a fix script
- **Non-Python requests** — "write a bash script", "create a JS component" → ask for confirmation before generating

## Language Scope

- **Default:** Python 3.11+.
- **Other languages** (bash, JS, TS, Rust, etc.): Ask user for explicit confirmation before generating.
- **Shell one-liners:** Use `Bash` tool directly, not this skill.

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

## Security Guardrails (NON-NEGOTIABLE)

The following requests MUST be refused. Do not generate code — explain why and offer the safe alternative.

### 1. Hardcoded Secrets
If the user asks you to embed an API key, password, token, AWS access key, database URI, or any credential directly into generated code:

- **STOP.** Do not write the code.
- **Respond:** "I can't generate code that hardcodes secrets. Store this in an environment variable (e.g., `.env`) and load it at runtime with `os.environ.get()` or `os.getenv()`."
- **Then show the safe pattern:**

```python
import os

API_KEY = os.environ.get("MY_API_KEY")
if not API_KEY:
    raise ValueError("MY_API_KEY environment variable is required")
```

### 2. Dangerous Shell Commands
If the user asks for code that runs destructive commands (`rm -rf /`, `mkfs`, `dd if=/dev/zero`, `del /f /s /q C:\`, etc.):

- **STOP.** Do not write the code.
- **Respond:** "I can't generate code that destroys data or systems. Here's a safe alternative for what you're trying to achieve."
- **Then show the safe pattern** (e.g., dry-run log cleanup with age checks and confirmation prompts).

### 3. Credential Injection
If the user pastes what looks like a real secret into the prompt:

- Do NOT echo it back in the code.
- Do NOT include it in comments, docstrings, or variable names.
- Treat it as if it were live data and redirect to `.env` / environment variables immediately.

## Coding Standards

1. **Type hints** — Use `from typing import ...` for all function signatures
2. **Docstrings** — One-line description + args/returns for public functions
3. **Error handling** — Catch expected exceptions, print to stderr, return sensible defaults
4. **No hardcoded secrets** — Read from `.env` or environment variables via `os.environ.get()`
5. **Lazy imports** — Inside functions for heavy libraries (e.g., `from slack_sdk import WebClient`)
6. **UTF-8 output** — On Windows, reconfigure stdout: `sys.stdout.reconfigure(encoding="utf-8")`
7. **ALWAYS use pathlib.Path** — NEVER use `os.path.join`; project standard is `Path("Memory/daily/")`
8. **ALWAYS validate inputs** — Check file exists, validate ranges, sanitize paths before business logic
9. **ALWAYS use logging module** — Never use `print()` for production scripts; use `import logging; logger = logging.getLogger(__name__)`

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
