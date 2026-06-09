# PRD — Cognee Integration Fixes & Production Hardening

> Generated: 2026-05-23
> Status: Draft — ready for implementation
> Scope: Second Brain only

---

## 1. Problem Statement

The Cognee graph-vector hybrid memory layer was successfully built but fails in practice due to three critical issues:

**Issue A: Test Isolation Failure**
The `CogneeMemory` class uses a singleton pattern (`_instances` dict) that reuses the same instance across tests. When `pytest` runs multiple tests, data ingested in `test_cognify_builds_graph` pollutes `test_search_similarity`. This makes the test suite unreliable and hides real bugs.

**Issue B: SQLite Database Locked**
Cognee's internal pipeline (`classify_documents` → `extract_chunks_from_documents` → `extract_graph_and_summarize` → `add_data_points`) runs multiple coroutines concurrently. All hit the same SQLite database file via aiosqlite, causing `(sqlite3.OperationalError) database is locked` errors. This kills the pipeline mid-run.

**Issue C: Missing Production Wiring**
The core infrastructure exists (`cognee_memory.py`, `cognee_index.py`, hook integrations) but:
- `memory_reflect.py` still uses regex promotion instead of `cognee.memify()`
- `heartbeat.py` doesn't query Cognee for cross-entity drafting context
- No automated scheduling for `cognify()` runs
- No multi-hop evaluation harness to measure accuracy vs sqlite-vec baseline

---

## 2. Evidence

### Issue A: Singleton Pollution

```python
# .claude/scripts/cognee_memory.py:121-127
class CogneeMemory:
    _instances: dict[str, CogneeMemory] = {}

    def __new__(cls, config: Optional[CogneeBackendConfig] = None, instance_id: str = "default"):
        if instance_id not in cls._instances:
            cls._instances[instance_id] = super().__new__(cls)
            cls._instances[instance_id]._initialized = False
        return cls._instances[instance_id]
```

**Test failure evidence:**
- `test_search_similarity` failed because "outage" was not in results — the graph from `test_cognify_builds_graph` had different data
- `test_search_empty_dataset` returned data when it expected empty — previous test data leaked

### Issue B: SQLite Lock Contention

**Log evidence:**
```
ERROR run_tasks(tasks: [Task], data):run_tasks.py:128
Item 1 failed: (sqlite3.OperationalError) database is locked
[SQL: UPDATE data SET token_count=?, updated_at=? WHERE data.id = ?]
```

**Root cause:** Cognee v1.1.0 uses aiosqlite with default timeout. When multiple pipeline tasks write concurrently, SQLite's reader-writer lock blocks writers. The default `timeout` parameter on `sqlite3.connect()` is 5 seconds, which is insufficient under concurrent load.

### Issue C: Missing Integrations

| Component | File | Status |
|-----------|------|--------|
| `cognee_memory.py` | `.claude/scripts/cognee_memory.py` | Built, singleton issue |
| `cognee_index.py` | `.claude/scripts/cognee_index.py` | Built, no scheduling |
| SessionStart hook | `.claude/hooks/session-start-context.py` | Built, Cognee search integrated |
| PreCompact hook | `.claude/hooks/pre-compact-flush.py` | Built, Cognee ingest integrated |
| `memory_reflect.py` | `.claude/scripts/memory_reflect.py` | NOT integrated — still regex-based |
| `heartbeat.py` | `.claude/scripts/heartbeat.py` | NOT integrated — no Cognee recall |
| Multi-hop eval | `tests/eval_multi_hop.py` | NOT built |
| Auto-scheduling | Windows Task Scheduler | NOT configured |

---

## 3. Proposed Solution

### Fix A: Remove Singleton Pattern

Replace the singleton with instance factories that return fresh objects. Add a `clear_instances()` helper for test teardown.

### Fix B: Increase SQLite Timeout + Connection Pooling

Patch Cognee's aiosqlite connection creation to use a longer timeout (30s) and WAL mode for better concurrency.

### Fix C: Wire Production Integrations

1. **memory_reflect.py** — Add `CogneeMemory.memify()` call after regex promotion
2. **heartbeat.py** — Add `CogneeMemory.search(GRAPH_COMPLETION)` before drafting emails/Slack replies
3. **eval_multi_hop.py** — Build 20-question benchmark comparing sqlite-vec vs Cognee
4. **Auto-scheduling** — Windows Task Scheduler nightly job for `cognee_index.py --cognify`

