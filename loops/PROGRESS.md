# Progress Log

_Each iteration appends one entry here._

---

## Iteration 1 — 2026-07-15

**Task completed:** Phase 1 — Structured JSON Extraction

**Changes made:**
- Replaced `SUMMARY_PROMPT` and `ACTION_ITEMS_PROMPT` with single `EXTRACTION_PROMPT` that returns structured JSON
- JSON schema covers: `stakeholders`, `use_cases`, `integrations`, `deployment_env`, `success_criteria`, `risks`, `action_items`
- Added JSON parsing with clear error handling (displays parse errors + raw response preview)
- Replaced old summary/actions display with 7 `st.expander` cards, one per field
- Changed download button from markdown report to JSON file
- Increased `max_new_tokens` to 2000 for JSON extraction call

**Key decisions:**
- Used single extraction call instead of separate summary + actions calls (more efficient, consistent structure)
- Display all expanders by default for stakeholders and use cases (most important fields), others collapsed
- Show helpful messages when fields are empty ("No stakeholders identified" vs silent)
- Severity emoji indicators for risks (🔴 High, 🟡 Medium, 🟢 Low)

**Files changed:**
- `app.py` — replaced prompts, updated analyze handler, new display logic
- `loops/IMPLEMENTATION_PLAN.md` — marked Phase 1 tasks complete
- `loops/PROGRESS.md` — this file

**Next task:** Phase 2 — Gap Check (second LLM call to identify missing/vague fields)