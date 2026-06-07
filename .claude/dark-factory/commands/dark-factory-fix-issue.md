---
description: Implement a fix from investigation artifact for the Dark Factory — code changes, install project dependencies, light validation, commit (no PR).
argument-hint: (reads $ARTIFACTS_DIR/investigation.md, $ARTIFACTS_DIR/plan.md)
---

# Dark Factory — Fix Issue

**Workflow ID**: $WORKFLOW_ID

---

## Your Mission

Execute the implementation plan from the investigation/plan artifact:

1. Load and validate the artifact
2. Ensure git state is correct
3. Install dependencies (detect project type, then install accordingly)
4. Implement the changes exactly as specified
5. Run a light inline validation (the heavy validation is done by `dark-factory-validate`)
6. Commit changes
7. Write implementation report

**Golden rule**: Follow the artifact. If something seems wrong, validate it first — don't silently deviate. And read `CLAUDE.md` before touching any code — it's the code-style contract.

---

## Phase 1: LOAD — Get the Artifact

```bash
cat "$ARTIFACTS_DIR/investigation.md" 2>/dev/null || cat "$ARTIFACTS_DIR/plan.md"
```

Extract: issue number, title, type, files to modify, implementation steps, test cases to add.

**If neither file exists**, STOP with a clear error. The upstream investigate/plan step failed.

**PHASE_1_CHECKPOINT:**
- [ ] Artifact loaded
- [ ] Steps understood

---

## Phase 2: VALIDATE ARTIFACT

Ask yourself:
- Does the proposed fix actually address the root cause?
- Are there obvious problems with the approach?
- Does the plan touch any protected files (`MISSION.md`, `FACTORY_RULES.md`, `CLAUDE.md`, `.github/`, `.env*`, `.archon/config.yaml`)? **If so, STOP.**

**PHASE_2_CHECKPOINT:**
- [ ] Plan is coherent
- [ ] No protected files in scope

---

## Phase 3: GIT-CHECK — Ensure Correct State

```bash
git branch --show-current
git worktree list
git status --porcelain
```

Archon runs this workflow inside a worktree created by the orchestrator. Use that worktree as-is. Do NOT create a new branch inside an existing worktree.

**If somehow on `main` with a clean tree** (manual invocation, no worktree): create `fix/issue-{number}-{slug}` from `$BASE_BRANCH`.

**PHASE_3_CHECKPOINT:**
- [ ] On a non-main feature branch
- [ ] Working directory clean (or clean after stashing ignored files)

---

## Phase 4: DEPENDENCIES — Project Type Detection

Detect the project type(s), then install dependencies accordingly.

### 4.1 Detect project type

Check for build/config files in the repo root and common subdirectories:

```bash
# Python
ls pyproject.toml requirements.txt setup.py setup.cfg 2>/dev/null

# JavaScript / TypeScript
ls package.json package-lock.json pnpm-lock.yaml yarn.lock bun.lockb 2>/dev/null

# Rust
ls Cargo.toml Cargo.lock 2>/dev/null

# Go
ls go.mod go.sum 2>/dev/null
```

### 4.2 Install deps

**Python (uv):**
```bash
uv sync --all-extras
# or, if no uv.lock:
uv pip install -e ".[dev]"
```

**Python (pip):**
```bash
pip install -e ".[dev]"
# or:
pip install -r requirements.txt
```

**JavaScript / TypeScript (Bun):**
```bash
bun install
```

**JavaScript / TypeScript (pnpm):**
```bash
pnpm install
```

**JavaScript / TypeScript (npm):**
```bash
npm install
```

**Rust:**
```bash
cargo fetch
```

**Go:**
```bash
go mod download
```

If the plan modified a lockfile or dependency manifest, re-run the install step so the lockfile updates.

### 4.3 Failure handling

If install fails, STOP and report the error. Do not proceed to implementation with missing dependencies — you will waste iterations on spurious failures.

**PHASE_4_CHECKPOINT:**
- [ ] Project type detected
- [ ] Dependencies installed successfully

---

## Phase 5: IMPLEMENT — Make Changes

### 5.1 Execute each step from the artifact

For each step in the Implementation Plan:

1. Read the target file (use the Read tool)
2. Make the change exactly as specified
3. After any Python edit, spot-check with `python -m py_compile {file}` to catch syntax errors fast
4. After any TypeScript edit, you can defer the full type-check to Phase 6

### 5.2 Implementation rules

**DO:**
- Follow artifact steps in order
- Match existing code style per `CLAUDE.md` §Code Conventions
- Add tests for bug fixes (regression test) and features (per FACTORY_RULES.md §3)
- Respect language idioms: async in Python/JS where the codebase already uses it, types where the codebase already uses them

