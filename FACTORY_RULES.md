<<<<<<< HEAD
# Dark Factory Rules

## §1 — Triage Verdicts
Every issue gets one of two verdicts:
- **ACCEPT**: Issue is unambiguous, in-scope, and safe for autonomous implementation
- **REJECT**: Issue is ambiguous, out-of-scope, requires human judgment, or unsafe

## §2 — Rate Limiting
Non-owner accounts are capped at 3 issues per UTC calendar day.
Excess issues are labeled `factory:rate-limited` and re-evaluated after UTC midnight.

## §3 — Holdout Principle
The validator must NEVER see implementation artifacts or coder rationale.
Validation tests the OUTCOME against the CONTRACT.

## §4 — Governance Poisoning
Any PR that modifies MISSION.md, FACTORY_RULES.md, or CLAUDE.md is automatically REJECT.
These files must only change via direct human commits to main.

## §5 — Weekly Regression
Every Monday at 06:00 UTC, the comprehensive test workflow runs against main.
Failures are auto-filed as issues and triaged.
=======
# Dark Factory — Governance Rules

## Scope & Boundaries

1. **Read-only on main.** The factory never commits directly to `main`. All changes go through PRs.
2. **Holdout validation.** Validators must not see `investigation.md`, `plan.md`, or any implementation artifacts from the fix workflow.
3. **No external side-effects.** The factory does not send emails, post Slack messages, or make purchases.
4. **Human escalation.** If a fix fails validation twice, stop and flag for human review.

## Triage Rules

- Issues are classified as `accepted`, `rejected`, or `needs-info`.
- Accepted issues must have a clear reproduction step or error message.
- Rejected issues are closed with a polite explanation.
- Needs-info issues are labeled and left open for 7 days before auto-rejection.

## Implementation Rules

- One issue per PR. No batching unrelated fixes.
- All changes must pass static checks (lint, type-check) before PR creation.
- Tests must be added or updated for bug fixes.
- The PR description must reference the issue and summarize the fix.

## Validation Rules

- Static checks: run project-appropriate linters and type-checkers.
- Unit tests: run the project's test suite.
- Behavioral validation: verify the fix actually resolves the reported issue.
- Security check: scan for secrets, injections, and dependency vulnerabilities.
- E2E (if app exists): verify the app starts and health endpoint responds.

## Quality Gates

A PR is approved only when ALL of the following are true:
1. Static checks pass.
2. Unit tests pass (or the project has no tests — log this).
3. Behavioral validation passes.
4. Security check passes.
5. PR diff is within scope (no unrelated changes).

## Escalation

- If any gate fails twice on the same issue, stop and label `factory:human-review`.
- If the factory files a duplicate issue, deduplicate and reference the original.
- If the factory detects an infra failure (missing deps, broken CI), label `factory:infra-failure`.
>>>>>>> diffblue-agents-tests
