---
description: Classify a GitHub issue into bug/feature/enhancement/refactor/chore/documentation for the Dark Factory fix workflow.
argument-hint: (reads $fetch-issue.output)
---

You are an issue classifier. Analyze the GitHub issue below and determine its type.

## Issue Content

$fetch-issue.output

## Classification Rules

| Type | Indicators |
|------|------------|
| bug | "broken", "error", "crash", "doesn't work", stack traces, regression |
| feature | "add", "new", "support", "would be nice", net-new capability |
| enhancement | "improve", "better", "update existing", "extend", incremental improvement |
| refactor | "clean up", "simplify", "reorganize", "restructure" |
| chore | "update deps", "upgrade", "maintenance", "CI/CD" |
| documentation | "docs", "readme", "clarify", "examples" |

Provide reasoning for your classification.
