# Riparna's Second Brain — CLAUDE.md

Project-level instructions for `second-brain-starter`. Loaded automatically when working in this directory.

---

## Workflow Orchestration

Behavioral rules that apply within this project. Not suggestions — requirements.
**Full detailed rules:** `.claude/rules/workflow-orchestration.md`

### Output Style
- **Explanatory / Learning mode** is the default. Always explain the *why* behind changes — architecture rationale, trade-offs, risks, and how it fits the broader system. Not just the what.

### Process Discipline
- **Plan mode first** for any task with 3+ steps or architectural impact. Stop and re-plan immediately if context or constraints change mid-implementation.
- **Subagents by default** for parallel research, exploration, or multi-file analysis. One task per agent.
- **Verification is mandatory** before marking any task complete. Prove it with tests, logs, or demonstrated behavior. No "it should work" handoffs.

### Quality Discipline
- **Elegance check** for non-trivial changes: pause and ask "is there a more elegant way?" Skip for trivial/obvious fixes.
- **Autonomous debugging**: when given a bug report, fix it. Point at the error, trace root cause, resolve. Do not ask the user how.

### Learning & Task Management
- After any user correction, write the pattern to `tasks/lessons.md`. Create if it does not exist.
- Plan all work in `tasks/todo.md` with checkable items. Track progress, explain changes, document results.

### Core Principles
- Simplicity first. Minimal code, minimal blast radius.
- Root causes only. No temporary fixes.
- Never modify more files than the task requires.

---

## Project Overview

**Name:** Second Brain
**Owner:** Riparna Chakraborty
**Role:** Agentic AI Engineer
**Timezone:** IST (UTC+5:30)
**Proactivity Level:** Advisor — draft-only, never send or post without explicit approval

A persistent, proactive AI assistant built on Claude Code and the Claude Agent SDK. It connects to Gmail, Slack, GitHub, and Linear; organizes research notes; drafts email replies in Riparna's voice; summarizes Slack conversations; and assists with code-generation workflows.

---

## Project Structure

```
second-brain-starter/
├── Memory/                          # Obsidian vault — centre of everything
│   ├── SOUL.md                      # Agent personality, behavioral rules, tone
│   ├── USER.md                      # Profile, accounts, preferences, team
│   ├── MEMORY.md                    # Key decisions, lessons, active projects
│   ├── HEARTBEAT.md                 # Heartbeat monitoring checklist
│   ├── HABITS.md                    # Daily habit pillars (auto-detected + self-report)
│   ├── daily/                       # YYYY-MM-DD.md append-only timestamped logs
│   ├── meetings/                    # Meeting notes and decisions
│   ├── projects/                    # Project status and progress
│   ├── clients/                     # Client/customer information
│   ├── research/                    # Research notes (ML/AI papers, LLM techniques)
│   ├── goals/                       # Personal goals and habits
│   ├── drafts/                      # Content ideas, email drafts, message drafts
│   │   ├── active/                  # Heartbeat-generated drafts awaiting review
│   │   ├── sent/                    # Riparna's actual sent replies (voice-matching RAG)
│   │   └── expired/                 # Drafts older than 24h with no reply
│   └── team/                        # Team context (who does what, preferences, timezones)
│
├── .claude/
│   ├── settings.json                # Hook registrations (SessionStart, PreCompact, Stop)
│   ├── hooks/
│   │   ├── session-start-context.py # Injects SOUL + USER + MEMORY + daily logs into context
│   │   ├── pre-compact-flush.py     # Extracts decisions/facts before auto-compaction
│   │   └── session-end-flush.py     # Saves remaining context on session end
│   ├── scripts/
│   │   ├── db.py                    # SQLite/Postgres abstraction (chunks, hybrid search)
│   │   ├── embeddings.py            # FastEmbed wrapper (384-dim vectors)
│   │   ├── memory_index.py          # Incremental indexing CLI
│   │   ├── memory_search.py         # Hybrid RAG search CLI
│   │   ├── heartbeat.py             # Proactive monitoring (Phase 6)
│   │   ├── memory_reflect.py        # Daily reflection (Phase 6)
│   │   ├── sanitize.py              # External text sanitization (Phase 8)
│   │   ├── shared.py                # Command guardrails (Phase 8)
│   │   └── integrations/
│   │       ├── registry.py          # Tracks available integrations
│   │       ├── query.py             # Unified CLI: query.py gmail/slack/github
│   │       ├── integration_template.py # Copy-rename-fill for new integrations
│   │       ├── gmail_integration.py # Gmail module (OAuth2, draft-only)
│   │       ├── slack_integration.py # Slack module (Socket Mode)
│   │       └── github_integration.py # GitHub module (Fine-Grained PAT)
│   ├── skills/
│   │   ├── vault-structure/SKILL.md          # File organization guidance
│   │   ├── draft-ai-email/SKILL.md           # ML/AI email drafting in Riparna's voice
│   │   ├── summarize-slack/SKILL.md          # Slack channel summarization
│   │   ├── organize-research/SKILL.md        # Research note formatting
│   │   ├── codegen-assist/SKILL.md           # Code generation assistance
│   │   └── create-second-brain-prd/SKILL.md  # PRD generation skill
│   └── data/
│       ├── memory.db                # SQLite + sqlite-vec database
│       ├── chat.db                  # Chat session store (Phase 7)
│       └── state/heartbeat-state.json # Snapshot diffing state (Phase 6)
│
├── .env                             # API keys and tokens (git-ignored)
├── credentials.json                   # Gmail OAuth client secret (git-ignored)
└── .agent/plans/second-brain-prd.md  # Full 9-phase PRD
```

