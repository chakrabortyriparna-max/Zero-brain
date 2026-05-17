# Session Capture Protocol

Lightweight in-convention rules that make session insight extraction reliable.

---

## Assistant Behavior

When a significant decision, action item, or lesson crystallizes during conversation, explicitly surface it using tagged syntax so the hook regex captures it automatically:

- **Decision:** When a choice is finalized.  
  Example: `**Decision:** We will rewrite shared_extract.py to traverse message.content blocks.`

- **Action Item:** When the user or assistant needs to do something later.  
  Example: `**Action Item:** Riparna to test the flush script on tomorrow's session.`

- **Lesson:** When something important is learned or a pattern is recognized.  
  Example: `**Lesson:** Claude Code transcript entries nest content under message.content, not at the root.`

- **Key Fact:** When a concrete fact or constraint is established.  
  Example: `**Key Fact:** The PreCompact hook fires before auto-compaction automatically.`

These tags are extracted by `shared_extract.py` and surfaced in the daily log under the correct category.

## User Triggers

When the user says any of the following, trigger an explicit session flush:

- "flush session"
- "wrap up"
- "summarize this session"
- "capture this"
- "log this"

Trigger by running:
```bash
python .claude/scripts/flush_session.py
```

With `--preview` first if the user seems unsure:
```bash
python .claude/scripts/flush_session.py --preview
```

## End-of-Session Protocol

Before the session ends (either by auto-compaction or explicit stop), the PreCompact and SessionEnd hooks will automatically extract tagged items and structural changes. The explicit flush CLI is available anytime the user wants control or visibility.
