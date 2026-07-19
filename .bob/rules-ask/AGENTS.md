# Project Documentation Context (Non-Obvious Only)

## What This Project Is

**watsonx Discovery PoC Orchestrator** — a Streamlit app (`app.py`) that ingests IBM client meeting notes (paste, .txt, .docx, or .pdf), calls IBM watsonx foundation models to extract structured data, runs a gap analysis and readiness scoring pipeline, then generates four PoC artifacts (IBM Placemat, PoC Checklist, Architecture Summary, Kickoff Email) for download.

It was built incrementally using an **agentic loop** (`loops/`) that drove IBM Bob Shell through six iterations, one task per run, guided by `loops/IMPLEMENTATION_PLAN.md`.

---

## Key Files

| File | What it does |
|---|---|
| `app.py` | The entire application — UI, watsonx calls, prompts, file parsers, scoring |
| `risk_triggers.py` | Keyword → risk category mapping; `detect_risks()` scans text, `get_risk_severity()` returns High/Medium/Low |
| `requirements.txt` | `streamlit`, `ibm-watsonx-ai`, `python-dotenv`, `python-docx`, `PyPDF2` |
| `loops/IMPLEMENTATION_PLAN.md` | All 5 phases, all tasks complete (`- [x]`) — the loop is finished |
| `loops/PROGRESS.md` | Six iteration entries documenting what each loop run did and why |
| `loops/prompt.md` | The loop agent's operating instruction — one task per iteration, then stop |
| `loops/loop.sh` | Bash outer loop; reads `IMPLEMENTATION_PLAN.md` to detect the done condition |

---

## Analysis Pipeline (in order)

1. **`EXTRACTION_PROMPT`** → structured JSON with 7 fields: `stakeholders`, `use_cases`, `integrations`, `deployment_env`, `success_criteria`, `risks`, `action_items`
2. **`GAP_CHECK_PROMPT`** → `{ gaps, readiness, summary }` — flags missing/vague fields with specific client questions
3. **`calculate_readiness_score()`** → score 0–100 derived from field completeness + unmitigated risks detected by `risk_triggers.py`
4. **[User confirmation gate]** — user reviews extracted data and gap check before artifact generation
5. **`generate_artifacts()`** → four LLM calls producing: IBM Placemat (markdown), PoC Checklist (markdown checkboxes), Architecture Summary (markdown), Kickoff Email (text)
6. **ZIP download** — all four artifacts + `discovery_extraction.json` bundled as `poc_artifacts.zip`
7. **TechZone button** — shown only if score ≥ 70 and a known `cloud_provider` is detected

---

## Supported Models

`SUPPORTED_MODELS` in `app.py` is a curated list of **text-generation models only** — it deliberately excludes embedding, reranker, and TTM models. Default: `meta-llama/llama-3-3-70b-instruct`.

Models include:
- IBM Granite: `granite-3-1-8b-base`, `granite-4-h-small`, `granite-8b-code-instruct`, `granite-guardian-3-8b`
- Meta Llama: `llama-3-1-70b-gptq`, `llama-3-1-8b`, `llama-3-3-70b-instruct`, `llama-4-maverick-17b-128e-instruct-fp8`
- Mistral: `mistral-large-2512`, `mistral-medium-2505`, `mistral-small-3-1-24b-instruct-2503`
- OpenAI (via watsonx): `gpt-oss-120b`

---

## Risk Trigger Categories

`risk_triggers.py` maps keywords to risk categories. Coverage:

| Severity | Categories |
|---|---|
| **High** | HIPAA Compliance, GDPR Compliance, PII Protection, Air-Gapped Environment, SOX, PCI, FedRAMP |
| **Medium** | SAP Integration, On-Premises Deployment, SSO/Identity Integration, Data Residency, Custom Model Training, Real-Time Processing |
| **Low** | CRM Integration, Enterprise System Integration, Voice/Audio Processing, Private Cloud, Hybrid Cloud, RAG Implementation, Vector Database, Embedding/Vector Search, ISO 27001, NIST, FISMA, Batch Processing |

---

## Sample Transcript

The built-in sample (`SAMPLE_TRANSCRIPT` in `app.py`) is a fictional **Nexus Financial** Azure/GDPR/SAP/HR onboarding scenario designed to trigger:
- GDPR + data residency + PII risks
- Azure AD / SSO integration
- SAP SuccessFactors + Workday integrations
- Fine-tuning capability question
- Previous vendor failure concern (ROI pressure)
- 90-day PoC timeline with measurable success criteria

Use it to demo the full pipeline end-to-end without real client data.

---

## Loop Build History

The app was built in 6 loop iterations, all on `feature/poc-orchestrator-loop`:

| Iteration | What was built |
|---|---|
| 1 | Structured JSON extraction — replaced free-text summary with 7-field JSON schema |
| 2 | Gap check — second LLM call identifies missing/vague fields with client questions |
| 3.1 | Created `risk_triggers.py` — keyword → risk category mapping with severity levels |
| 3.2 | Readiness score (0–100) — deduction table, progress bar, risk breakdown |
| 4 | Four artifact tabs (Placemat, Checklist, Architecture, Email) with per-tab downloads |
| 5 | ZIP download, sample transcript button, TechZone provisioning form, state reset |

---

## Environment Setup

```bash
cp .bob/skills/generate-loop/assets/.env-template .env
# Edit .env: set WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL
pip install -r requirements.txt
streamlit run app.py
```

The app calls `check_env()` on startup and halts with a clear error if either `WATSONX_API_KEY` or `WATSONX_PROJECT_ID` is missing.