---

## Build Phases

| Phase | What | Status |
|-------|------|--------|
| 1 | Memory Layer (SOUL.md, USER.md, MEMORY.md, vault structure) | ✅ Built |
| 2 | Hooks (SessionStart, PreCompact, SessionEnd) | ✅ Built |
| 3 | Memory Search (FastEmbed + sqlite-vec + FTS5 hybrid RAG) | ✅ Built |
| 4 | Integrations (Gmail, Slack, GitHub — dataclass + auth + query + CLI) | ✅ Built |
| 5 | Skills (vault-structure, draft-ai-email, summarize-slack, organize-research, codegen-assist) | ✅ Built |
| 6 | Proactive Systems (heartbeat.py + memory_reflect.py + habits auto-detection) | ⏳ Not built |
| 7 | Chat Interface (Slack bot with Socket Mode + session store) | ⏳ Not built |
| 8 | Security Hardening (sanitize.py, guardrails, PreToolUse hook) | ⏳ Not built |
| 9 | Deployment (Windows Task Scheduler + DigitalOcean VPS sync) | ⏳ Not built |

---

## Skills

| Skill | Trigger Phrase | Purpose |
|-------|----------------|---------|
| `vault-structure` | "where should I save", "save this note" | File organization guidance |
| `draft-ai-email` | "draft email", "write reply" | ML/AI email drafting with RAG voice-matching on `drafts/sent/` |
| `summarize-slack` | "summarize slack" | Channel summarization + action items |
| `organize-research` | "organize these notes", "format this research" | Obsidian-formatted markdown with tags and links |
| `codegen-assist` | "write a script for", "generate code to" | Code snippets and agentic workflows |
| `create-second-brain-prd` | "create my second brain PRD" | Generates phased build plan from requirements template |
| `learn-unfamiliar-code` | "explain this code", "draw a diagram", "teach me", "spaced repetition" | HTML presentations, ASCII diagrams, flashcards, and explanatory output |

---

## Integrations

