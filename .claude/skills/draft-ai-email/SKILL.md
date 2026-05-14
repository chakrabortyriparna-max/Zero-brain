---
name: draft-ai-email
description: Draft professional ML/AI-related email replies in Riparna's voice. Uses RAG on Memory/drafts/sent/ for tone matching. Triggers on "draft email", "write reply", "draft response", or when heartbeat identifies an email needing response.
argument-hint: <email-subject-or-context>
---

# Draft AI Email

## Workflow

1. **Read context** — Original email content (passed as argument or fetched via Gmail integration)
2. **Voice-match via RAG** — Run `python .claude/scripts/memory_search.py "<email topic>" --path-prefix Memory/drafts/sent --top-k 5` to find similar past replies
3. **Draft reply** — Match Riparna's professional, technical tone
4. **Save** — Write to `Memory/drafts/active/YYYY-MM-DD_email_<slug>.md`
5. **Notify** — Tell Riparna the draft is ready for review. NEVER send directly.

## Voice Guidelines

- **Technical but approachable** — Reference ML/AI concepts naturally, not pedantically
- **Concise** — No fluff. One thought per paragraph. Bullet points for multiple items.
- **Action-oriented** — End with clear next steps or questions
- **Professional sign-off** — "Best, Riparna" or "Thanks, Riparna"
- **No hedging** — Use "I recommend" not "I think maybe we could consider"
- **Specific** — Reference concrete tools, papers, or techniques when relevant

## Output Format

Save as markdown with YAML frontmatter:

```yaml
---
type: email
source_id: <gmail_message_id>
recipient: <email>
subject: <subject>
context: <brief context>
created: 2026-05-13T08:00:00+05:30
status: active
---
```

## Example Draft Body

```markdown
Hi [Name],

Thanks for the detailed write-up on the fine-tuning approach.

A few thoughts:
- The LoRA adapter merge strategy looks solid. I'd suggest running eval on the
  merged weights before deployment to catch any rank-collapse issues.
- For the RLHF pipeline, consider switching from PPO to DPO — we've seen
  better convergence with smaller model sizes.
- Happy to review the final training script before you kick off the run.

Let me know if you want to sync on this tomorrow.

Best,
Riparna
```

## RAG Voice Matching

When drafting, search `Memory/drafts/sent/` for similar topics:

```bash
python .claude/scripts/memory_search.py "fine-tuning email" \
  --path-prefix Memory/drafts/sent --top-k 5
```

Use the top result's tone, vocabulary, and structure as a template. Do not copy verbatim.

## Security Boundary

- ✅ Draft emails and save to `Memory/drafts/active/`
- ❌ NEVER call `gmail_integration.create_draft()` without explicit user approval
- ❌ NEVER send emails
- ❌ NEVER auto-reply to emails

## GPS Quality Check

Before finalizing any email draft, optionally apply the GPS Framework (from `.claude/skills/gps-prompt-engineer/SKILL.md`) to the prompt that generated the draft:

1. **Gaslight:** If the stakes are high (investor, client, job), raise them in the drafting prompt. ("This email goes to a VC who gets 500 pitches a month.")
2. **Push Back:** After drafting, challenge the tone. ("If the recipient is having a bad day, does this email still land well?")
3. **Stress Test:** Run a Bias Sweep — check for confirmation bias (did I assume they agree?), survivorship bias (am I modeling replies only from people who said yes?).
