---
name: summarize-slack
description: 'STRICT trigger list ONLY activates on "summarize slack", "what happened in #channel", or when heartbeat checks Slack. NEVER triggers on code generation, email drafting, learning requests, note organization, file organization, research formatting, or PRD creation. MUST NOT post messages to Slack.'
argument-hint: <channel-id-or-name> [hours-back]
---

## Negative Triggers

This skill MUST NOT trigger on:
- **Code generation** — "write a script", "generate code" → route to `codegen-assist`
- **Email drafting** — "draft email", "write reply" → route to `draft-ai-email`
- **Learning requests** — "explain this", "help me learn" → route to `learn-unfamiliar-code`
- **Note organization** — "organize these notes" → route to `organize-research`
- **File organization** — "where should I save" → route to `vault-structure`
- **PRD creation** — "create my second brain PRD" → route to `create-second-brain-prd`

## Directives

1. ALWAYS save summaries to `Memory/meetings/YYYY-MM-DD_slack_<channel>.md`.
2. NEVER post messages to Slack or @mention users without explicit `approved=True`.
3. MUST identify blockers, decisions, and action items in every summary.
4. ALWAYS filter noise — skip bot messages, reactions, and emoji-only posts.
5. MUST group insights by topic and surface key findings with timestamps.
6. ALWAYS preserve original message context when quoting user statements.
7. MUST output structured markdown matching the Output Format template exactly.
8. CHECK that every extracted signal has a timestamp and an owner.

# Summarize Slack

## Workflow

1. **Fetch history** — Use `slack_integration.get_history(channel_id, oldest_ts)` to get recent messages
2. **Filter noise** — Skip bot messages, reactions, emoji-only posts
3. **Extract signals** — Identify blockers, decisions, questions, action items
4. **Summarize** — Group by topic, surface key insights
5. **Save** — Write summary to `Memory/meetings/YYYY-MM-DD_slack_<channel>.md`

## Signal Extraction Rules

| Pattern | Label | Example |
|---------|-------|---------|
| "blocked by...", "can't proceed" | 🔴 Blocker | "Blocked by the API rate limit" |
| "decided to...", "we agreed" | ✅ Decision | "Decided to migrate to v2" |
| "action item:", "TODO:" | 📌 Action Item | "Action item: update the docs" |
| "question:", "does anyone know" | ❓ Question | "Question: what's the timeline?" |
| "LGTM", "approved" | 👍 Approval | "LGTM, ship it" |

## Output Format

```markdown
---
name: Slack Summary — #channel-name
type: meeting
source: slack
channel_id: C0B0...
date: 2026-05-13
hours_scanned: 24
---

## Summary

[2-3 sentence overview of what happened]

## 🔴 Blockers

- [Description and who is blocked]

## ✅ Decisions

- [Decision and context]

## 📌 Action Items

| Item | Owner | Status |
|------|-------|--------|
| [item] | @user | pending |

## ❓ Questions Raised

- [Question and who asked]

## 👍 Approvals

- [What was approved]
```

## CLI Helper

```bash
# Summarize last 24h in a channel
python .claude/scripts/integrations/query.py slack history C0B0HTS2EA0
```

## Save Location

Always save Slack summaries to:
- `Memory/meetings/YYYY-MM-DD_slack_<channel-name>.md`

If multiple summaries exist for the same day, append a counter: `_slack_channel-2.md`.

## Security Boundary

- ✅ Read Slack history, draft summaries
- ✅ Save summaries to vault
- ❌ NEVER post messages to Slack without explicit `approved=True`
- ❌ NEVER @mention users in drafted messages
