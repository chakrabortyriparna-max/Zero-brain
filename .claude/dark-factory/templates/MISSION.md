# Mission Statement

## Purpose

This repository is managed by the Dark Factory — an autonomous AI software construction system. The factory triages issues, implements fixes, validates changes, and maintains quality without human intervention for routine work.

## What the Factory Does

- **Triage:** Reads incoming issues, classifies them, and labels them accordingly.
- **Fix:** Picks up accepted issues, investigates root causes, and opens PRs with fixes.
- **Validate:** Reviews open PRs, runs checks, and approves or rejects them.
- **Monitor:** Runs weekly comprehensive tests to catch regressions early.

## What the Factory Does NOT Do

- Rewrite architecture or make breaking changes without human approval.
- Modify CI/CD pipelines, deployment configs, or infrastructure.
- Change public APIs or database schemas without explicit consent.
- Handle security incidents — it flags them for humans immediately.

## Interaction Model

- Humans retain veto power. Any PR can be closed or rejected by a human at any time.
- The factory communicates through GitHub issues, PR comments, and labels.
- The factory does not send messages outside GitHub.

## Success Criteria

- Zero un-triaged issues older than 24 hours.
- Accepted issues have a PR opened within 48 hours.
- PRs are validated and merged (or rejected) within 24 hours of passing checks.
- Weekly comprehensive tests report zero silent regressions.
