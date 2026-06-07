# Dark Factory Module

Autonomous AI software construction system for Second Brain. Manages GitHub issues and PRs across configured repositories via Archon workflows.

## Architecture

- **Commands** (`commands/`): Repo-agnostic AI agent command files (`.md`)
- **Workflows** (`workflows/`): YAML DAG definitions for Archon
- **Orchestrator** (`orchestrator.py`): Python polling loop that reads `decision-mapping.json`, polls GitHub, and dispatches workflows
- **Templates** (`templates/`): Governance file templates (`FACTORY_RULES.md`, `MISSION.md`, `CLAUDE.md`)

## Workflows

| Workflow | Purpose |
|----------|---------|
| `dark-factory-triage` | Label untriaged issues as accepted / rejected / needs-human |
| `dark-factory-fix-github-issue` | Implement fixes for accepted issues |
| `dark-factory-validate-pr` | Multi-agent PR validation (behavioral, security, code review) |
| `dark-factory-comprehensive-test` | Weekly full-suite regression testing |

## Usage

### Dry Run (no side effects)

```bash
python .claude/dark-factory/orchestrator.py --dry-run --once
```

### Test Single Repo

```bash
python .claude/dark-factory/orchestrator.py --test-repo second-brain-starter --once
```

### Continuous Mode (via Task Scheduler)

Configure Windows Task Scheduler to run every 30 minutes:

```powershell
python .claude/dark-factory/orchestrator.py --once
```

## Configuration

Set via environment variables (prefix `DARK_FACTORY_`) or defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `DARK_FACTORY_ARCHON_PATH` | `archon` | Path to Archon CLI |
| `DARK_FACTORY_POLL_INTERVAL_MINUTES` | `30` | Poll interval |
| `DARK_FACTORY_MAX_ISSUES_PER_RUN` | `3` | Max issues to process per cycle |
| `DARK_FACTORY_MAX_PRS_PER_RUN` | `2` | Max PRs to validate per cycle |
| `DARK_FACTORY_DRY_RUN` | `false` | Log only, no dispatch |

Also requires:
- `GITHUB_TOKEN` — GitHub PAT with repo scope
- `OPENROUTER_API_KEY` — For Archon workflow LLM calls

## Governance

Each target repo must have these files at its root:
- `FACTORY_RULES.md` — Factory operational rules
- `MISSION.md` — Product scope and boundaries
- `CLAUDE.md` — Code conventions

Scaffold them with:

```bash
python .claude/dark-factory/orchestrator.py --scaffold-governance <repo-tag>
```

## Integration with Second Brain

- **Decision Mapping**: Reads `.claude/data/decision-mapping.json` for repo registry
- **Heartbeat**: `.claude/scripts/heartbeat.py` checks orchestrator health
- **State DB**: Uses `.claude/scripts/db.py` for run history
