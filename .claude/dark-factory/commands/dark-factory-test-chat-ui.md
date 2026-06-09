---
description: Comprehensive test scenario - verify the chat UI loads, accepts input, and displays messages.
argument-hint: (no arguments - reads port files from $ARTIFACTS_DIR)
---

# Dark Factory Comprehensive Test — Chat UI

**Workflow ID**: $WORKFLOW_ID

---

## Your Role

You are running a comprehensive E2E test for the chat UI.
Your job is to verify that users can open the chat interface, send a message,
and receive a response.

You have access to the Bash tool and the agent-browser skill.
Do NOT read any source code - you are a black-box tester.

---

## Running App URLs

- Frontend: `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.frontend-port 2>/dev/null || echo "")`
- Backend:  `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.backend-port 2>/dev/null || echo "")`

If no frontend port exists, test the backend API directly with curl.

---

## Steps

1. `agent-browser open <frontend URL>` (or backend if no frontend).
2. `agent-browser snapshot -i` to locate the chat input and send button.
3. Type a simple test message (e.g., "Hello") and click send.
4. Wait for a response to appear in the chat history.
5. Verify the response container contains text (not empty).
6. Take a screenshot to `$ARTIFACTS_DIR/test-chat-ui.png`.
7. `agent-browser close`.
8. Write a markdown summary to `$ARTIFACTS_DIR/test-chat-ui.md` with:
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
