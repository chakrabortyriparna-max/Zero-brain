# Plan Mode Review — Code & Architecture Review Rules

These rules apply when reviewing plans, architecture, or codebases.
They do NOT override autonomous bug fixing (workflow-orchestration.md) or outcomes-first
reporting (operational-discipline.md Communication) during normal execution.

Loaded on demand by Claude CLI. Triggered via `/review-plan` command.

---

## Engineering Preferences

Use these to guide all recommendations during reviews:

- **DRY is important** — flag repetition aggressively
- **Well-tested code is non-negotiable** — rather too many tests than too few
- **"Engineered enough"** — not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unnecessary complexity)
- **Handle more edge cases, not fewer** — thoughtfulness > speed
- **Explicit over clever** — readable code wins over terse/smart code

---

## Review Checklists

### 1. Architecture Review
Evaluate:
- Overall system design and component boundaries
- Dependency graph and coupling concerns
- Data flow patterns and potential bottlenecks
- Scaling characteristics and single points of failure
- Security architecture (auth, data access, API boundaries)

### 2. Code Quality Review
Evaluate:
- Code organization and module structure
- DRY violations — be aggressive here
- Error handling patterns and missing edge cases (call these out explicitly)
- Technical debt hotspots
- Areas that are over-engineered or under-engineered relative to engineering preferences above

### 3. Test Review
Evaluate:
- Test coverage gaps (unit, integration, e2e)
- Test quality and assertion strength
- Missing edge case coverage — be thorough
- Untested failure modes and error paths

### 4. Performance Review
Evaluate:
- N+1 queries and database access patterns
- Memory-usage concerns
- Caching opportunities
- Slow or high-complexity code paths

---

## Issue Reporting Format

For every specific issue (bug, smell, design concern, or risk):

1. **Describe the problem** concretely, with file and line references
2. **Present 2–3 options**, including "do nothing" where reasonable
3. **For each option**, specify: implementation effort, risk, impact on other code, maintenance burden
4. **Give your recommended option** and why, mapped to engineering preferences above
5. **Ask whether I agree** or want a different direction before proceeding

### Formatting Rules
- **NUMBER** issues (1, 2, 3...)
- **LETTER** options within each issue (A, B, C...)
- Recommended option is always listed **first** (option A)
- Label clearly: e.g., "Issue #2, Option B" so the user can respond unambiguously

---

## Interaction Pattern

After each review section (Architecture → Code Quality → Tests → Performance):
- Output findings with the structured issue format above
- **Pause and ask for feedback** before moving to the next section
- Maximum 4 issues per section to keep reviews focused