---

## 4. Key Hypothesis

> We believe that fixing test isolation and SQLite concurrency will make the Cognee layer reliable enough for production use. We'll know we're right when all 19 tests in `test_cognee_memory.py` pass (fast + slow) consistently across 5 consecutive runs.

Secondary hypothesis:
> We believe that wiring `memify()` into `memory_reflect.py` and Cognee search into `heartbeat.py` will improve draft relevance by surfacing implicit relationships across the Memory vault.

---

## 5. What We're NOT Building

| Out of Scope | Rationale |
|---|---|
| Migrate existing `memory.db` data to Cognee | Too risky; dual-write mode is sufficient |
| Replace sqlite-vec entirely | Adjacent layer, not replacement |
| Web UI for graph visualization | Nice-to-have; Kuzu Explorer exists |
| Custom embedding model fine-tuning | FastEmbed is sufficient for v1 |
| Multi-tenant support | Single-user system |

---

## 6. Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Test suite reliability | 10/19 pass (52%) | 19/19 pass (100%) | Run `pytest tests/test_cognee_memory.py` 5x |
| SQLite lock errors | ~6 per run | 0 | Count `(sqlite3.OperationalError) database is locked` in logs |
| Multi-hop query accuracy | N/A | >60% | `tests/eval_multi_hop.py` — 20 questions |
| Memory consolidation | Manual regex only | Auto memify() weekly | Count facts added by memify() vs regex |

---

## 7. Solution Detail

### Must Have (v1 Fixes)

| # | Feature | Description |
|---|---|---|
| 1 | Remove singleton from `CogneeMemory` | Replace `_instances` dict with factory methods; add `clear_instances()` for tests |
| 2 | SQLite timeout patch | Monkey-patch aiosqlite to use 30s timeout + WAL mode |
| 3 | Unique data dirs per test | `temp_cognee` fixture generates isolated `data_root` + `system_root` |
| 4 | Fix test assertions | Update assertions to match actual Cognee output format |
| 5 | `memory_reflect.py` integration | Call `cognee.memify()` after regex promotion |

### Should Have (v1.1)

| # | Feature | Description |
|---|---|---|
| 6 | `heartbeat.py` Cognee recall | Query graph before drafting emails/Slack replies |
| 7 | Multi-hop eval harness | `tests/eval_multi_hop.py` — 20 questions with expected answers |
| 8 | Auto-cognify scheduling | Windows Task Scheduler nightly job |

### Nice to Have (v2)

| # | Feature | Description |
|---|---|---|
| 9 | Graph visualization | Export Kuzu graph to HTML for manual inspection |
| 10 | Performance benchmark | Measure indexing latency on full vault |

---

## 8. Technical Approach

### Fix A: Remove Singleton

**File:** `.claude/scripts/cognee_memory.py`

```python
# BEFORE (lines 121-127)
class CogneeMemory:
    _instances: dict[str, CogneeMemory] = {}

    def __new__(cls, config=None, instance_id="default"):
        if instance_id not in cls._instances:
            cls._instances[instance_id] = super().__new__(cls)
            cls._instances[instance_id]._initialized = False
        return cls._instances[instance_id]

# AFTER
class CogneeMemory:
    """Non-singleton: create fresh instances via factory."""
    
    @classmethod
    def create(cls, config=None, instance_id="default") -> CogneeMemory:
        instance = super().__new__(cls)
        instance._initialized = False
        instance.cfg = config or CogneeBackendConfig()
        instance._initialized = True
        instance._apply_config()
        return instance
```

Update `create_memory()` factory to use `CogneeMemory.create()` instead of `CogneeMemory()`.

### Fix B: SQLite Timeout

**File:** `.claude/scripts/cognee_memory.py` (inside `_apply_config`)

Add before Cognee init:
```python
# Patch aiosqlite to use longer timeout
import aiosqlite
_original_connect = aiosqlite.connect

def _patched_connect(*args, **kwargs):
    kwargs.setdefault("timeout", 30.0)
    return _original_connect(*args, **kwargs)

aiosqlite.connect = _patched_connect
```

