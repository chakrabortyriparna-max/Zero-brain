# PRD — Cognee Graph-Vector Hybrid Memory for Second Brain

> Generated: 2026-05-22
> Status: Draft — awaiting validation
> Scope: Second Brain only (Archon integration out of scope)

---

## 1. Problem Statement

The Second Brain agent forgets.

Current memory is a flat hybrid RAG stack: markdown vaults → chunked → embedded into `sqlite-vec` + `FTS5` with Reciprocal Rank Fusion (0.7 vector + 0.3 keyword). This works for similarity search (`find conversations like this one`). It fails the moment a query crosses entity boundaries.

**Example failure:**
- Fact A: "Alice is the tech lead on Project Atlas" (in `Memory/team/`)
- Fact B: "Project Atlas uses PostgreSQL for its primary datastore" (in `Memory/projects/`)
- Fact C: "The PostgreSQL cluster experienced an outage on Tuesday" (in `Memory/daily/`)
- Query: "Was Alice's project affected by Tuesday's outage?"

Vector search ranks Fact A and Fact C high (they mention Alice and Tuesday). Fact B — the bridge connecting them — mentions neither. It never surfaces. The agent has all the information on disk but cannot traverse the relationship.

This is the normal shape of real-world questions. Business knowledge is inherently relational: people belong to teams, teams own projects, projects depend on systems, systems have incidents. Any query spanning two or more hops exceeds what flat vector retrieval can answer.

Additionally:
- **No memory consolidation:** `memory_reflect.py` promotes daily log items to `MEMORY.md` via regex + optional LLM, but there is no mechanism to distill repeated episodic events into semantic rules.
- **Storage without catalog:** The vault holds 2,000+ facts across daily logs, project notes, and research. Loading all of them into context exceeds the 128K window. Keyword search is too brittle for synonyms and paraphrases.
- **Lost in the middle:** Even within the context window, accuracy drops over 30% when relevant information sits in the middle of a long prompt.

## 2. Evidence

### Current Architecture (verified by reading code)

| Component | File | What it does | Limitation |
|---|---|---|---|
| Hybrid RAG backend | `.claude/scripts/db.py:8-197` | SQLite + sqlite-vec (384-dim) + FTS5 with RRF | Flat vectors; no relational traversal |
| Incremental indexer | `.claude/scripts/memory_index.py:1-137` | SHA-256 hash → chunk (~1,500 chars, 200 overlap) → embed | Chunks are isolated; no entity linking |
| Search CLI | `.claude/scripts/memory_search.py:1-45` | Embeds query → `search_hybrid()` | Returns top-K chunks, not connected facts |
| Embeddings | `.claude/scripts/embeddings.py:1-29` | FastEmbed `all-MiniLM-L6-v2` (384-dim float32) | Local, no API cost; but model is general-purpose, not fine-tuned for entity extraction |
| SessionStart hook | `.claude/hooks/session-start-context.py:1-97` | Injects SOUL.md + USER.md + MEMORY.md + last 3 daily logs into stdout | Loads raw text, not retrieved context; grows unbounded |
| PreCompact hook | `.claude/hooks/pre-compact-flush.py` | Extracts decisions/facts/action items from JSONL transcript → appends to daily log | No deduplication against prior facts; no relationship extraction |
| Heartbeat | `.claude/scripts/heartbeat.py:1-60+` | Polls Gmail/Slack/GitHub, diffs state, drafts replies, logs to daily logs | Stores summaries as flat text; no graph linking between entities (people, projects, incidents) |
| Memory reflection | `.claude/scripts/memory_reflect.py:1-50+` | Promotes yesterday's items to MEMORY.md via regex/LLM | Manual consolidation; no automatic derivation of rules from patterns |

### Database Schema (verified)

```sql
-- .claude/scripts/db.py:33-57
CREATE TABLE chunks (id INTEGER PRIMARY KEY, file_path TEXT, chunk_text TEXT, file_hash TEXT, updated_at TEXT);
CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_text, content='chunks', content_rowid='id');
CREATE VIRTUAL TABLE chunks_vec USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[384]);
CREATE TABLE file_hashes (file_path TEXT PRIMARY KEY, file_hash TEXT, updated_at TEXT);
```

No entity table. No relationship table. No provenance tracking beyond `file_path` and `updated_at`.

### Dependencies (verified)

Current `requirements.txt` (`C:\Users\chakr\...\requirements.txt:1-31`):
- `fastembed==0.3.6`
- `sqlite-vec==0.1.3`
- `numpy==1.26.4`
- `anthropic==0.49.0`
- `groq==0.18.0`

