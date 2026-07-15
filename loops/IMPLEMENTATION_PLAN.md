# Implementation Plan — Discovery PoC Orchestrator

## Phase 1: Structured JSON Extraction (app.py)
- [x] Replace `SUMMARY_PROMPT` with a JSON-returning extraction prompt covering fields: `stakeholders`, `use_cases`, `integrations`, `deployment_env`, `success_criteria`, `risks`, `action_items`.
- [x] Update `call_watsonx` (or add a helper) to parse the JSON response and surface a clear error when parsing fails.
- [x] Display each extracted field in a `st.expander` card instead of raw text.
- [x] Update `requirements.txt` if any new dependencies are needed.

## Phase 2: Gap Check
- [x] Add a second LLM call that feeds the extracted JSON back and asks: "Which fields are missing, empty, or too vague to proceed?"
- [x] Display the gap-check result as a `st.warning` box with bullet-point questions.
- [x] Add a "Confirm and continue" button — artifact generation must be gated behind this confirmation.

## Phase 3: Risk Detection + Readiness Score
- [x] Create `risk_triggers.py` — a keyword→flag dict covering: HIPAA, SAP, GDPR, Voice, on-prem, SSO/Azure AD.
- [ ] Implement a readiness score (0–100): start at 100, deduct points for each missing/vague field and each risk flag without a mitigation.
- [ ] Display the score as a `st.progress` bar with a breakdown table showing which items cost points.

## Phase 4: Artifact Generation Tabs
- [ ] Add four LLM calls to generate: IBM Placemat (structured markdown), PoC Checklist (checkbox list), Architecture summary (component list), Kickoff email draft.
- [ ] Display each artifact in its own `st.tab`.
- [ ] Replace the single download button with a ZIP download containing all four artifacts as `.md` files.

## Phase 5: Polish + Sample Transcript + TechZone Button
- [ ] Add a sample transcript (the Azure/GDPR/SAP/HR onboarding scenario) as a pre-fill button in the UI.
- [ ] Wire the TechZone button: if readiness score ≥ 70 and `deployment_env` is detected, show a "Request TechZone environment" button (human-confirmed, no auto-submit).
- [ ] Ensure all Streamlit state resets cleanly when new notes are analysed.
- [ ] Run the app locally and verify the full flow end-to-end with the sample transcript.
