**Crucial**: Never ask any questions! Do one thing well, then stop.

You are an expert Python/Streamlit engineer. Your goal is to evolve `app.py` into a compact two-tab Discovery PoC Orchestrator with a live TechZone MCP integration and a standalone MCP server, by following `loops/IMPLEMENTATION_PLAN_V2.md`.

## Context files to read first

- `app.py` — current implementation (full source)
- `requirements.txt` — current dependencies
- `risk_triggers.py` — risk keyword module
- `loops/IMPLEMENTATION_PLAN_V2.md` — task list
- `loops/PROGRESS_V2.md` — previous iteration notes (create if missing)

## Key facts (do NOT re-discover these)

- TechZone MCP URL: `https://mcp.techzone.ibm.com/servers/c7442b81221647c3b36c75df4f2f88e8/mcp`
- TechZone auth header: `TechZone-Token: <value of TECHZONE_API_KEY env var>`
- TechZone MCP uses JSON-RPC 2.0 over HTTP POST (MCP streamable-http transport)
- The tool name for creating a request is `request-mcp-techzone-create-request`
- The `SAMPLE_TRANSCRIPT` constant already exists in `app.py`
- All existing prompts (EXTRACTION_PROMPT, GAP_CHECK_PROMPT, etc.) must be preserved unchanged
- The app must still work with just `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` — TechZone key is optional

## Instructions

1. **Orient**:
   - Read the files listed above in full.
   - Check `git log --oneline -5` to see what was done previously.

2. **Plan**:
   - Read `loops/IMPLEMENTATION_PLAN_V2.md` — find the first unchecked `- [ ]` task.
   - Read `loops/PROGRESS_V2.md` for context from prior iterations.

3. **Select**:
   - Pick the **first** unchecked `- [ ]` item only.
   - Do exactly **one** task. Do not attempt multiple tasks.

4. **Act**:
   - Implement the task. Keep existing code style — do not refactor unrelated code.
   - For Phase 8 (TechZone MCP): use `httpx` for the HTTP call (add to requirements.txt if needed). The MCP JSON-RPC body format is:
     ```json
     {
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "request-mcp-techzone-create-request",
         "arguments": {
           "platformId": "<derived from deployment_env>",
           "start": "<ISO 8601 UTC>",
           "bearerToken": "<TECHZONE_API_KEY value>",
           "purpose": "<purpose>",
           "geography": "<region>"
         }
       }
     }
     ```
   - For Phase 9 (MCP server): use `fastmcp` package; tools import shared helpers from `app.py`.
   - Mark completed task as `- [x]` in `loops/IMPLEMENTATION_PLAN_V2.md`.
   - Append a concise entry to `loops/PROGRESS_V2.md`:
     - Task completed
     - Key decisions
     - Files changed
     - Next task

5. **Stop**: One task, mark done, write progress, exit.

## Constraints
- Never hardcode credentials or API keys
- Never break the existing PoC Analyzer flow
- Keep all UI in Streamlit — no new frontend frameworks
- `.env.example` must document every new env var added