No vector database beyond sqlite-vec. No graph database. No entity extraction pipeline.

## 3. Proposed Solution

Integrate **Cognee** as an adjacent memory layer — not a replacement for the existing hybrid RAG, but a graph-vector hybrid store that sits alongside it.

**Cognee** is an open-source knowledge engine (`pip install cognee`) that combines:
1. **Relational store** (SQLite default) → provenance: where data came from, when it was ingested
2. **Vector store** (LanceDB default) → semantics: what content means, what it's similar to
3. **Graph store** (Kuzu default) → relationships: how entities connect, who reports to whom

The API surface is four async calls:
- `cognee.add(text, dataset)` — ingest raw data
- `cognee.cognify([dataset])` — build knowledge graph + embeddings via LLM-driven entity/relationship extraction + deduplication
- `cognee.memify(dataset)` — self-improve the graph (strengthen useful paths, prune stale nodes, auto-tune edge weights)
- `cognee.search(query, query_type=SearchType.GRAPH_COMPLETION)` — retrieve with reasoning

**Integration pattern:**
- Keep the existing `memory.db` + `memory_index.py` + `memory_search.py` for fast similarity search and backward compatibility.
- Add a new `cognee_memory.py` wrapper module that ingests the same markdown vault into Cognee's graph-vector store.
- Modify hooks (`session-start-context.py`, `pre-compact-flush.py`) to push extracted insights into Cognee, not just flat daily logs.
- Modify `heartbeat.py` to use `SearchType.GRAPH_COMPLETION` for cross-entity queries (e.g., "which project was affected by the outage mentioned in Slack?").
- Modify `memory_reflect.py` to call `cognee.memify()` for automatic consolidation instead of regex-based promotion.

**Why adjacent, not replacement?**
- The existing sqlite-vec stack is zero-config, zero-cost, and works for simple similarity search.
- Cognee requires an LLM API key for `cognify()` (entity extraction) and is heavier (LanceDB + Kuzu + SQLite).
- Running both lets us A/B test retrieval quality before committing to a full migration.

## 4. Key Hypothesis

> **We believe** that adding a Cognee graph-vector layer alongside the existing flat RAG will **enable multi-hop reasoning across the Memory vault** for Riparna's Second Brain agent. **We'll know we're right when** the agent can correctly answer relational queries (e.g., "Was Alice's project affected by Tuesday's outage?") with >80% accuracy, compared to <20% today.

Secondary hypothesis:
> **We believe** that replacing `memory_reflect.py`'s regex/LLM promotion with `cognee.memify()` will **reduce manual consolidation overhead** and surface implicit rules (e.g., "Riparna prefers executive summaries for client emails") without explicit programming.

## 5. What We're NOT Building

| Out of Scope | Rationale |
|---|---|
| Archon workflow integration | User explicitly selected "Second Brain only" |
| Full migration of `memory.db` to Cognee | Adjacent-first; migrate only after validation |
| Multi-tenant/dataset permissions | Single-user system; `dataset="main"` is sufficient |
| Real-time Slack bot (Phase 7) | Out of scope for this PRD; memory layer should support it when built |
| Custom embedding model fine-tuning | Use Cognee's default (OpenAI embeddings) or keep FastEmbed |
| Web UI for graph visualization | Nice-to-have; can be added later via Kuzu Explorer or custom route |
| Automatic `memify()` scheduling | Requires cost estimation; start with manual trigger |

## 6. Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Multi-hop query accuracy | <20% (manual test) | >80% | Hand-crafted 20-question eval set spanning people → projects → systems → incidents |
| Memory consolidation recall | N/A (manual) | Weekly auto-promotion of 5+ derived facts | Count of facts added to `MEMORY.md` by `memify()` vs by `memory_reflect.py` |
| Draft relevance score | Subjective | Same or better | Riparna rates heartbeat-generated drafts before/after Cognee recall integration |
| Indexing latency | ~2s for 100 files | <10s for Cognee cognify() on same corpus | Time `python cognee_index.py --benchmark` |
| Storage overhead | ~50MB (`memory.db`) | <200MB (Cognee SQLite + LanceDB + Kuzu) | `du -sh .cognee/` |

## 7. Open Questions

