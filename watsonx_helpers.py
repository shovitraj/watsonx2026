"""
watsonx_helpers.py — shared watsonx client, prompts, and analysis functions.

Imported by both app.py (Streamlit UI) and mcp_server.py (FastMCP server).
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

# ── Supported models ──────────────────────────────────────────────────────────

SUPPORTED_MODELS = [
    "ibm/granite-3-1-8b-base",
    "ibm/granite-4-h-small",
    "ibm/granite-8b-code-instruct",
    "ibm/granite-guardian-3-8b",
    "meta-llama/llama-3-1-70b-gptq",
    "meta-llama/llama-3-1-8b",
    "meta-llama/llama-3-3-70b-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
    "mistral-large-2512",
    "mistralai/mistral-medium-2505",
    "mistralai/mistral-small-3-1-24b-instruct-2503",
    "openai/gpt-oss-120b",
]
DEFAULT_MODEL = "meta-llama/llama-3-3-70b-instruct"


# ── watsonx client ────────────────────────────────────────────────────────────

def get_watsonx_client():
    from ibm_watsonx_ai import APIClient, Credentials
    credentials = Credentials(
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        api_key=os.getenv("WATSONX_API_KEY"),
    )
    return APIClient(credentials)


def call_watsonx(prompt: str, model_id: str = DEFAULT_MODEL, max_new_tokens: int = 800) -> str:
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as Params

    model = ModelInference(
        model_id=model_id,
        api_client=get_watsonx_client(),
        project_id=os.getenv("WATSONX_PROJECT_ID"),
        params={
            Params.DECODING_METHOD: "greedy",
            Params.MAX_NEW_TOKENS: max_new_tokens,
            Params.REPETITION_PENALTY: 1.1,
        },
    )
    return str(model.generate_text(prompt=prompt)).strip()


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Strip prose around a JSON object and attempt to repair truncation."""
    start = text.find("{")
    if start == -1:
        return text
    end = len(text)
    while end > start:
        candidate = text[start:end]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass
        prev = candidate.rfind("}", 0, len(candidate) - 1)
        if prev == -1:
            break
        end = start + prev + 1
    last = text.rfind("}")
    return text[start: last + 1] if last != -1 else text[start:]


# ── Prompts ───────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
<|system|>
You are an expert Discovery PoC analyst for IBM watsonx. Extract structured information \
from client meeting notes to prepare for a Proof of Concept engagement.

Return ONLY valid JSON in this exact structure:

{{
  "stakeholders": [{{"name": "Full Name", "role": "Job Title", "organization": "Company/Dept"}}],
  "use_cases": [{{"title": "Brief title", "description": "What they want to achieve"}}],
  "integrations": [{{"system": "System name", "purpose": "Why it needs to integrate"}}],
  "deployment_env": {{
    "cloud_provider": "AWS | Azure | IBM Cloud | GCP | On-premises | Hybrid | Unknown",
    "region": "Geographic region or 'Unknown'",
    "constraints": "Any compliance, data residency, or infrastructure constraints"
  }},
  "success_criteria": ["Measurable outcome 1"],
  "risks": [{{"risk": "Description of risk", "severity": "High | Medium | Low"}}],
  "action_items": [{{"owner": "Person or 'Unassigned'", "task": "What needs to be done", "due": "Date or 'TBD'"}}]
}}

Rules: Return ONLY the JSON — no markdown, no preamble. Use [] for empty lists, "" for unknown strings.
<|user|>
Meeting notes:
{notes}
<|assistant|>
"""

GAP_CHECK_PROMPT = """\
<|system|>
You are a Discovery PoC readiness analyst. Review extracted meeting data and identify gaps.

Return ONLY valid JSON:
{{
  "gaps": [{{"field": "Field name", "issue": "What's missing", "question": "Question to ask client"}}],
  "readiness": "Ready | Needs clarification | Blocked",
  "summary": "One-sentence assessment"
}}

Rules: Return ONLY the JSON. List 3-7 gaps maximum.
<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""

PLACEMAT_PROMPT = """\
<|system|>
Create an IBM Placemat in markdown for a Discovery PoC. Include: Executive Summary, Stakeholders, \
Business Objectives, Use Cases, Technical Architecture, Success Criteria, Risks & Mitigation, Next Steps.
Return ONLY the markdown document — no preamble, no code fences.
<|user|>
{extracted_json}
<|assistant|>
"""

CHECKLIST_PROMPT = """\
<|system|>
Create a PoC checklist in markdown with checkboxes (- [ ] format). Include 15-25 items grouped under: \
Pre-PoC Setup, Technical Requirements, Use Case Implementation, Testing & Validation, Risk Mitigation, \
Documentation & Handoff. Return ONLY the markdown checklist.
<|user|>
{extracted_json}
<|assistant|>
"""

ARCHITECTURE_PROMPT = """\
<|system|>
Create a technical architecture summary in markdown. Include: Deployment Environment, Core Components, \
Integration Points, Authentication & Security, Data Flow, Scalability Considerations. \
Return ONLY the markdown document.
<|user|>
{extracted_json}
<|assistant|>
"""

EMAIL_PROMPT = """\
<|system|>
Draft a professional PoC kickoff email (200-300 words). Include subject line, thank attendees, \
summarize key points, list next steps with owners and dates. Return ONLY the email text.
<|user|>
{extracted_json}
<|assistant|>
"""


# ── Analysis functions ────────────────────────────────────────────────────────

def analyze_notes(notes_text: str, model_id: str = DEFAULT_MODEL) -> dict:
    """Extract structured data from meeting notes. Returns the parsed JSON dict."""
    raw = call_watsonx(
        EXTRACTION_PROMPT.format(notes=notes_text),
        model_id=model_id,
        max_new_tokens=4000,
    )
    return json.loads(_extract_json(raw))


def check_gaps(extracted_data: dict, model_id: str = DEFAULT_MODEL) -> dict:
    """Run gap analysis on extracted data. Returns gaps, readiness, summary."""
    raw = call_watsonx(
        GAP_CHECK_PROMPT.format(extracted_json=json.dumps(extracted_data, indent=2)),
        model_id=model_id,
        max_new_tokens=1000,
    )
    try:
        return json.loads(_extract_json(raw))
    except json.JSONDecodeError:
        return {"gaps": [], "readiness": "Needs clarification", "summary": "Gap check parse error"}


def generate_artifacts(extracted_data: dict, model_id: str = DEFAULT_MODEL) -> dict:
    """Generate all four PoC artifacts. Returns dict with placemat, checklist, architecture, email."""
    extracted_json = json.dumps(extracted_data, indent=2)
    artifacts = {}
    for key, prompt, tokens in [
        ("placemat",     PLACEMAT_PROMPT,     2000),
        ("checklist",    CHECKLIST_PROMPT,    1500),
        ("architecture", ARCHITECTURE_PROMPT, 1500),
        ("email",        EMAIL_PROMPT,         800),
    ]:
        try:
            artifacts[key] = call_watsonx(
                prompt.format(extracted_json=extracted_json),
                model_id=model_id,
                max_new_tokens=tokens,
            )
        except Exception as e:
            artifacts[key] = f"Error generating {key}: {e}"
    return artifacts
