# 10-Point Skill Evaluation — Usage Guide

## Files Created

| File | Purpose |
|------|---------|
| `.claude/scripts/skill_eval_full.py` | Master 10-point evaluation script |
| `.claude/scripts/skill_eval_history.json` | Tracks pass-rate trends per skill |
| `.claude/scripts/skill_eval_failures.json` | Accumulates user-reported failures for regression testing |
| `.claude/hooks/pre-commit-skill-eval.py` | Git pre-commit hook (optional) |

## How to Evaluate a New Skill

### 1. Add prompt coverage (required for Points 3-10)

Edit `.claude/scripts/skill_eval_prompts.json` and add an entry for your skill:

```json
{
  "your-skill-name": {
    "categories": {
      "core": {
        "weight": 0.44,
        "threshold": 1.0,
        "cases": [
          {"id": "core-01", "prompt": "...", "expected_trigger": true, "deterministic_checks": ["check1", "check2"]}
        ]
      },
      "guardrails": {
        "weight": 0.25,
        "threshold": 1.0,
        "cases": [...]
      },
      "negative": {
        "weight": 0.12,
        "threshold": 0.0,
        "cases": [
          {"id": "neg-01", "prompt": "...", "expected_trigger": false, "deterministic_checks": ["no_code_generated"]}
        ]
      }
    }
  }
}
```

### 2. Run static-only checks (fast, no API calls)

```bash
python .claude/scripts/skill_eval_full.py your-skill-name --skill-only
```

This validates Points 1-2:
- **Point 1:** Skill description has explicit triggers and negative triggers
- **Point 2:** Uses directives ("ALWAYS", "NEVER", "MUST") not passive language

### 3. Run full 10-point evaluation

```bash
# With Groq (recommended for speed)
python .claude/scripts/skill_eval_full.py your-skill-name --groq --trials 3 --model llama-3.3-70b-versatile

# With Anthropic (highest quality, costs $)
python .claude/scripts/skill_eval_full.py your-skill-name --live --trials 3 --model claude-sonnet-4-6

# Dry-run (mock LLM, instant, for script debugging)
python .claude/scripts/skill_eval_full.py your-skill-name --dry-run --trials 2
```

### 4. Block commits on skill eval failure (optional)

Copy the hook into your git hooks:

```bash
cp .claude/hooks/pre-commit-skill-eval.py .git/hooks/pre-commit
# On Windows: copy .claude\hooks\pre-commit-skill-eval.py .git\hooks\pre-commit
```

Now any commit that modifies a `SKILL.md` will run the full 10-point eval. If it fails, the commit is blocked.

## The 10 Points

| # | Name | What it checks |
|---|------|----------------|
| 1 | **Skill Description Trigger Check** | Description has explicit positive/negative triggers, directive language |
| 2 | **Directives vs Information** | Imperative language ("ALWAYS use pathlib") dominates over passive suggestions |
| 3 | **Negative Tests** | Skill does NOT fire on non-trigger prompts (haiku, explain, etc.) |
| 4 | **Extend from Failures** | Previously failed cases are re-run; new failures are added to regression DB |
| 5 | **Grade Outcomes, Not Paths** | Deterministic checks verify end results, not exact code structure |
| 6 | **Isolate Each Run** | Trials with high variance flag potential context bleed |
| 7 | **Multiple Trials** | 3+ trials per case; reports min/avg/max distribution |
| 8 | **Test Across Harnesses** | Loaded skill must outperform generic system prompt significantly |
| 9 | **Graduate Evals** | Tracks pass-rate trends; transitions from capability → regression eval |
| 10 | **Detect Skill Retirement** | If generic prompt performs nearly as well, skill can be retired |

## Exit Codes

- `0` = all 10 points passed. Safe to commit/push.
- `1` = one or more points failed. Review the markdown report in `Memory/research/skill-eval-results/`.

## Cost Awareness

A full 10-point eval with 3 trials per case makes ~50-60 API calls. Estimated costs:
- Groq (`llama-3.3-70b-versatile`): ~$0.01-0.03 per run
- Anthropic (`claude-sonnet-4-6`): ~$0.50-1.50 per run

Run `--skill-only` first (free), then `--dry-run` to debug, then live.
