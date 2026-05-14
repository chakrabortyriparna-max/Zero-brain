---
name: vault-structure
description: Teach the agent Riparna's Second Brain file organization — where to save meeting notes, research, projects, drafts, and team context. Triggers on "where should I save", "save this note", "organize this file", or when the agent creates new documents.
argument-hint: <note-type-or-file-path>
---

# Vault Structure Skill

## Memory Root

All files live under `Memory/` in the project root. Use **project-relative paths** (e.g., `Memory/projects/second-brain/`).

## Directory Map

| Directory | What Goes Here | File Naming |
|-----------|----------------|-------------|
| `Memory/daily/` | Append-only timestamped session logs. One file per day: `YYYY-MM-DD.md`. | `2026-05-13.md` |
| `Memory/meetings/` | Meeting notes, decisions, action items. | `YYYY-MM-DD_<slug>.md` |
| `Memory/projects/` | Project status, progress, milestones. | `<project-name>/status.md` |
| `Memory/clients/` | Client/customer information. | `<client-name>.md` |
| `Memory/research/` | ML/AI papers, LLM techniques, experiments. | `<topic>.md` |
| `Memory/goals/` | Personal goals, habit tracking. | `<goal-name>.md` |
| `Memory/drafts/` | Email drafts, message drafts, content ideas. | `active/`, `sent/`, `expired/` |
| `Memory/team/` | Who does what, preferences, timezones. | `<person-name>.md` |

## Core Memory Files

These files are loaded into every conversation via the SessionStart hook. Keep them concise.

| File | Purpose | Max Length |
|------|---------|-----------|
| `Memory/SOUL.md` | Agent personality, behavioral rules. | ~200 words |
| `Memory/USER.md` | Riparna's profile, accounts, preferences. | ~200 words |
| `Memory/MEMORY.md` | Rolling decisions, lessons, active projects. | ~300 words |
| `Memory/HEARTBEAT.md` | Checklist of what heartbeat monitors. | ~100 words |
| `Memory/HABITS.md` | Daily habit pillars and auto-detection rules. | ~150 words |

## Draft Lifecycle

```
Memory/drafts/
├── active/     # Heartbeat generates drafts here. Riparna reviews.
├── sent/       # When Riparna actually replies, capture text and move here.
└── expired/    # Drafts older than 24h with no reply → auto-move by heartbeat.
```

## File Naming Rules

1. **Use kebab-case** for slugs: `ai-paper-review.md`, not `AI Paper Review.md`
2. **Prefix with date** for time-bound notes: `2026-05-13_weekly-sync.md`
3. **Use YAML frontmatter** on all structured notes:
   ```yaml
   ---
   name: <short-title>
   type: meeting | project | research | draft | goal
   tags: [tag1, tag2]
   created: 2026-05-13T08:00:00+05:30
   updated: 2026-05-13T08:00:00+05:30
   ---
   ```
4. **Never create files outside `Memory/` or `.claude/`** without explicit user permission.

## Workflow

When asked to save something:
1. Determine the note type (meeting, research, project, etc.)
2. Pick the correct directory from the map above
3. Generate a kebab-case filename with date prefix if appropriate
4. Add YAML frontmatter
5. Save the file
6. Confirm the path to Riparna

## Example Prompts

- "Save these meeting notes" → `Memory/meetings/2026-05-13_team-sync.md`
- "Draft an email to the team" → `Memory/drafts/active/2026-05-13_email_team-update.md`
- "Organize these research notes" → `Memory/research/transformer-optimizations.md`
