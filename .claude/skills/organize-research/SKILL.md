---
name: organize-research
description: Take raw research notes and organize them into Obsidian-formatted markdown with tags, links, categorization, and references. Triggers on "organize these notes", "format this research", or when saving ML/AI paper notes.
argument-hint: <raw-notes-or-file-path>
---

# Organize Research

## Workflow

1. **Read raw notes** — From argument, file path, or pasted content
2. **Identify the topic** — Paper title, technique name, tool, concept
3. **Categorize** — Pick the right `Memory/research/` subcategory
4. **Format** — Convert to Obsidian markdown with YAML frontmatter, tags, wikilinks
5. **Cross-link** — Add `[[...]]` wikilinks to related notes (search memory_index first)
6. **Save** — Write to `Memory/research/<category>/<slug>.md`

## Research Directory Structure

```
Memory/research/
├── papers/           # Academic papers with summaries
├── techniques/       # ML/AI techniques (RAG, LoRA, RLHF, etc.)
├── tools/            # Tools and frameworks (Claude SDK, LangChain, etc.)
├── experiments/      # Personal experiments and results
└── reading-list/     # Queue of papers/articles to read
```

## YAML Frontmatter Template

```yaml
---
name: <Paper Title or Topic>
type: research
subtype: paper | technique | tool | experiment
authors: [Author1, Author2]
url: <paper-url-or-arxiv>
tags: [ml, llm, rag, fine-tuning]
status: unread | reading | summarized | digested
created: 2026-05-13T08:00:00+05:30
updated: 2026-05-13T08:00:00+05:30
---
```

## Obsidian Formatting Rules

1. **Wikilinks** — Link to related notes: `[[LoRA Fine-Tuning]]`, `[[Claude Agent SDK]]`
2. **Tags** — Inline tags for discoverability: `#ml #rag #technique`
3. **Headers** — Use H2 (`##`) for sections, H3 (`###`) for subsections
4. **Callouts** — Use Obsidian callout syntax for key insights:
   ```markdown
   > [!important] Key Insight
   > The hybrid approach (0.7 vector + 0.3 keyword) outperforms pure semantic search.
   ```
5. **References** — Link all external sources at the bottom:
   ```markdown
   ## References
   - [Paper Title](arxiv-url)
   - [[Related Internal Note]]
   ```

## Example Output

```markdown
---
name: "QLoRA: Efficient Finetuning of Quantized LLMs"
type: research
subtype: paper
authors: [Tim Dettmers, Artidoro Pagnoni, et al.]
url: https://arxiv.org/abs/2305.14314
tags: [llm, fine-tuning, quantization, lora]
status: digested
created: 2026-05-13T08:00:00+05:30
updated: 2026-05-13T08:00:00+05:30
---

# QLoRA: Efficient Finetuning of Quantized LLMs

## TL;DR

QLoRA enables fine-tuning of 65B parameter models on a single 48GB GPU by
quantizing the base model to 4-bit and using LoRA adapters.

## Key Contributions

1. **4-bit NormalFloat (NF4)** — Optimal quantization for normally distributed weights
2. **Double Quantization** — Quantizes the quantization constants for additional memory savings
3. **Paged Optimizers** — Uses NVIDIA unified memory to avoid OOM during gradient checkpointing

> [!important] Practical Impact
> Can fine-tune a 65B model on a single consumer GPU (RTX 4090 24GB).

## Related Notes

- [[LoRA Fine-Tuning]] — Overview of the LoRA technique
- [[Model Quantization]] — General quantization strategies
- [[GPU Memory Management]] — Tips for fitting large models

## References

- [QLoRA Paper](https://arxiv.org/abs/2305.14314)
- [[LoRA Fine-Tuning]]
```

## Cross-Linking Strategy

Before saving a new research note:
1. Run `python .claude/scripts/memory_search.py "<topic>" --path-prefix Memory/research --top-k 5`
2. Add `[[...]]` wikilinks to the most relevant 2-3 existing notes
3. If no relevant notes exist, skip linking — the note will be discovered on future searches

## Save Rules

- **New papers** → `Memory/research/papers/<slug>.md`
- **Technique deep-dives** → `Memory/research/techniques/<slug>.md`
- **Tool evaluations** → `Memory/research/tools/<slug>.md`
- **Experiment logs** → `Memory/research/experiments/YYYY-MM-DD_<slug>.md`

## GPS Quality Check

Before finalizing any organized research note, optionally apply the GPS Framework (from `.claude/skills/gps-prompt-engineer/SKILL.md`):

1. **Gaslight:** If the research is for a high-stakes decision (product, investment, career), raise the stakes in the structuring prompt. ("This research determines whether we pivot the product. Structure it like you're presenting to a board.")
2. **Push Back:** Challenge the framing. ("What would a skeptic say is missing from this summary?")
3. **Stress Test:**
   - **Gap Check:** Did I capture the methodology, sample size, limitations?
   - **Bias Sweep:** Check for confirmation bias — did I cherry-pick papers that support my hypothesis?
   - **Stakes Injection:** "If I act on this research and the paper is wrong, what's the cost?"
