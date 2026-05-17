# Lessons Learned

## 2026-05-17 — Groq Rate Limits

Groq `llama-3.3-70b-versatile` has a 100,000 tokens-per-day limit on the free tier. A full 10-point evaluation with 2 trials per case consumes ~50k-60k tokens. Always check rate limit status before running large eval suites.

**Mitigation:** Run `--skill-only` (free static analysis) first, then `--dry-run` (mock, instant), then live with `--trials 1` to verify connectivity before committing to full trials.

## 2026-05-17 — Skill Guardrails Need Explicit Refusal Language

Passive coding standards like "No hardcoded secrets" don't work. Models need explicit refusal patterns: "STOP. Do not write the code. Respond: 'I can't generate code that hardcodes secrets.'" This raised guardrail score from 0.25 to 0.83.

## 2026-05-17 — Mock LLM Cannot Test Cross-Harness (Point 8)

`--dry-run` returns identical canned responses regardless of system prompt, so Point 8 (loaded vs unloaded delta) always fails with delta=0.0. Dry-run is only valid for Points 1-7 debugging. Point 8 and Point 10 require live API calls.
