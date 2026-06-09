---
name: MEMORY
description: Rolling document of key decisions, lessons learned, active projects, and important facts.
updated: 2026-05-12
---

# MEMORY — Active Context & Long-Term Knowledge

## Key Decisions

*(Populated over time by the daily reflection process and explicit session notes.)*

**Decision:** We will use SQLite + sqlite-vec for local memory, with a Cognee-based graph-vector hybrid layer (FalkorDB + Supabase) for advanced multi-hop reasoning. Migration path: SQLite first, hybrid layer added once Cognee stabilizes.

**Decision:** All external integrations (Gmail, Slack, GitHub) remain draft-only. The agent cannot send messages or post without explicit human approval. This is non-negotiable.

**Decision:** Archon workflows for the Second Brain live in `Archon/.archon/workflows/second-brain-*.yaml`. Supporting Python scripts live in `.claude/scripts/decision_*.py`. New workflows must be validated with `bun run cli validate workflows` before merging.

**Decision:** This repository will not use GitHub Actions for automated testing, code review, or release management. All CI/CD pipelines must be handled through external orchestration tools or manual processes only.

## Lessons Learned

*(Populated over time. One-line summaries with dates.)*

- [GPS Prompt Engineering](Memory/research/prompt-engineering-gps-framework.md) — Active prompt optimization skill and reference library

## Active Projects

| Project | Status | Location | Last Updated |
|---------|--------|----------|--------------|
| Second Brain Build | In Progress | `Memory/projects/second-brain/` | 2026-05-12 |

## Important Facts

- **Build Start Date:** 2026-05-12
- **Architecture:** Claude Code + Claude Agent SDK, local SQLite + DigitalOcean VPS.
- **Security Stance:** Advisor — draft-only, no unilateral sends/posts.

## Contacts & Relationships

*(Populated in `Memory/team/` and mirrored here for quick reference.)*

## Expired / Archived Items

*(Moved here by daily reflection when no longer relevant. Pruned with confirmation.)*
