---
description: Comprehensive test scenario - verify video ingestion upload and processing pipeline.
argument-hint: (no arguments - reads port files from $ARTIFACTS_DIR)
---

# Dark Factory Comprehensive Test — Video Ingestion

**Workflow ID**: $WORKFLOW_ID

---

## Your Role

You are running a comprehensive E2E test for the video ingestion feature.
Your job is to verify that a video file can be uploaded and processed.

You have access to the Bash tool and the agent-browser skill.
Do NOT read any source code - you are a black-box tester.

---

## Running App URLs

- Frontend: `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.frontend-port 2>/dev/null || echo "")`
- Backend:  `http://127.0.0.1:$(cat $ARTIFACTS_DIR/.backend-port 2>/dev/null || echo "")`

If no frontend port exists, test the backend upload endpoint directly with curl.

---

## Steps

1. `agent-browser open <frontend URL>` (or use curl against backend).
2. Locate the video upload input or drag-and-drop zone.
3. Upload a small test video (use a test fixture if available, or simulate).
4. Wait for processing status to complete.
5. Verify the processed video appears in the library or returns a success status.
6. Take a screenshot to `$ARTIFACTS_DIR/test-video-ingestion.png`.
7. `agent-browser close`.
8. Write a markdown summary to `$ARTIFACTS_DIR/test-video-ingestion.md` with:
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
