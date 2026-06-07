---
description: Extract the GitHub issue number from the workflow arguments for Dark Factory fix workflow.
argument-hint: (reads $ARGUMENTS — the workflow invocation message)
---

Find the GitHub issue number for this request.

Request: $ARGUMENTS

Rules:
- If the message contains an explicit issue number (e.g., "#26", "issue 26", "26"), extract that number.
- If the message is ambiguous (e.g., "fix the CORS bug"), use `gh issue list` to search for matching open issues with `factory:accepted` label and pick the best match.

CRITICAL: Your final output must be ONLY the bare number with no quotes, no markdown, no explanation. Example correct output: 26
