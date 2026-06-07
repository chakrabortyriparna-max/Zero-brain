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