| # | Question | Why it matters |
|---|---|---|
| 1 | Should we use OpenAI embeddings (Cognee default) or keep FastEmbed (`all-MiniLM-L6-v2`) for cost? | OpenAI embeddings are better but cost money per token. FastEmbed is free but may reduce graph extraction quality. |
| 2 | How do we partition datasets? One global `dataset="main"`, or per-source (`daily`, `projects`, `research`, `drafts`)? | Per-source enables scoped search but complicates cross-source queries. |
| 3 | How often should `cognify()` run? On every file change (expensive), nightly batch (stale), or on-demand? | Balances cost vs freshness. Nightly is likely the right default. |
| 4 | Should `memify()` run automatically or require explicit trigger? | `memify()` calls an LLM and mutates the graph. Auto-runs risk unbounded cost. |
| 5 | How do we handle Cognee's LLM dependency for `cognify()`? | Cognee uses `OPENAI_API_KEY` by default. We already have `llm_client.py` with Anthropic/Groq/Ollama support. Need to verify Cognee supports non-OpenAI LLMs. |
| 6 | What happens to the existing `memory.db` if we later migrate fully? | Need a migration path: dual-write → validate → deprecate sqlite-vec. |

## 8. Users & Context

**Primary User:** Riparna Chakraborty, Agentic AI Engineer.

**Role context:**
- Manages multiple client projects simultaneously
- Tracks AI/ML research papers, LLM techniques, and tools
- Maintains a personal knowledge vault in `Memory/` (daily logs, projects, research, team, goals)
- Uses the Second Brain agent for: drafting emails, summarizing Slack, organizing research, code generation assistance

**Job to Be Done:**
> "When I have a complex question that spans multiple notes (e.g., 'what did we decide about the database migration for Project Atlas?'), I want the agent to connect the dots across my vault, so I don't have to manually grep through 50 markdown files."

**Non-users:**
- External team members (single-user system)
- Non-technical users (requires local Python env, API keys)

**Constraints:**
- Local-first: prefers embedded databases over cloud services
- Cost-conscious: evaluates token/API spend before enabling features
- Privacy-first: sensitive client data must not leave local machine
- Windows 11 Home: no Docker, no Linux containers

## 9. Solution Detail

### Must Have (v1)

| # | Feature | Description |
|---|---|---|
| 1 | Cognee wrapper module | `.claude/scripts/cognee_memory.py` — async `ingest()`, `search()`, `cognify()`, `memify()` wrappers with config management |
| 2 | Vault indexer | `.claude/scripts/cognee_index.py` — walk `Memory/` markdown files, call `cognee.add()` per file, run `cognee.cognify()` |
| 3 | SessionStart hook integration | Modify `.claude/hooks/session-start-context.py` to prepend `$COGNEE_CONTEXT` (retrieved memories) instead of raw MEMORY.md text |
| 4 | PreCompact hook integration | Modify `.claude/hooks/pre-compact-flush.py` to push extracted decisions/facts into Cognee, not just daily logs |
| 5 | Search CLI extension | Extend `.claude/scripts/memory_search.py` with `--mode cognee` flag to run `GRAPH_COMPLETION` search |
| 6 | Requirements update | Add `cognee` to `requirements.txt` and `.claude/scripts/requirements.txt` |

### Should Have (v1.1)

| # | Feature | Description |
|---|---|---|
| 7 | Heartbeat recall | Modify `.claude/scripts/heartbeat.py` to use Cognee search for cross-entity drafting context (e.g., "who is this client? what project? what was last discussed?") |
| 8 | Memory reflect migration | Replace `memory_reflect.py` regex promotion with `cognee.memify()` + derived-fact extraction |
| 9 | Dual-write mode | `cognee_index.py` writes to both `memory.db` (sqlite-vec) and Cognee for backward compatibility |

### Nice to Have (v2)

| # | Feature | Description |
|---|---|---|
| 10 | Graph visualization | Export Kuzu graph to `.cognee/graph.html` for manual inspection |
| 11 | Evaluation harness | `tests/test_cognee_memory.py` — 20-question multi-hop eval set with expected answers |
| 12 | Auto-cognify scheduling | Windows Task Scheduler job to run `cognee_index.py --cognify` nightly |

## 10. Technical Approach

### 10.1 File Paths & Changes

