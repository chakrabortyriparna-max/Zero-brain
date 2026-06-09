---
description: Comprehensive test scenario - verify RAG query returns relevant grounded responses.
argument-hint: (no arguments - reads port files from $ARTIFACTS_DIR)
---

# Dark Factory Comprehensive Test — RAG Response

**Workflow ID**: $WORKFLOW_ID

---

## Your Role

You are running a comprehensive E2E test for the RAG (Retrieval-Augmented Generation) feature.
Your job is to verify that queries return relevant, grounded responses.

You have access to the Bash tool and the agent-browser skill.
Do NOT read any source code - you are a black-box tester.

---

## Running App URLs

- Frontend: `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.frontend-port 2>/dev/null || echo "")`
- Backend:  `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.backend-port 2>/dev/null || echo "")`

If no frontend port exists, test the backend RAG endpoint directly with curl.

---

## Steps

1. `agent-browser open <frontend URL>` (or use curl against backend RAG endpoint).
2. Locate the search or query input.
3. Submit a query that should trigger retrieval (e.g., a question about indexed content).
4. Wait for the response.
5. Verify the response contains relevant information and is not a generic fallback.
6. Take a screenshot to `$ARTIFACTS_DIR/test-rag-response.png`.
7. `agent-browser close`.
8. Write a markdown summary to `$ARTIFACTS_DIR/test-rag-response.md` with:
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
