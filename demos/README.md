# Zero Brain — Demos

This directory contains public-facing demos and templates. Nothing in this folder contains real credentials or private data.

## Files

| File | Purpose |
|------|---------|
| `placeholder.env` | Template showing where API keys go. Copy to project root as `.env` and fill with real values. |
| `date_function_demo.py` | Shows IST timezone handling without exposing real data. |

## Actionbook Setup (Browser Automation)

Actionbook is the browser automation tool used for demo video recording.

### Prerequisites

1. **Chrome Extension**: Install Actionbook from the Chrome Web Store.
2. **CLI**: Install the Actionbook CLI locally:
   ```bash
   # See Actionbook docs for exact install command
   npm install -g @actionbook/cli
   ```
3. **MCP Connection**: In your Claude desktop app, add the Actionbook MCP server:
   - Name: `actionbook`
   - URL: `https://edge.actionbook.dev/mcp`
   - Click Connect → approve in the Chrome extension tab.

### Usage in Workflows

The GitHub Actions workflow (`.github/workflows/demo-release.yml`) has a placeholder step for Actionbook. Because Actionbook requires a live browser and human approval, it cannot run headlessly in CI.

**Recommended workflow:**
1. Develop locally with Actionbook connected to Claude.
2. When ready, run the demo script and record manually:
   ```bash
   python demos/date_function_demo.py
   # Use Actionbook to record the terminal/output
   ```
3. Attach the video to the `demo-latest` GitHub Release manually, or use `gh release upload`:
   ```bash
   gh release upload demo-latest my-demo-video.mp4 --clobber
   ```

### Security Note

Actionbook uses your existing browser cookies. You never share passwords with the AI or Actionbook servers. Review the browser tab group (blue "Actionbook" tabs) to monitor what the agent clicks in real time.
