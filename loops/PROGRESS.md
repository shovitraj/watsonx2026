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

---

## Iteration 2 — 2026-07-15

**Task completed:** Phase 2 — Gap Check

**Changes made:**
- Added `GAP_CHECK_PROMPT` that analyzes extracted JSON for missing/vague fields
- Implemented `check_gaps()` function that calls watsonx with gap analysis prompt
- Gap check runs automatically after extraction completes
- Display readiness status banner (Ready/Needs clarification/Blocked) with color coding
- Show gaps in expandable section with field name, issue, and specific question to ask client
- Added "Confirm and continue" button that gates artifact generation (Phase 4)
- Session state management: clear gap check and confirmation on new analysis

**Key decisions:**
- Gap check runs immediately after extraction (no separate button) for seamless UX
- Readiness levels: Ready (green), Needs clarification (yellow), Blocked (red)
- Confirmation button only shows before confirmation to prevent re-confirmation
- Graceful fallback if gap check fails (warning but continues)
- Gap questions formatted as bullet points with ❓ emoji for clarity

**Files changed:**
- `app.py` — added GAP_CHECK_PROMPT, check_gaps() function, gap display UI, confirmation button
- `loops/IMPLEMENTATION_PLAN.md` — marked Phase 2 tasks complete
- `loops/PROGRESS.md` — this file

**Next task:** Phase 3 — Risk Detection + Readiness Score (create risk_triggers.py, implement scoring)

---

## Iteration 3 — 2026-07-15

**Task completed:** Phase 3.1 — Create risk_triggers.py

**Changes made:**
- Created `risk_triggers.py` with comprehensive keyword→risk category mapping
- Covered all required categories: HIPAA, SAP, GDPR, Voice, on-prem, SSO/Azure AD
- Added additional relevant triggers: PCI, SOX, FedRAMP, ISO 27001, NIST, FISMA compliance
- Added enterprise systems: Salesforce, Oracle, Workday, PeopleSoft
- Added AI-specific triggers: RAG, vector database, embedding, model training, real-time processing
- Implemented `detect_risks()` function to scan text and return matched risk categories with keywords
- Implemented `get_risk_severity()` function to assign default severity levels (High/Medium/Low)

**Key decisions:**
- Used lowercase keywords for case-insensitive matching
- Grouped related keywords under single risk categories (e.g., "hipaa", "phi", "patient data" → "HIPAA Compliance")
- Severity levels: High for compliance/security (HIPAA, GDPR, PCI), Medium for integrations/deployment, Low for others
- Helper functions return structured data ready for UI display

**Files changed:**
- `risk_triggers.py` — new file with RISK_TRIGGERS dict and helper functions
- `loops/IMPLEMENTATION_PLAN.md` — marked Phase 3.1 task complete
- `loops/PROGRESS.md` — this file

**Next task:** Phase 3.2 — Implement readiness score (0-100) with point deductions and progress bar display