# Implementation Plan V2 — Discovery PoC Orchestrator UI Refresh

## Phase 6: Two-Tab Layout (PoC Analyzer + Demo)
- [x] Restructure `app.py` into two top-level `st.tabs`: "🔬 PoC Analyzer" (existing flow) and "🎬 Demo" (static pre-baked walkthrough).
- [x] Build the Demo tab: display `SAMPLE_TRANSCRIPT` text + hardcoded extraction JSON + hardcoded readiness score (87) + hardcoded gap list + hardcoded artifact previews — no LLM calls, renders instantly.
- [x] Ensure all session state keys are namespaced per-tab so Demo and Analyzer don't interfere.

## Phase 7: Compact UI (Less Scrolling)
- [x] Move model selector and PoC readiness score badge into `st.sidebar` — free up main area vertical space.
- [x] Collapse all `st.expander` cards by default (`expanded=False`) except the active result section.
- [x] Show extraction fields (stakeholders, use cases, risks, etc.) in a 2-column grid layout using `st.columns` instead of stacked expanders.
- [x] Move gap check and score breakdown into a single collapsed expander; show only the score banner and readiness status inline.
- [x] Reduce text area height from 280 to 180px; move Upload/Paste toggle inline with the Load Sample button.

## Phase 8: TechZone MCP Integration
- [x] Add `TECHZONE_API_KEY` and `TECHZONE_MCP_URL` to `.env.example` (create if missing) with instructions.
- [x] Implement `request_techzone_env(deployment_env, purpose, notes)` in `app.py` — POSTs to the TechZone MCP endpoint (`https://mcp.techzone.ibm.com/servers/c7442b81221647c3b36c75df4f2f88e8/mcp`) with `TechZone-Token` header using the MCP JSON-RPC call format for `request-mcp-techzone-create-request`.
- [x] Replace the fake TechZone form with the real MCP call: show spinner during request, display returned request ID + status on success, show error details on failure.
- [x] Gracefully disable the TechZone button with an `st.info` message when `TECHZONE_API_KEY` is absent from env.

## Phase 9: MCP Server (mcp_server.py)
- [x] Create `mcp_server.py` using `FastMCP` that exposes three tools: `analyze_notes(notes_text, model_id)`, `check_gaps(extracted_json)`, `generate_artifacts(extracted_json, model_id)`.
- [x] Each tool reuses the existing prompt constants and `call_watsonx` from `app.py` (import shared helpers from a new `watsonx_helpers.py` module extracted from `app.py`).
- [x] Add `fastmcp` to `requirements.txt`.
- [x] Add startup instructions to `README.md`: `python mcp_server.py` runs the MCP server on stdio for local use.