After Cognee creates its SQLite database, enable WAL mode:
```python
# Enable WAL mode for better concurrent read/write
async def _enable_wal():
    db_path = Path(cognee.config.system_root_directory) / "databases" / "cognee_db.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()
```

### Fix C: Test Fixture Update

**File:** `tests/test_cognee_memory.py`

```python
@pytest.fixture
def temp_cognee(tmp_path):
    data_root = tmp_path / "cognee" / "data_storage"
    system_root = tmp_path / "cognee" / "system"
    data_root.mkdir(parents=True)
    system_root.mkdir(parents=True)

    cfg = CogneeBackendConfig(
        relational_provider="sqlite",
        relational_db_name="test_cognee_db",
        graph_provider="kuzu",
        vector_provider="lancedb",
        data_root_directory=data_root,
        system_root_directory=system_root,
        dataset_name="test",
        llm_model="qwen2.5-coder:1.5b",
    )
    # Use factory, not singleton
    mem = CogneeMemory.create(config=cfg)
    yield mem
```

### Fix D: memory_reflect.py Integration

**File:** `.claude/scripts/memory_reflect.py`

After regex-based promotion to `MEMORY.md`, add:
```python
async def _cognee_consolidate(items: list[str]) -> None:
    """Push promoted items into Cognee graph for self-improvement."""
    try:
        from cognee_memory import create_memory
        mem = create_memory()
        text = "\n".join(items)
        await mem.ingest_text(text, source="memory_reflect")
        await mem.memify()
    except Exception as exc:
        print(f"[memory_reflect] Cognee consolidation failed: {exc}", file=sys.stderr)
```

---

## 9. Implementation Phases

### Phase A: Test Isolation (1-2 hours)

| # | Task | Verification |
|---|---|---|
| A1 | Remove singleton from `cognee_memory.py` | `python -c "from cognee_memory import CogneeMemory; a=CogneeMemory.create(); b=CogneeMemory.create(); assert a is not b"` |
| A2 | Update `create_memory()` factory | `python -c "from cognee_memory import create_memory; m=create_memory(); print(m.cfg.graph_provider)"` |
| A3 | Fix `temp_cognee` fixture in tests | Run `pytest tests/test_cognee_memory.py -v -m "not slow"` — all 10 pass |
| A4 | Update test assertions for actual Cognee output | No assertion failures on content keywords |

### Phase B: SQLite Concurrency (1 hour)

| # | Task | Verification |
|---|---|---|
| B1 | Patch aiosqlite timeout to 30s | Run slow tests, check logs for zero "database is locked" errors |
| B2 | Enable WAL mode on Cognee SQLite | `PRAGMA journal_mode;` returns `wal` |
| B3 | Run slow tests 5x in a row | All pass consistently |

### Phase C: Production Wiring (2-3 hours)

| # | Task | Verification |
|---|---|---|
| C1 | Integrate `memify()` into `memory_reflect.py` | Run reflection, verify Cognee log shows `memify()` activity |
| C2 | Add Cognee recall to `heartbeat.py` | Inspect draft output for cross-entity context |
| C3 | Build `tests/eval_multi_hop.py` | Run eval, document baseline vs Cognee accuracy |
| C4 | Create Windows Task Scheduler job for nightly cognify | Task exists, runs `python .claude/scripts/cognee_index.py --cognify` |

---

## 10. Decisions Log

| # | Decision | Rationale | Date |
|---|---|---|---|
| 1 | Remove singleton instead of making it test-safe | Singletons are anti-patterns in Python; factories are cleaner | 2026-05-23 |
| 2 | Monkey-patch aiosqlite instead of forking Cognee | Cognee is external dependency; minimal invasive change | 2026-05-23 |
| 3 | Use WAL mode for SQLite | Enables concurrent reads while writes proceed | 2026-05-23 |
| 4 | Keep Kuzu for tests, FalkorDB for production | Kuzu is embedded (no Docker); FalkorDB requires container | 2026-05-23 |
| 5 | memify() in memory_reflect.py, not heartbeat | Reflection runs daily (safe cadence); heartbeat is too frequent | 2026-05-23 |

---

## Next Step

To begin implementation: execute Phase A (remove singleton + fix tests) above.
