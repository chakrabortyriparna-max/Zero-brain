---
name: Prompt Library
description: Running catalog of prompts optimized via the GPS Framework. Updated by the gps-prompt-engineer skill after each session.
type: reference
created: 2026-05-13
updated: 2026-05-13
---

# Prompt Library

A living document tracking prompts tested and optimized via the GPS Framework (Gaslight, Push Back, Stress Test).

## Format

| Name | Use Case | Original | Optimized | GPS Stage | Model | Notes |
|------|----------|----------|-----------|-----------|-------|-------|

## Entries

### 2026-05-14 — Database Integrity Check

| Field | Value |
|-------|-------|
| **Name** | Database Integrity + Resilience Audit |
| **Use Case** | Verify SQLite database health after corruption recovery |
| **Original** | Could you confirm that the database has been reviewed properly and that there are no other conflicts within the GPS framework and the indexing? All nine files are now searchable. If this is not the case in the future, please inform me. |
| **Optimized** | Before I trust this database for production use, run a full resilience audit. Check `PRAGMA integrity_check`, verify rowcount alignment across `chunks`, `chunks_vec`, and `file_hashes`, and tell me the 3 silent failure modes an SRE would watch for. If anything looks off, flag it with `[DB ALERT]` in today's daily log. Also: what likely caused the previous corruption, and what prevents it recurring? |
| **GPS Stage** | G (production stakes) / P (SRE silent failure modes) / S (gap check + bias sweep + stakes injection) |
| **Model** | Claude (gps-prompt-engineer skill) |
| **Notes** | Key upgrade: shifted from "confirm it's fine" to "what would make it fail silently?" Added rowcount alignment check across three stores and proactive monitoring recommendation. |

**Key Takeaways:**
- "Confirm it's fine" is a trap. Ask "what would make it fail silently?" instead.
- Rowcount alignment across `chunks`, `vec`, `fts` catches desync faster than `integrity_check` alone.
- Previous corruption root cause matters more than current clean state.

