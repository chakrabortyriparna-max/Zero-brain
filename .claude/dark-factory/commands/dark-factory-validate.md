---
description: Run Dark Factory validation — auto-detect project type and run appropriate static checks and tests.
argument-hint: (no arguments — reads $ARTIFACTS_DIR/implementation.md and git diff)
---

# Dark Factory Validation

**Workflow ID**: $WORKFLOW_ID

---

## Your Mission

Run the full validation suite for this repo and fix any failures.
Auto-detect the project type from files present (`pyproject.toml`,
`requirements.txt`, `package.json`, etc.) and run the appropriate checks.
This validate step runs the same checks a human would run before committing.

**Golden rule**: run each check, read the error, fix the root cause (not the
test), re-run until green. Never modify tests to make them pass — that's an
explicit CLAUDE.md violation.

---

## Phase 1: SCOPE — What Did the Implementation Touch?

The diff may be backend-only, frontend-only, docs-only, or mixed. Run only the
checks that apply, so we don't waste tokens re-validating untouched layers.

```bash
git diff --name-only $BASE_BRANCH...HEAD
```

Classify each changed file by detecting the project structure:

| Path prefix / File            | Layer     |
|-------------------------------|-----------|
| `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py` | backend   |
| `package.json`, `tsconfig.json`, `*.ts`, `*.tsx`, `*.js`, `*.jsx` | frontend  |
| `*.md`, `docs/`               | docs only |
| `.github/`, `FACTORY_RULES.md`, `MISSION.md`, `CLAUDE.md` | **forbidden — see hard rules** |

**Hard rules (FACTORY_RULES.md §5 and §Protected Files):**

- If the diff touches `FACTORY_RULES.md`, `MISSION.md`, or `CLAUDE.md` — STOP and
  write a validation BLOCKED artifact. Governance files are not factory-editable.
- If the diff touches `.github/`, Dockerfiles, `.env*`, or `.archon/config.yaml` —
  STOP and write a validation BLOCKED artifact.
- If no source files changed and only docs changed, run the `docs-only`
  fast path (see §5.4 below).

**PHASE_1_CHECKPOINT:**
- [ ] Touched layers identified
- [ ] No protected files modified

---

## Phase 2: BACKEND CHECKS (if backend layer touched)

Backend validation commands — auto-detected from project files. All commands run
from the repo root unless a tool requires a specific directory.

### 2.1 Detect backend type

- If `pyproject.toml` exists → modern Python project (use ruff / mypy / pytest).
- Else if `setup.py` exists → setuptools project (use pylint / pytest).
- Else if `requirements.txt` exists → plain Python project (use pylint / pytest).
- If none exist → record `SKIPPED - no backend detected`.

### 2.2 Ensure backend deps are installed

For `pyproject.toml` projects, install with your environment manager of choice
(e.g., `pip install -e .[dev]` or `poetry install`). For `requirements.txt`
projects, use `pip install -r requirements.txt`.

### 2.3 Lint

**If `pyproject.toml` exists:**

```bash
ruff check .
```

**If `pyproject.toml` does not exist:**

```bash
pylint $(git ls-files '*.py')
```

**If fails:**
1. Try auto-fix (ruff only): `ruff check --fix .`
2. Re-run lint
3. If still failing, manually fix the reported issues

**Record result**: Pass / Fail (fixed)

### 2.4 Format check

**If `pyproject.toml` exists:**

```bash
ruff format --check .
```

**If fails:**
1. Auto-fix — **scoped to files this branch modified** so we never reformat unrelated (protected) files:
   ```bash
   git diff --name-only origin/main -- '*.py' '**/*.py' \
     | xargs -r ruff format
   ```
   Do NOT run `ruff format .` repo-wide — that can cause PRs to be auto-rejected for touching protected files with cosmetic-only collateral.
2. Verify: `ruff format --check .` — if this still fails on files outside the diff, leave them alone (they pre-date this branch); record `Pass (drift remains in unmodified files)`.

**Record result**: Pass / Fail (fixed)

### 2.5 Type check

**If `pyproject.toml` exists:**

```bash
mypy .
```