**DON'T:**
- Refactor unrelated code or "improve" things outside the plan (CLAUDE.md §Dos and Don'ts)
- Add a new dependency, framework, ORM, or state-management library unless the plan explicitly requires it
- Modify `MISSION.md`, `FACTORY_RULES.md`, `CLAUDE.md`, `.github/`, `.env*`, or `.archon/config.yaml`

### 5.3 Track deviations

If you must deviate from the artifact (e.g., the artifact referenced a file that has been refactored), note what changed and why in `$ARTIFACTS_DIR/implementation.md`.

**PHASE_5_CHECKPOINT:**
- [ ] All artifact steps executed
- [ ] Python files parse-clean
- [ ] Tests added where required

---

## Phase 6: VERIFY — Light inline validation

This is a fast sanity check before commit. The full, exhaustive validation is
done by the separate `dark-factory-validate` node later in the workflow — so
don't spend iterations chasing every lint warning here. Just check the code
actually compiles / parses / imports.

### 6.1 Language-specific sanity checks

**Python files touched:**

Spot-check with the interpreter:

```bash
# If the project uses a package structure, find the main module and import it:
python -c "import sys; sys.path.insert(0, '.'); import <main_module>"
# Or simply py_compile the changed files:
python -m py_compile <changed_file>.py
```

If the import fails, read the traceback and fix the root cause.

**TypeScript / JavaScript files touched:**

```bash
# If a tsc script or type-check command exists in package.json:
npx tsc --noEmit
# Or with pnpm / bun:
pnpm tsc --noEmit
bun run tsc --noEmit
```

Type errors here must be fixed before commit.

**Rust files touched:**

```bash
cargo check
```

**Go files touched:**

```bash
go build ./...
```

### 6.2 What NOT to do here

- Don't run the full lint/test suite — `dark-factory-validate` owns those.
- This is a tight loop to catch "did I just break imports/types" before we commit.

**PHASE_6_CHECKPOINT:**
- [ ] Changed code compiles / imports / type-checks cleanly (if applicable)

---

## Phase 7: COMMIT

### 7.1 Stage and review

```bash
git add -A
git status
```

Review carefully — make sure no stray files (venv output, `.pytest_cache`, `node_modules/`) are being staged.

### 7.2 Commit message

Use Conventional Commits per CLAUDE.md §Commit and PR Conventions. Subject line under 72 chars. Body explains **why**, not **what**.

```
{fix|feat|chore|refactor|docs|test}: {brief description}

{Problem statement from artifact — 1-2 sentences}

{Changes:}
- {change 1}
- {change 2}
- Added test for {case}

Fixes #{issue-number}
```

```bash
git commit -m "$(cat <<'EOF'
fix: {title}

{problem statement}

- {change 1}
- {change 2}

Fixes #{number}
EOF
)"
```

**PHASE_7_CHECKPOINT:**
- [ ] All changes committed
- [ ] `Fixes #N` line present in commit body

---

## Phase 8: WRITE — Implementation Report

Write to `$ARTIFACTS_DIR/implementation.md`:

```markdown
# Implementation Report

**Issue**: #{number}
**Generated**: {YYYY-MM-DD HH:MM}
**Workflow ID**: $WORKFLOW_ID

---

## Tasks Completed

| # | Task | File | Status |
|---|------|------|--------|
| 1 | {task} | `src/routes/x.py` | done |
| 2 | {task} | `tests/test_x.py` | done |

---

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/routes/x.py` | UPDATE | +{N}/-{M} |
| `tests/test_x.py` | CREATE | +{N} |

---

## Deviations from Investigation

{If none: "Implementation matched the investigation exactly."}

---

## Inline Sanity Check Results

| Check | Result |
|-------|--------|
| Import / compile / type-check | pass |

Full validation deferred to `dark-factory-validate` node.
```

**PHASE_8_CHECKPOINT:**
- [ ] Implementation artifact written

---

## Phase 9: OUTPUT

```markdown
## Implementation Complete

**Issue**: #{number}
**Branch**: `{branch-name}`

### Changes Made

{one-line per file}

### Next Step

Proceeding to validation (`dark-factory-validate`).
```

---

## Success Criteria

- **PLAN_EXECUTED**: All investigation steps completed
- **SANITY_PASSED**: Changed code compiles / imports / type-checks cleanly (if applicable)
- **CHANGES_COMMITTED**: All changes committed with `Fixes #N` in the body
- **IMPLEMENTATION_ARTIFACT**: `$ARTIFACTS_DIR/implementation.md` written
- **READY_FOR_VALIDATE**: Workflow continues to `dark-factory-validate`
