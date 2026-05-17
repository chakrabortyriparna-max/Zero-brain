---
name: learn-unfamiliar-code
description: Generate visual HTML presentations, ASCII diagrams, and spaced-repetition drills to help Riparna understand unfamiliar code, protocols, and codebases. Triggers on "explain this code", "help me learn", "draw a diagram", "teach me", "spaced repetition", or when asked to explain the why behind changes.
argument-hint: <topic-or-code-to-learn>
---

# Learn Unfamiliar Code

## Modes

### Mode 1: Explanatory Output (Default)

When writing or modifying code, always explain the **why** behind the change — not just the what.

- **Architecture rationale**: Why this pattern over alternatives?
- **Trade-offs**: What was sacrificed for this choice?
- **Context**: How does this fit into the broader system?
- **Risks**: What could break or degrade?

### Mode 2: Visual HTML Presentation

Generate a self-contained HTML slide deck explaining unfamiliar code.

**Workflow:**
1. Read the target code/files
2. Identify key concepts, data flow, and decision points
3. Generate `Memory/research/learning/<topic>-slides.html`

**Slide structure (per concept):**
- Title + one-line summary
- ASCII or simplified diagram
- Code snippet (max 15 lines)
- "Why this matters" bullet
- "Common pitfall" warning

**Style:**
- Dark theme, monospace code blocks
- Navigation arrows between slides
- Collapsible "Deep Dive" sections

**Example trigger:** "Create a presentation explaining the heartbeat architecture"

### Mode 3: ASCII Diagram

Draw ASCII art diagrams for protocols, codebases, or data flows.

**Use cases:**
- System architecture overview
- Request/response lifecycle
- State machine transitions
- Database schema relationships
- Hook execution flow

**Rules:**
- Use box-drawing characters (`┌─┐│└┘`) for clean edges
- Label every arrow with action/data name
- Keep width ≤80 columns
- Include a legend if symbols are non-obvious

**Save to:** `Memory/research/diagrams/<topic>.txt`

### Mode 4: Spaced-Repetition Drill

Interactive learning loop: Riparna explains, Claude probes gaps, stores result.

**Workflow:**
1. Riparna states a topic or pastes code she is trying to understand
2. Claude asks 3–5 targeted follow-up questions designed to surface misunderstandings
3. Riparna answers
4. Claude identifies gaps and provides concise corrections + one analogy
5. Store the Q&A pair to `Memory/research/flashcards/<topic>.md` in this format:

```markdown
---
topic: <topic>
created: <YYYY-MM-DD>
type: flashcard
---

## Question
<question that exposed a gap>

## Answer
<corrected understanding>

## Analogy
<one-sentence analogy for memory anchoring>

## Tags
#learning #<domain>
```

**Question design principles:**
- Ask "what happens if...?" to test edge cases
- Ask "why not...?" to test alternative knowledge
- Ask "how does X relate to Y?" to test system thinking
- Avoid factual recall; focus on reasoning gaps

## Save Locations

| Output | Location |
|--------|----------|
| HTML slides | `Memory/research/learning/<topic>-slides.html` |
| ASCII diagrams | `Memory/research/diagrams/<topic>.txt` |
| Flashcards | `Memory/research/flashcards/<topic>.md` |

## After Generating

1. Show a preview of the first slide / diagram / flashcard
2. Remind: "Run `python .claude/scripts/memory_index.py` to make this searchable"
3. Offer to walk through the material live