**If fails:**
1. Read each error carefully — prefer adding a real type annotation over `# type: ignore`
2. Fix by tightening types at the source, not by silencing mypy
3. `# type: ignore` is only acceptable when bridging an untyped third-party dep, with a comment explaining why

**Record result**: Pass / Fail (fixed)

### 2.6 Pytest

```bash
pytest tests -xvs
```

**If `tests/` does not exist:**
- If the implementation added no tests (e.g., pure refactor, config change), record `SKIPPED - no tests`.
- If the implementation SHOULD have added tests (bug fix, feature), that's a validation failure — the implement step violated FACTORY_RULES.md §3 ("Always include tests for new features" / regression tests for bug fixes). Either add the missing tests yourself or mark validation BLOCKED with a clear reason.

**If fails:**
1. Identify which test(s) failed
2. Is it an implementation bug or test bug? Implementation bugs = fix the source. Test bugs in tests YOU just wrote = fix the test. Test bugs in pre-existing tests = **do not modify**, this likely means your change regressed something — fix the source.
3. Re-run

**Record result**: Pass ({N} tests) / Fail (fixed) / SKIPPED

**PHASE_2_CHECKPOINT:**
- [ ] Lint passes
- [ ] Format passes
- [ ] Type check passes (if applicable)
- [ ] Pytest passes or skipped with reason

---

## Phase 3: FRONTEND CHECKS (if frontend layer touched)

Frontend validation commands — auto-detected from `package.json`.

### 3.1 Detect frontend scripts

Read `package.json` scripts. Common checks:
- `tsc` / `tsc --noEmit` → type check
- `eslint` / `lint` → lint
- `vitest` / `jest` / `test` → tests
- `build` → build sanity

If `package.json` does not exist → record `SKIPPED - no frontend detected`.

### 3.2 Ensure frontend deps installed

```bash
if [ ! -d "node_modules" ]; then
  npm install   # or pnpm install / yarn install as appropriate
fi
```

### 3.3 TypeScript type check

If `package.json` contains a `tsc` or `typecheck` script, run it (e.g., `npm run tsc -- --noEmit`).
Otherwise, if `tsconfig.json` exists, run `npx tsc --noEmit`.

**If fails:**
1. Read errors; fix the types. Do NOT add `any` — CLAUDE.md §Code Conventions forbids it except when bridging an untyped dep.
2. Re-run

**Record result**: Pass / Fail (fixed)

### 3.4 Lint + format check

If `package.json` contains an `eslint` or `lint` script, run it (e.g., `npm run lint`).
If it contains a `format:check` or `prettier --check` script, run that too.

**If fails:**
1. Try auto-fix: `npm run lint -- --fix` or `npx prettier --write {changed-files}`
2. Re-run
3. If still failing, manually fix

**Record result**: Pass / Fail (fixed)

### 3.5 Tests

If `package.json` contains a `test` script (vitest, jest, etc.), run it (e.g., `npm run test`).

**Handling the same test-absence logic as Phase 2.6:**
- If no test script or no tests exist yet, record `SKIPPED - no tests`.
- If the implementation added tests, they must pass.
- Never modify pre-existing passing tests to absorb your changes.

**Record result**: Pass ({N} tests) / Fail (fixed) / SKIPPED

### 3.6 Frontend build sanity (light — only if build config changed)

If `package.json` contains a `build` script, run it (e.g., `npm run build`).

Skip this unless the implementation touched build configuration. The type-check
in 3.3 already catches most build failures.

**PHASE_3_CHECKPOINT:**
- [ ] Type check passes
- [ ] Lint / format passes
- [ ] Tests pass or skipped with reason
- [ ] Build passes (if run)

---

## Phase 4: PROJECT INVARIANTS (always — cheap guard against silent regressions)

If the repo contains a `CLAUDE.md` or `FACTORY_RULES.md` that lists project
invariants (behaviors, configs, or architectural constraints that MUST NOT
regress), read the invariant list and verify them against the diff.

**Procedure:**
1. Scan `CLAUDE.md` and `FACTORY_RULES.md` for sections titled "Invariants",
   "Pipeline Invariants", "Architecture Invariants", or similar.