| File | Change | What to do |
|---|---|---|
| **New** `.claude/scripts/cognee_memory.py` | Create | Async wrapper around Cognee API: `init()`, `ingest_file()`, `ingest_text()`, `search()`, `cognify()`, `memify()`. Handles config (SQLite+LanceDB+Kuzu), dataset naming, error retry. |
| **New** `.claude/scripts/cognee_index.py` | Create | CLI: walk `Memory/**/*.md`, hash files (reuse `memory_index.py` logic), batch-ingest new/changed files into Cognee, trigger `cognify()`. Supports `--dry-run`, `--cognify`, `--prune`. |
| **Modify** `.claude/hooks/session-start-context.py:32-61` | Extend | After building context, call `cognee_memory.search("recent priorities and open questions")` and prepend results under a `## Cognee Context` section. |
| **Modify** `.claude/hooks/pre-compact-flush.py` | Extend | After extracting decisions/facts, call `cognee_memory.ingest_text()` with source="session_flush" and run `cognee.cognify(["session_flush"])`. |
| **Modify** `.claude/scripts/memory_search.py:10-45` | Extend | Add `--mode {hybrid,cognee}` argument. If `cognee`, call `cognee_memory.search()` with `SearchType.GRAPH_COMPLETION` and render results with relationship paths. |
| **Modify** `requirements.txt:1-31` | Update | Add `cognee>=0.1.0` (verify latest version). Add `lancedb`, `kuzu` if not pulled in transitively. |
| **Modify** `.claude/scripts/requirements.txt` | Update | Same as above. |

### 10.2 Cognee Wrapper Design

```python
# .claude/scripts/cognee_memory.py (skeleton)
import asyncio
import cognee
from cognee.modules.search.types import SearchType
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "cognee"

async def init_cognee():
    cognee.config.set_vector_db_config({"vector_db_provider": "lancedb"})
    cognee.config.set_graph_db_config({"graph_database_provider": "kuzu"})
    cognee.config.set_relational_db_config({"db_provider": "sqlite", "db_name": "cognee_db"})
    cognee.config.data_root_directory(str(DATA_ROOT / "data_storage"))
    cognee.config.system_root_directory(str(DATA_ROOT / "system"))

async def ingest_file(file_path: Path, dataset: str = "main"):
    text = file_path.read_text(encoding="utf-8")
    await cognee.add(text, dataset)

async def search(query: str, dataset: str = "main", top_k: int = 5):
    await cognee.cognify([dataset])  # ensure graph is built
    results = await cognee.search(
        query_text=query,
        query_type=SearchType.GRAPH_COMPLETION,
        top_k=top_k,
    )
    return results
```

**Key decisions:**
- Use **embedded stack** (SQLite + LanceDB + Kuzu) — no Docker, no external services, aligns with local-first constraint.
- Use **single dataset** (`"main"`) for v1 — per-source datasets are "nice to have."
- **Lazy initialization** — call `init_cognee()` on first use, not at import time.
- **Incremental cognify** — Cognee's default is incremental; only new/changed data gets reprocessed.

### 10.3 SessionStart Hook Memory Injection

Current behavior (`session-start-context.py:32-61`): loads SOUL.md + USER.md + MEMORY.md + last 3 daily logs as raw text.

New behavior:
1. Load raw context (keep existing behavior for fallback)
2. Call `cognee_memory.search("What are the current active projects, open decisions, and recent habits?")`
3. Prepend search results under `## Cognee Context` before raw MEMORY.md

This keeps the raw text available but surfaces structured, relational context first.

### 10.4 PreCompact Hook Graph Ingestion

Current behavior (`pre-compact-flush.py`): extracts tagged items from JSONL → appends categorized block to daily log.

New behavior:
1. Extract tagged items (keep existing)
2. Append to daily log (keep existing)
3. Also call `cognee_memory.ingest_text(categorized_block, dataset="daily_logs")`
4. Trigger `cognee.cognify(["daily_logs"])` (incremental; only new block gets processed)

This ensures every session's decisions, action items, and lessons enter the graph within minutes of creation.

## 11. Implementation Phases

### Phase A: Setup & Wrapper (1-2 days)

| # | Task | Verification |
|---|---|---|
| A1 | `pip install cognee` in the project venv; verify imports | `python -c "import cognee; print(cognee.__version__)"` |
| A2 | Create `.claude/scripts/cognee_memory.py` with `init()`, `ingest_file()`, `search()` | Run unit test: ingest one markdown file, search, assert result contains filename |
| A3 | Create `.claude/scripts/cognee_index.py` CLI | Run: `python cognee_index.py --dry-run` → lists files that would be indexed |
| A4 | Update `requirements.txt` | `git diff requirements.txt` shows `cognee` added |

### Phase B: Hook Integration (1 day)