| Platform | Status | Auth | Key Files |
|----------|--------|------|-----------|
| Gmail | ✅ Built | OAuth2 Desktop App | `credentials.json`, `.env` (`token.json` auto-generated) |
| Slack | ✅ Built | Bot Token (`xoxb-`) + App Token (`xapp-`) | `.env` (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`) |
| GitHub | ✅ Built | Fine-Grained PAT | `.env` (`GITHUB_TOKEN`) |
| Linear | ⏳ Pending setup | API Key | `.env` (`LINEAR_API_KEY`) |

**Dependencies:** `pip install fastembed sqlite-vec google-api-python-client google-auth-oauthlib slack-bolt slack_sdk PyGithub python-dotenv`

---

## Hooks

| Hook | Event | Script | Behavior |
|------|-------|--------|----------|
| SessionStart | Conversation start | `session-start-context.py` | Reads SOUL.md + USER.md + MEMORY.md + last 3 daily logs → stdout injection |
| PreCompact | Before auto-compaction | `pre-compact-flush.py` | Parses JSONL transcript for decisions/lessons/action items → appends to today's daily log |
| Stop | Session end | `session-end-flush.py` | Saves remaining unsaved context to daily log |

---

## Memory Search

**Pipeline:** Incremental indexing → chunking (~400 tokens, 50-token overlap) → FastEmbed (`sentence-transformers/all-MiniLM-L6-v2`, 384-dim) → SQLite + sqlite-vec + FTS5.

**Hybrid search:** 70% vector similarity + 30% keyword via Reciprocal Rank Fusion.

**CLI:**
```bash
python .claude/scripts/memory_index.py   # Incremental re-index changed .md files
python .claude/scripts/memory_search.py "query" --top-k 10 --path-prefix drafts/sent
```

---

## Security Boundaries

- **Draft only.** No sending emails, posting Slack messages, or modifying files outside `Memory/` or `.claude/` without explicit permission.
- **No unilateral side-effects.** No commits, deploys, purchases, or deletions (`rm`, `del`, `Remove-Item`) blocked by guardrails.
- **External text sanitization.** All email/Slack/GitHub text runs through pattern detection → markdown escaping → XML trust boundaries before reaching the LLM.
- **API key isolation.** Python handles all auth; LLM never sees credentials.

---

## RTK (Rust Token Killer)

Always prefix commands with `rtk` for token-optimized output. Even in chains:

```bash
rtk git add . && rtk git commit -m "msg" && rtk git push
```

### Build & Compile
- `rtk cargo build`, `rtk cargo check`, `rtk cargo clippy`
- `rtk tsc`, `rtk lint`, `rtk prettier --check`, `rtk next build`

### Test
- `rtk cargo test`, `rtk vitest run`, `rtk playwright test`, `rtk test <cmd>`

### Git
- `rtk git status`, `rtk git log`, `rtk git diff`, `rtk git show`
- `rtk git add`, `rtk git commit`, `rtk git push`, `rtk git pull`
- `rtk git branch`, `rtk git fetch`, `rtk git stash`, `rtk git worktree`

### GitHub
- `rtk gh pr view`, `rtk gh pr checks`, `rtk gh run list`, `rtk gh issue list`, `rtk gh api`

### JS/TS Tooling
- `rtk pnpm list`, `rtk pnpm outdated`, `rtk pnpm install`
- `rtk npm run <script>`, `rtk npx <cmd>`, `rtk prisma`

### Files & Search
- `rtk ls <path>`, `rtk read <file>`, `rtk grep <pattern>`, `rtk find <pattern>`

### Analysis & Debug
- `rtk err <cmd>`, `rtk log <file>`, `rtk json <file>`, `rtk deps`, `rtk env`, `rtk summary <cmd>`, `rtk diff`

### Infrastructure
- `rtk docker ps`, `rtk docker images`, `rtk docker logs <c>`
- `rtk kubectl get`, `rtk kubectl logs`

### Network
- `rtk curl <url>`, `rtk wget <url>`

### Meta
- `rtk gain`, `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>`, `rtk init`