2. For each invariant listed, check whether the diff touches the relevant files.
3. If the diff touches those files, verify the invariant still holds.
4. If no invariants are documented, skip this phase and record `SKIPPED - no invariants defined`.

Any regression on a documented invariant is an automatic validation FAIL —
even if static checks pass. Write the regression into the artifact and stop.

**PHASE_4_CHECKPOINT:**
- [ ] Project invariants verified (or skipped because none are defined or diff didn't touch relevant files)

---

## Phase 5: ARTIFACT — Write validation.md

Write to `$ARTIFACTS_DIR/validation.md`:

```markdown
# Validation Results

**Generated**: {YYYY-MM-DD HH:MM}
**Workflow ID**: $WORKFLOW_ID
**Status**: {ALL_PASS | FIXED | BLOCKED}
**Layers touched**: {backend, frontend, docs, or combinations}

---

## Summary

| Check            | Layer    | Result        | Details                |
|------------------|----------|---------------|------------------------|
| Lint             | backend  | pass / fixed  | {N} auto-fixed         |
| Format           | backend  | pass / fixed  |                        |
| Type check       | backend  | pass / fixed  | {N} type errors fixed  |
| Tests            | backend  | pass ({N})    |                        |
| Type check       | frontend | pass / fixed  |                        |
| Lint / format    | frontend | pass / fixed  | {N} auto-fixed         |
| Tests            | frontend | pass ({N})    |                        |
| Project invariants | all      | pass          | {list of invariants checked} |

---

## Files Modified During Validation

{If validation had to fix any files, list them with a one-line reason per file.}

---

## Issues Remaining

{If BLOCKED: what check failed, what was tried, what manual intervention is needed.}
```

### 5.4 Docs-only fast path

If Phase 1 determined the diff is docs-only (no source files changed),
skip Phases 2-4 entirely and write:

```markdown
# Validation Results

**Status**: ALL_PASS
**Layers touched**: docs
**Skipped**: backend + frontend checks (no source changes)

This PR is documentation-only. Static checks and tests are not applicable.
Reviewed that only `.md` files and/or `docs/` were modified.
```

**PHASE_5_CHECKPOINT:**
- [ ] `$ARTIFACTS_DIR/validation.md` written
- [ ] Status accurately reflects what ran and what passed

---

## Phase 6: OUTPUT — Report back to the workflow

### If all pass:

```markdown
## Validation Complete

**Workflow ID**: `$WORKFLOW_ID`

Backend: lint / format / type check / tests — all pass
Frontend: type check / lint / tests — all pass
Project invariants: verified

Artifact: `$ARTIFACTS_DIR/validation.md`

Next: proceed to create-pr.
```

### If blocked:

```markdown
## Validation BLOCKED

**Workflow ID**: `$WORKFLOW_ID`

### Failed check
{check-name}: {short error summary}

### What was tried
1. {attempt 1}
2. {attempt 2}

### Required action
{what needs manual intervention — or why this is a real bug in the implementation
that the implement step produced}

Artifact: `$ARTIFACTS_DIR/validation.md`
```

---

## Success Criteria

- **BACKEND_LINT_PASS**: `ruff check .` (or `pylint`) exits 0
- **BACKEND_FORMAT_PASS**: `ruff format --check .` (or equivalent) exits 0
- **BACKEND_TYPE_PASS**: `mypy .` (or equivalent) exits 0
- **BACKEND_TESTS_PASS**: `pytest tests -xvs` all green (or skipped with reason)
- **FRONTEND_TYPE_PASS**: `tsc --noEmit` (or equivalent) exits 0
- **FRONTEND_LINT_PASS**: `eslint` / `biome check` (or equivalent) exits 0
- **FRONTEND_TESTS_PASS**: `vitest` / `jest` / `npm test` all green (or skipped with reason)
- **PROJECT_INVARIANTS_PASS**: no regressions per documented invariants in CLAUDE.md or FACTORY_RULES.md
- **ARTIFACT_WRITTEN**: `$ARTIFACTS_DIR/validation.md` exists with accurate status
