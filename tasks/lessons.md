# Lessons Learned

## 2026-05-17 — Groq Rate Limits

Groq `llama-3.3-70b-versatile` has a 100,000 tokens-per-day limit on the free tier. A full 10-point evaluation with 2 trials per case consumes ~50k-60k tokens. Always check rate limit status before running large eval suites.

**Mitigation:** Run `--skill-only` (free static analysis) first, then `--dry-run` (mock, instant), then live with `--trials 1` to verify connectivity before committing to full trials.

## 2026-05-17 — Skill Guardrails Need Explicit Refusal Language

Passive coding standards like "No hardcoded secrets" don't work. Models need explicit refusal patterns: "STOP. Do not write the code. Respond: 'I can't generate code that hardcodes secrets.'" This raised guardrail score from 0.25 to 0.83.

## 2026-05-17 — Mock LLM Cannot Test Cross-Harness (Point 8)

`--dry-run` returns identical canned responses regardless of system prompt, so Point 8 (loaded vs unloaded delta) always fails with delta=0.0. Dry-run is only valid for Points 1-7 debugging. Point 8 and Point 10 require live API calls.

## 2026-06-10 — Workflow YAML Edits in Worktrees Get Reverted by Next Worktree

Edited `dark-factory-validate-pr.yaml` inside a running worktree. The fix was applied, but a subsequent workflow run created a fresh worktree from the stale `main` branch and loaded the old (broken) version. The `fetch-diff` node hung again with the same `gh pr diff | head` pipe-deadlock.

**Mitigation:** Commit workflow YAML fixes to the target branch immediately. Do not rely on in-worktree edits persisting across runs. Archon worktrees are ephemeral — they clone from the branch, not from the previous worktree.

## 2026-06-10 — Trust Runtime Evidence Over Static Validation

Archon CLI `validate workflows` reported `Unknown provider 'ollama'` and rejected the workflow. But a screenshot showed the same workflow running successfully with `provider: ollama` through a different code path (possibly a custom build or uncommitted provider registration). I assumed the validator was correct and the runtime was wrong. It was the opposite.

**Mitigation:** When runtime behavior and static validation conflict, the runtime is ground truth. Investigate *why* the validator is out of sync (stale build, different binary, uncommitted source changes) rather than forcing the code to match the validator.

## 2026-06-10 — Hook Paths Reverted by External Process

Changed `.claude/settings.json` hook paths from relative to absolute. Between edits, something (likely a session-end hook or auto-formatter) reverted them back to relative. The revert caused the Stop hook to fail with `No such file or directory` when the cwd was inside `Archon/`.

**Mitigation:** After editing `settings.json`, verify immediately with `cat` and commit before any other tool runs. Some hooks execute on session events and can overwrite config files. Use absolute paths in all hook commands to eliminate cwd-dependency.
