---
name: HEARTBEAT
description: Checklist of what the proactive heartbeat monitors. Configured in Phase 6.
updated: 2026-05-12
---

# HEARTBEAT — Monitoring Checklist

## Sources to Poll (Every 30 Minutes, 8 AM – 10 PM IST)

- [ ] **Gmail** — Unread messages, threads needing reply.
- [ ] **Slack** — New messages since last check, @mentions, DMs.
- [ ] **GitHub** — New notifications, issues, PRs requiring review.

## Actions to Take When Changes Detected

1. **Draft email replies** for unread threads → save to `Memory/drafts/active/`
2. **Summarize Slack activity** and flag action items.
3. **Flag GitHub notifications** needing attention with context.
4. **Update state file** `.claude/data/state/heartbeat-state.json` for snapshot diffing.

## Advisor Boundaries

- ✅ Draft emails and messages for Riparna's review.
- ✅ Send Windows Toast notifications for urgent items.
- ✅ Track habit progress and suggest next steps.
- ❌ Never send emails or Slack messages directly.
- ❌ Never auto-complete tasks or make commits.
- ❌ Never post without explicit approval.

## Notification Channels

- **Primary:** Windows Toast notifications for urgent items.
- **Secondary:** Drafts saved to `Memory/drafts/active/` with YAML frontmatter.
- **Tertiary:** Daily log append for non-urgent summaries.

## Habits Monitoring

- Auto-detect `Main Project` pillar via GitHub commits.
- Auto-detect `Community` pillar via Slack public channel activity.
- `Relationships`, `Health`, `Side Project` — self-reporting required.