| # | Task | Verification |
|---|---|---|
| B1 | Modify `session-start-context.py` to prepend Cognee search results | Run hook standalone; verify output contains `## Cognee Context` |
| B2 | Modify `pre-compact-flush.py` to push extracted items to Cognee | Simulate a flush; verify `cognee.search()` finds the decision |
| B3 | Add `--mode cognee` to `memory_search.py` | Run: `python memory_search.py "Alice Project Atlas" --mode cognee` → returns connected facts |

### Phase C: Heartbeat & Reflection (2-3 days)

| # | Task | Verification |
|---|---|---|
| C1 | Modify `heartbeat.py` to query Cognee before drafting emails | Inspect draft output: does it reference correct project/client context? |
| C2 | Modify `memory_reflect.py` to call `cognee.memify()` | Run reflection; inspect `MEMORY.md` for newly derived facts |
| C3 | Add dual-write to `cognee_index.py` (also update `memory.db`) | Run indexer; verify both `memory.db` and Cognee contain new chunks |

### Phase D: Evaluation & Hardening (2-3 days)

| # | Task | Verification |
|---|---|---|
| D1 | Build 20-question multi-hop eval set | `tests/test_cognee_memory.py` — run `pytest` |
| D2 | Measure baseline vs Cognee accuracy | Document results in `Memory/research/cognee-eval-2026-05-xx.md` |
| D3 | Add retry, error handling, and fallback to sqlite-vec | Simulate Cognee failure; verify fallback to `memory_search.py` |
| D4 | Performance benchmark: indexing latency | Run `python cognee_index.py --benchmark` on full vault |

### Parallel Opportunities

- **A1 + A2** can happen in parallel (install vs code)
- **B1 + B2** can happen in parallel (independent hooks)
- **C1 + C2** can happen in parallel (heartbeat vs reflection)

## 12. Decisions Log

| # | Decision | Rationale | Date |
|---|---|---|---|
| 1 | Cognee adjacent to existing sqlite-vec, not replacement | Preserve backward compatibility; enable A/B testing | 2026-05-22 |
| 2 | Embedded stack: SQLite + LanceDB + Kuzu | Aligns with local-first, zero-Docker constraint; same four-call API as cloud backends | 2026-05-22 |
| 3 | Single dataset (`"main"`) for v1 | Simplifies API; per-source datasets are "nice to have" | 2026-05-22 |
| 4 | `GRAPH_COMPLETION` as primary search type | Enables multi-hop reasoning; fallback to `SIMILARITY` for simple queries | 2026-05-22 |
| 5 | Manual `memify()` trigger for v1 | Avoids unbounded LLM cost; auto-scheduling is "nice to have" | 2026-05-22 |
| 6 | Keep FastEmbed for sqlite-vec; use OpenAI embeddings for Cognee (default) | Cognee's graph extraction quality depends on embedding quality; accept cost for v1 | 2026-05-22 |

---

## Validation Notes

All technical references verified against the Second Brain codebase as of commit `646f3c8`:

| Claim | Verified Against | Status |
|---|---|---|
| SQLite + sqlite-vec + FTS5 hybrid RAG | `.claude/scripts/db.py:8-197` | Confirmed |
| 384-dim float32 embeddings via FastEmbed | `.claude/scripts/embeddings.py:5-11` | Confirmed |
| Incremental indexing with SHA-256 + chunking | `.claude/scripts/memory_index.py:23-76` | Confirmed |
| SessionStart hook injects raw SOUL/USER/MEMORY + 3 daily logs | `.claude/hooks/session-start-context.py:32-61` | Confirmed |
| Heartbeat polls Gmail/Slack/GitHub, logs to daily logs | `.claude/scripts/heartbeat.py:1-60+` | Confirmed |
| Memory reflection promotes daily items to MEMORY.md | `.claude/scripts/memory_reflect.py:1-50+` | Confirmed |
| No entity table, no relationship table in current schema | `.claude/scripts/db.py:33-57` | Confirmed |
| Requirements pinned; no cognee present | `requirements.txt:1-31` | Confirmed |
| Cognee API: `add`, `cognify`, `memify`, `search` | Research via `docs.cognee.ai/python-api` | Confirmed (external) |
| Cognee embedded stack: SQLite + LanceDB + Kuzu | Research via GitHub `topoteretes/cognee` | Confirmed (external) |

**Unverified claims (need research):**
- Cognee's exact PyPI version and transitive dependencies (will verify at `pip install` time)
- Whether Cognee supports non-OpenAI LLMs for `cognify()` (Open Question #5)
- Windows 11 compatibility of LanceDB + Kuzu (assumed yes; will verify in Phase A)

---

## Next Step

To begin implementation: execute Phase A (setup + wrapper) above.
