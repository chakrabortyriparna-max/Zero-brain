---
description: Comprehensive test scenario 1 - verify the app starts and the health endpoint returns 200.
argument-hint: (no arguments - reads port files from $ARTIFACTS_DIR)
---

# Dark Factory Comprehensive Test — Health Check

**Workflow ID**: $WORKFLOW_ID

---

## Your Role

You are running scenario 1 of the Dark Factory comprehensive weekly test.
Your only job is to verify that the application starts and its health
endpoint responds with HTTP 200.

You have access to the Bash tool and the agent-browser skill (if a frontend
is available). Do NOT read any source code - you are a black-box tester.

---

## Running App URLs

Read these from artifact files:
- Frontend: `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.frontend-port)`
- Backend:  `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.backend-port)`

---

## Steps

1. `curl -sf "$BACKEND_URL/health" > /dev/null` (or whatever health path is
   conventional for the repo, falling back to `GET /` if `/health` 404s).
2. If the backend does NOT return HTTP 200, that is a FAIL.
3. If a frontend port file exists, `agent-browser open <frontend URL>`.
4. `agent-browser snapshot -i` to see interactive elements.
5. Verify at least one interactive element loads (e.g., a button, link, or
   input). If the page is completely blank or shows a fatal error, that is a
   FAIL.
6. Take a screenshot to `$ARTIFACTS_DIR/test-health-check.png`.
7. `agent-browser close`.
8. Write a markdown summary to `$ARTIFACTS_DIR/test-health-check.md` with:
   - Pass/fail verdict
   - What you observed
   - Screenshot path
   - Any console errors or visible UI errors

---

## Output Format

Return structured JSON:
- `status`: `"pass"` | `"fail"`
- `summary`: one-sentence human description
- `evidence`: list of artifact paths (screenshot, markdown, logs)
- `failure_reason`: null if passing, else concrete problem description
