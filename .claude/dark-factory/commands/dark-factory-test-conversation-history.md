---
description: Comprehensive test scenario - verify conversation history persists across sessions.
argument-hint: (no arguments - reads port files from $ARTIFACTS_DIR)
---

# Dark Factory Comprehensive Test — Conversation History

**Workflow ID**: $WORKFLOW_ID

---

## Your Role

You are running a comprehensive E2E test for conversation history persistence.
Your job is to verify that chat messages persist and can be retrieved.

You have access to the Bash tool and the agent-browser skill.
Do NOT read any source code - you are a black-box tester.

---

## Running App URLs

- Frontend: `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.frontend-port 2>/dev/null || echo "")`
- Backend:  `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.backend-port 2>/dev/null || echo "")`

If no frontend port exists, test the backend history endpoint directly with curl.

---

## Steps

1. `agent-browser open <frontend URL>` (or use curl against backend).
2. Send a test message and note its content.
3. Refresh the page or re-open the app.
4. Verify the previously sent message appears in the conversation history.
5. Take a screenshot to `$ARTIFACTS_DIR/test-conversation-history.png`.
6. `agent-browser close`.
7. Write a markdown summary to `$ARTIFACTS_DIR/test-conversation-history.md` with:
   - Pass/fail verdict
   - What you observed
   - Screenshot path
   - Any errors

---

## Output Format

Return structured JSON:
- `status`: `"pass"` | `"fail"`
- `summary`: one-sentence description
- `evidence`: list of artifact paths
- `failure_reason`: null if passing, else concrete problem
