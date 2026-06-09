# Tasks — Second Brain

## Completed

### 10-Point Skill Evaluation Framework
- [x] Build `skill_eval_full.py` covering all 10 best practices
- [x] Implement Point 1: Skill description trigger check (static analysis)
- [x] Implement Point 2: Directives vs information (static analysis)
- [x] Implement Points 3-7: Prompt-based eval with negative tests, failure extension, isolation, multiple trials
- [x] Implement Point 8: Cross-harness comparison (loaded vs unloaded)
- [x] Implement Point 9: Graduation tracking (history DB)
- [x] Implement Point 10: Skill retirement detection
- [x] Create pre-commit hook script
- [x] Write usage guide
- [ ] Run live Groq evaluation for codegen-assist (blocked: Groq rate limit 99,154/100,000 TPD)

## Backlog

- [ ] Add prompt coverage for remaining 7 skills in `skill_eval_prompts.json`
- [ ] Run 10-point eval on all 8 skills once Groq rate limit resets
- [ ] Integrate pre-commit hook into git workflow

## Blockers

- Groq TPD rate limit reached. Retry after 2026-05-17 13:00 IST (~20 min from now).
