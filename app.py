import io
import json
import os
import zipfile

import streamlit as st
from dotenv import load_dotenv
from risk_triggers import get_risk_severity

load_dotenv()


def _extract_json(text: str) -> str:
    """Strip prose before/after the JSON object and attempt to repair truncation."""
    start = text.find("{")
    if start == -1:
        return text  # let json.loads raise a meaningful error
    # Try increasingly shorter slices ending at each closing brace
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
    # Last resort: first { to last }
    last = text.rfind("}")
    return text[start : last + 1] if last != -1 else text[start:]


# ── watsonx client ────────────────────────────────────────────────────────────

def get_watsonx_client():
    from ibm_watsonx_ai import APIClient, Credentials
    credentials = Credentials(
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        api_key=os.getenv("WATSONX_API_KEY"),
    )
    return APIClient(credentials)


# Text-generation models only — embedding/reranker/TTM models cannot generate text
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
    response = model.generate_text(prompt=prompt)
    return str(response).strip()


def check_gaps(extracted_data: dict, model_id: str = DEFAULT_MODEL) -> dict:
    """Run gap analysis on extracted data to identify missing or unclear fields."""
    import json

    extracted_json = json.dumps(extracted_data, indent=2)
    prompt = GAP_CHECK_PROMPT.format(extracted_json=extracted_json)

    raw_response = call_watsonx(prompt, model_id=model_id, max_new_tokens=1000)

    try:
        gap_data = json.loads(_extract_json(raw_response))
        return gap_data
    except json.JSONDecodeError:
        # Fallback if parsing fails
        return {
            "gaps": [],
            "readiness": "Needs clarification",
            "summary": "Unable to parse gap analysis response"
        }


def calculate_readiness_score(extracted_data: dict, notes_text: str) -> dict:
    """
    Calculate PoC readiness score (0-100) based on data completeness and risk detection.

    Scoring logic:
    - Start at 100 points
    - Deduct points for missing/empty critical fields
    - Deduct points for detected risks without mitigation plans

    Returns:
        dict with keys: score (int), breakdown (list of deduction items), detected_risks (dict)
    """
    from risk_triggers import detect_risks, get_risk_severity

    score = 100
    breakdown = []

    # Check critical fields for completeness
    stakeholders = extracted_data.get("stakeholders", [])
    if not stakeholders:
        score -= 15
        breakdown.append({"item": "No stakeholders identified", "points": -15, "category": "Missing Data"})

    use_cases = extracted_data.get("use_cases", [])
    if not use_cases:
        score -= 20
        breakdown.append({"item": "No use cases defined", "points": -20, "category": "Missing Data"})
    elif any(not uc.get("description") or uc.get("description") == "No description" for uc in use_cases):
        score -= 10
        breakdown.append({"item": "Use case descriptions incomplete", "points": -10, "category": "Vague Data"})

    success_criteria = extracted_data.get("success_criteria", [])
    if not success_criteria:
        score -= 15
        breakdown.append({"item": "No success criteria defined", "points": -15, "category": "Missing Data"})

    deployment_env = extracted_data.get("deployment_env", {})
    cloud_provider = deployment_env.get("cloud_provider", "Unknown")
    if cloud_provider == "Unknown" or not cloud_provider:
        score -= 10
        breakdown.append({"item": "Deployment environment unclear", "points": -10, "category": "Vague Data"})

    integrations = extracted_data.get("integrations", [])
    if integrations and any(not i.get("purpose") or i.get("purpose") == "No purpose specified" for i in integrations):
        score -= 5
        breakdown.append({"item": "Integration purposes unclear", "points": -5, "category": "Vague Data"})

    # Detect risks from meeting notes
    detected_risks = detect_risks(notes_text)

    # Check if risks have mitigation plans
    extracted_risks = extracted_data.get("risks", [])
    extracted_risk_texts = [r.get("risk", "").lower() for r in extracted_risks]

    for risk_category, keywords in detected_risks.items():
        severity = get_risk_severity(risk_category)

        # Check if this risk category is mentioned in extracted risks
        has_mitigation = any(
            risk_category.lower() in risk_text or
            any(kw in risk_text for kw in keywords)
            for risk_text in extracted_risk_texts
        )

        if not has_mitigation:
            # Deduct points based on severity
            if severity == "High":
                deduction = 10
            elif severity == "Medium":
                deduction = 5
            else:
                deduction = 3

            score -= deduction
            breakdown.append({
                "item": f"{risk_category} detected but no mitigation plan",
                "points": -deduction,
                "category": "Unmitigated Risk",
                "severity": severity
            })

    # Ensure score doesn't go below 0
    score = max(0, score)

    return {
        "score": score,
        "breakdown": breakdown,
        "detected_risks": detected_risks
    }


def generate_artifacts(extracted_data: dict, model_id: str = DEFAULT_MODEL) -> dict:
    """
    Generate all four PoC artifacts from extracted data.

    Returns:
        dict with keys: placemat, checklist, architecture, email (all strings)
    """
    import json

    extracted_json = json.dumps(extracted_data, indent=2)

    artifacts = {}

    # Generate IBM Placemat
    try:
        artifacts["placemat"] = call_watsonx(
            PLACEMAT_PROMPT.format(extracted_json=extracted_json),
            model_id=model_id,
            max_new_tokens=2000
        )
    except Exception as e:
        artifacts["placemat"] = f"Error generating placemat: {e}"

    # Generate PoC Checklist
    try:
        artifacts["checklist"] = call_watsonx(
            CHECKLIST_PROMPT.format(extracted_json=extracted_json),
            model_id=model_id,
            max_new_tokens=1500
        )
    except Exception as e:
        artifacts["checklist"] = f"Error generating checklist: {e}"

    # Generate Architecture Summary
    try:
        artifacts["architecture"] = call_watsonx(
            ARCHITECTURE_PROMPT.format(extracted_json=extracted_json),
            model_id=model_id,
            max_new_tokens=1500
        )
    except Exception as e:
        artifacts["architecture"] = f"Error generating architecture: {e}"

    # Generate Kickoff Email
    try:
        artifacts["email"] = call_watsonx(
            EMAIL_PROMPT.format(extracted_json=extracted_json),
            model_id=model_id,
            max_new_tokens=800
        )
    except Exception as e:
        artifacts["email"] = f"Error generating email: {e}"

    return artifacts


# ── file parsers ──────────────────────────────────────────────────────────────

def parse_txt(file) -> str:
    return file.read().decode("utf-8", errors="ignore")


def parse_docx(file) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file.read()))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_pdf(file) -> str:
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def extract_text(uploaded_file) -> str:
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if ext == "txt":
        return parse_txt(uploaded_file)
    if ext == "docx":
        return parse_docx(uploaded_file)
    if ext == "pdf":
        return parse_pdf(uploaded_file)
    raise ValueError(f"Unsupported file type: .{ext}")


# ── prompts ───────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """\
<|system|>
You are an expert Discovery PoC analyst for IBM watsonx. Your job is to extract structured \
information from client meeting notes to prepare for a Proof of Concept engagement.

Extract the following fields from the meeting notes and return them as a JSON object. \
If a field cannot be determined from the notes, use an empty array [] or empty string "" as appropriate.

Return ONLY valid JSON in this exact structure:

{{
  "stakeholders": [
    {{"name": "Full Name", "role": "Job Title", "organization": "Company/Dept"}}
  ],
  "use_cases": [
    {{"title": "Brief title", "description": "What they want to achieve"}}
  ],
  "integrations": [
    {{"system": "System name (e.g., SAP, Salesforce)", "purpose": "Why it needs to integrate"}}
  ],
  "deployment_env": {{
    "cloud_provider": "AWS | Azure | IBM Cloud | GCP | On-premises | Hybrid | Unknown",
    "region": "Geographic region or 'Unknown'",
    "constraints": "Any compliance, data residency, or infrastructure constraints"
  }},
  "success_criteria": [
    "Measurable outcome 1",
    "Measurable outcome 2"
  ],
  "risks": [
    {{"risk": "Description of risk or concern", "severity": "High | Medium | Low"}}
  ],
  "action_items": [
    {{"owner": "Person name or 'Unassigned'", "task": "What needs to be done", "due": "Date or 'TBD'"}}
  ]
}}

Rules:
- Return ONLY the JSON object — no markdown code fences, no preamble, no explanation
- Use empty arrays [] for list fields with no data
- Use empty strings "" for text fields with no data
- For deployment_env, always include all three sub-fields even if "Unknown" or ""
- Extract risks even if only briefly mentioned
- Be precise — do not invent information not present in the notes
<|user|>
Meeting notes:
{notes}
<|assistant|>
"""

GAP_CHECK_PROMPT = """\
<|system|>
You are a Discovery PoC readiness analyst for IBM watsonx. Your job is to review extracted \
information from client meeting notes and identify what's missing or too vague to proceed \
with a successful Proof of Concept.

Review the extracted data below and identify gaps that would prevent a successful PoC. \
Focus on:
- Missing or empty critical fields (stakeholders, use cases, success criteria)
- Vague or incomplete information (e.g., "Unknown" deployment environment, unclear success metrics)
- Missing technical details needed for scoping (integrations, SSO/IdP, data sources)
- Unaddressed risks or concerns

Return your analysis as a JSON object with this structure:

{{
  "gaps": [
    {{"field": "Field name", "issue": "What's missing or unclear", "question": "Specific question to ask the client"}}
  ],
  "readiness": "Ready | Needs clarification | Blocked",
  "summary": "One-sentence assessment of PoC readiness"
}}

Rules:
- Return ONLY the JSON object — no markdown, no preamble
- List 3-7 gaps maximum — prioritize the most critical ones
- Each question should be specific and actionable
- Use "Ready" only if all critical fields are complete and clear
- Use "Blocked" if multiple critical fields are missing

<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""

PLACEMAT_PROMPT = """\
<|system|>
You are an IBM watsonx Solutions Engineer creating an IBM Placemat document for a Discovery PoC.

Generate a structured IBM Placemat in markdown format based on the extracted discovery data below.

The Placemat should include these sections:

# IBM watsonx Discovery PoC — [Client Name]

## Executive Summary
Brief 2-3 sentence overview of the engagement

## Stakeholders
List key stakeholders with roles and organizations

## Business Objectives
What the client wants to achieve (from use cases)

## Use Cases
Detailed description of each use case with expected outcomes

## Technical Architecture
- Deployment environment (cloud provider, region)
- Required integrations
- Authentication/SSO requirements

## Success Criteria
Measurable outcomes that define PoC success

## Risks & Mitigation
Identified risks with severity and mitigation strategies

## Next Steps
Action items with owners and due dates

Rules:
- Use proper markdown formatting (headers, lists, bold)
- Be professional and concise
- Extract client name from stakeholders if available, otherwise use "Client"
- Return ONLY the markdown document — no preamble, no code fences

<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""

CHECKLIST_PROMPT = """\
<|system|>
You are an IBM watsonx Solutions Engineer creating a PoC Checklist for a Discovery engagement.

Generate a comprehensive PoC checklist in markdown format with checkboxes based on the extracted data below.

The checklist should cover:

# watsonx PoC Checklist

## Pre-PoC Setup
- [ ] Stakeholder kickoff meeting scheduled
- [ ] Access credentials obtained
- [ ] Development environment provisioned
- [ ] [Add items based on deployment_env and integrations]

## Technical Requirements
- [ ] [Items based on integrations, SSO, data sources]

## Use Case Implementation
- [ ] [One checkbox per use case with key deliverables]

## Testing & Validation
- [ ] [Items based on success criteria]

## Risk Mitigation
- [ ] [One checkbox per identified risk]

## Documentation & Handoff
- [ ] Architecture documentation complete
- [ ] User guide created
- [ ] Handoff meeting scheduled

Rules:
- Use markdown checkbox format: - [ ] Item
- Be specific and actionable
- Include 15-25 items total
- Group related items under headers
- Return ONLY the markdown checklist — no preamble, no code fences

<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""

ARCHITECTURE_PROMPT = """\
<|system|>
You are an IBM watsonx Solutions Architect creating a technical architecture summary for a Discovery PoC.

Generate a concise architecture summary in markdown format based on the extracted data below.

The summary should include:

# Technical Architecture Summary

## Deployment Environment
- Cloud Provider: [from deployment_env]
- Region: [from deployment_env]
- Constraints: [from deployment_env]

## Core Components
- watsonx.ai foundation models
- [List other IBM watsonx components needed based on use cases]

## Integration Points
[List each integration with purpose and data flow]

## Authentication & Security
[SSO/IdP requirements, security considerations from risks]

## Data Flow
[High-level description of how data moves through the system]

## Scalability Considerations
[Based on use cases and deployment environment]

Rules:
- Be technical but concise
- Focus on IBM watsonx components
- Include integration architecture
- Mention security/compliance requirements from risks
- Return ONLY the markdown document — no preamble, no code fences

<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""

EMAIL_PROMPT = """\
<|system|>
You are an IBM watsonx Solutions Engineer drafting a kickoff email for a Discovery PoC.

Generate a professional kickoff email based on the extracted data below.

The email should:
- Have a clear subject line
- Thank attendees for the discovery meeting
- Summarize key points discussed
- List next steps with owners and dates
- Set expectations for the PoC timeline
- Include a professional closing

Format:
Subject: [Appropriate subject line]

[Email body]

Rules:
- Professional but friendly tone
- 200-300 words
- Include specific names from stakeholders
- Reference specific use cases discussed
- Return ONLY the email text — no preamble, no code fences

<|user|>
Extracted data:
{extracted_json}
<|assistant|>
"""


# ── sample transcript ─────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """\
Meeting Notes — Discovery Call
Date: 2026-07-14
Attendees: Sarah Chen (VP Digital Transformation, Nexus Financial), \
Marcus Rowe (Enterprise Architect, Nexus Financial), \
Priya Nair (IBM Client Engineer), \
Tom Walsh (IBM Account Executive)

--- Discussion ---

Sarah opened by explaining Nexus Financial's strategic priority for FY27: automating \
HR onboarding and employee support using AI. They have ~4,000 employees across Europe \
and North America. Current onboarding takes 3-4 weeks; target is under 5 days.

Use Cases:
1. HR Onboarding Assistant — answer new-hire questions (benefits, policies, IT setup), \
   integrate with Workday for employee data and SAP SuccessFactors for policy documents.
2. Employee Helpdesk Chatbot — handle IT and HR tier-1 tickets, route complex issues \
   to ServiceNow, reduce helpdesk call volume by 40%.

Marcus raised infrastructure constraints: Nexus Financial is Azure-first, West Europe \
region, with strict GDPR compliance requirements. All PII must stay in EU. They use \
Azure Active Directory for SSO. No on-premise systems will be involved, but they need \
data residency guarantees. Marcus also asked about model fine-tuning capabilities.

Sarah flagged a concern: they had a previous AI vendor fail to deliver; leadership \
needs to see measurable ROI within 90 days of PoC start.

Success criteria discussed:
- Onboarding assistant answers 80% of new-hire questions without human escalation
- Helpdesk chatbot deflects 40% of tier-1 tickets
- PoC delivered and demoed within 8 weeks

Risks noted by Marcus:
- GDPR data residency — all data must remain in EU
- Azure AD integration complexity (they use conditional access policies)
- SAP SuccessFactors API rate limits may affect document retrieval

Action items:
- Priya to send watsonx.ai architecture proposal by July 22
- Marcus to share Azure AD tenant details and API credentials for SAP by July 19
- Sarah to confirm executive sponsor for PoC kickoff meeting
- Tom to arrange TechZone environment provisioning on IBM Cloud, Frankfurt region
"""

# ── UI helpers ────────────────────────────────────────────────────────────────

def check_env() -> bool:
    missing = [v for v in ("WATSONX_API_KEY", "WATSONX_PROJECT_ID") if not os.getenv(v)]
    if missing:
        st.error(
            f"Missing environment variables: `{'`, `'.join(missing)}`\n\n"
            "Copy `.env.example` → `.env` and fill in your credentials."
        )
        return False
    return True


def render_results(summary: str, actions: str):
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("📋 Summary")
        st.markdown(summary)
    with col2:
        st.subheader("✅ Action Items")
        st.markdown(actions)


def render_analyzer_tab(selected_model: str):
    st.subheader("🔬 PoC Analyzer")

    st.divider()

    # ── input section ─────────────────────────────────────────────────────────
    input_method = st.radio(
        "Input method",
        ["✏️ Paste text", "📎 Upload file"],
        horizontal=True,
        label_visibility="collapsed",
    )

    notes_text = ""

    if input_method == "✏️ Paste text":
        # Sample transcript pre-fill
        col_pre, _ = st.columns([1, 3])
        with col_pre:
            if st.button("📋 Load sample transcript", help="Pre-fill with an Azure / GDPR / SAP / HR-onboarding scenario"):
                st.session_state["sample_loaded"] = True
                # Clear any previous analysis when loading sample
                for key in ("extracted_data", "gap_check", "readiness_score", "artifacts", "confirmed"):
                    st.session_state.pop(key, None)
                st.rerun()

        default_text = SAMPLE_TRANSCRIPT if st.session_state.get("sample_loaded") else ""
        notes_text = st.text_area(
            "Paste your meeting notes here",
            value=default_text,
            height=280,
            placeholder="e.g. Attendees: Alice, Bob, Carol\n\nAlice presented Q3 results...",
        )

    else:
        uploaded = st.file_uploader(
            "Upload meeting notes",
            type=["txt", "docx", "pdf"],
            help="Supported formats: .txt · .docx · .pdf",
        )
        if uploaded:
            with st.spinner("Reading file…"):
                try:
                    notes_text = extract_text(uploaded)
                    with st.expander("📄 Extracted text preview", expanded=False):
                        st.text(notes_text[:2000] + ("…" if len(notes_text) > 2000 else ""))
                except Exception as e:
                    st.error(f"Could not read file: {e}")
                    st.stop()

    # ── analyse button ────────────────────────────────────────────────────────
    st.divider()
    analyse_disabled = not notes_text.strip()
    if st.button("🔍 Analyse", type="primary", disabled=analyse_disabled, use_container_width=True):
        # Reset all previous results when starting a new analysis
        for key in ("extracted_data", "gap_check", "readiness_score", "artifacts", "confirmed"):
            st.session_state.pop(key, None)
        with st.spinner("Extracting structured data from watsonx…"):
            try:
                raw_response = call_watsonx(
                    EXTRACTION_PROMPT.format(notes=notes_text),
                    model_id=selected_model,
                    max_new_tokens=4000
                )

                # Parse JSON response
                try:
                    extracted_data = json.loads(_extract_json(raw_response))
                    st.session_state["extracted_data"] = extracted_data
                    # Clear previous gap check and confirmation
                    st.session_state.pop("gap_check", None)
                    st.session_state.pop("confirmed", None)
                except json.JSONDecodeError as je:
                    st.error(
                        f"Failed to parse watsonx response as JSON.\n\n"
                        f"**Error:** {je}\n\n"
                        f"**Raw response (first 500 chars):**\n```\n{raw_response[:500]}\n```"
                    )
                    st.stop()

            except Exception as e:
                st.error(f"watsonx error: {e}")
                st.stop()

        # Run gap check immediately after extraction
        with st.spinner("Checking for gaps and missing information…"):
            try:
                gap_data = check_gaps(st.session_state["extracted_data"], model_id=selected_model)
                st.session_state["gap_check"] = gap_data
            except Exception as e:
                st.warning(f"Gap check failed: {e}")
                # Continue anyway with empty gap check
                st.session_state["gap_check"] = {
                    "gaps": [],
                    "readiness": "Needs clarification",
                    "summary": "Gap check unavailable"
                }

        # Calculate readiness score
        with st.spinner("Calculating readiness score…"):
            try:
                score_data = calculate_readiness_score(st.session_state["extracted_data"], notes_text)
                st.session_state["readiness_score"] = score_data
            except Exception as e:
                st.warning(f"Readiness score calculation failed: {e}")
                # Continue with default score
                st.session_state["readiness_score"] = {
                    "score": 50,
                    "breakdown": [{"item": "Score calculation unavailable", "points": -50, "category": "Error"}],
                    "detected_risks": {}
                }

    # ── results ───────────────────────────────────────────────────────────────
    if "extracted_data" in st.session_state:
        st.divider()
        data = st.session_state["extracted_data"]

        # Readiness score details (score badge is now in sidebar)
        if "readiness_score" in st.session_state:
            score_data = st.session_state["readiness_score"]
            score = score_data["score"]
            breakdown = score_data["breakdown"]
            detected_risks = score_data["detected_risks"]

            # Breakdown table
            if breakdown:
                with st.expander("📉 Score breakdown — what reduced the score", expanded=False):
                    st.markdown("**Point deductions:**")

                    # Group by category
                    categories = {}
                    for item in breakdown:
                        cat = item.get("category", "Other")
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(item)

                    # Display by category
                    for category, items in categories.items():
                        st.markdown(f"**{category}:**")
                        for item in items:
                            points = item["points"]
                            description = item["item"]
                            severity = item.get("severity", "")
                            severity_emoji = ""
                            if severity == "High":
                                severity_emoji = "🔴 "
                            elif severity == "Medium":
                                severity_emoji = "🟡 "
                            elif severity == "Low":
                                severity_emoji = "🟢 "

                            st.markdown(f"- {severity_emoji}{description}: **{points} points**")
                        st.markdown("")

            # Display detected risks
            if detected_risks:
                with st.expander(f"⚠️ Detected risks ({len(detected_risks)} categories)", expanded=False):
                    st.markdown("**Risk triggers found in meeting notes:**")
                    for risk_category, keywords in detected_risks.items():
                        severity = get_risk_severity(risk_category)
                        severity_emoji = "🔴" if severity == "High" else "🟡" if severity == "Medium" else "🟢"
                        st.markdown(f"{severity_emoji} **{risk_category}** ({severity})")
                        st.markdown(f"  - Keywords: {', '.join(keywords[:5])}")

            st.divider()

        # Display gap check results
        if "gap_check" in st.session_state:
            gap_data = st.session_state["gap_check"]
            readiness = gap_data.get("readiness", "Needs clarification")
            summary = gap_data.get("summary", "")
            gaps = gap_data.get("gaps", [])

            # Show readiness banner
            if readiness == "Ready":
                st.success(f"✅ **PoC Readiness:** {readiness} — {summary}")
            elif readiness == "Blocked":
                st.error(f"🚫 **PoC Readiness:** {readiness} — {summary}")
            else:
                st.warning(f"⚠️ **PoC Readiness:** {readiness} — {summary}")

            # Show gaps if any
            if gaps:
                with st.expander("🔍 Missing or unclear information", expanded=False):
                    st.markdown("**The following items need clarification before proceeding:**")
                    for gap in gaps:
                        field = gap.get("field", "Unknown field")
                        issue = gap.get("issue", "")
                        question = gap.get("question", "")
                        st.markdown(f"- **{field}:** {issue}")
                        if question:
                            st.markdown(f"  - ❓ _{question}_")
                    st.divider()
                    st.markdown("_Review the extracted data below and update your notes if needed, then re-analyze._")

            # Confirmation button (only show if not already confirmed)
            if "confirmed" not in st.session_state:
                st.divider()
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("✅ Confirm and continue", type="primary", use_container_width=True):
                        st.session_state["confirmed"] = True
                        st.rerun()
                st.info("👆 Review the extraction above, then confirm to proceed with artifact generation.")
                st.divider()

        # Generate and display artifacts (only after confirmation)
        if st.session_state.get("confirmed"):
            # Generate artifacts if not already generated
            if "artifacts" not in st.session_state:
                with st.spinner("Generating PoC artifacts from watsonx…"):
                    try:
                        artifacts = generate_artifacts(data, model_id=selected_model)
                        st.session_state["artifacts"] = artifacts
                    except Exception as e:
                        st.error(f"Failed to generate artifacts: {e}")
                        st.stop()

            # Display artifacts in tabs
            st.divider()
            st.subheader("📄 Generated PoC Artifacts")

            tab1, tab2, tab3, tab4 = st.tabs([
                "📋 IBM Placemat",
                "✅ PoC Checklist",
                "🏗️ Architecture",
                "📧 Kickoff Email"
            ])

            artifacts = st.session_state["artifacts"]

            with tab1:
                st.markdown(artifacts.get("placemat", "No placemat generated"))
                st.download_button(
                    "⬇️ Download Placemat (.md)",
                    data=artifacts.get("placemat", ""),
                    file_name="ibm_placemat.md",
                    mime="text/markdown",
                )

            with tab2:
                st.markdown(artifacts.get("checklist", "No checklist generated"))
                st.download_button(
                    "⬇️ Download Checklist (.md)",
                    data=artifacts.get("checklist", ""),
                    file_name="poc_checklist.md",
                    mime="text/markdown",
                )

            with tab3:
                st.markdown(artifacts.get("architecture", "No architecture generated"))
                st.download_button(
                    "⬇️ Download Architecture (.md)",
                    data=artifacts.get("architecture", ""),
                    file_name="architecture_summary.md",
                    mime="text/markdown",
                )

            with tab4:
                st.markdown(artifacts.get("email", "No email generated"))
                st.download_button(
                    "⬇️ Download Email (.txt)",
                    data=artifacts.get("email", ""),
                    file_name="kickoff_email.txt",
                    mime="text/plain",
                )

            # ZIP download — all four artifacts in one bundle
            st.divider()
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("ibm_placemat.md", artifacts.get("placemat", ""))
                zf.writestr("poc_checklist.md", artifacts.get("checklist", ""))
                zf.writestr("architecture_summary.md", artifacts.get("architecture", ""))
                zf.writestr("kickoff_email.txt", artifacts.get("email", ""))
                zf.writestr("discovery_extraction.json", json.dumps(data, indent=2))
            zip_buf.seek(0)
            st.download_button(
                "📦 Download all artifacts (.zip)",
                data=zip_buf,
                file_name="poc_artifacts.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary",
            )

            # TechZone environment request button (score ≥ 70 + known deployment env)
            if "readiness_score" in st.session_state:
                score = st.session_state["readiness_score"]["score"]
                cloud_provider = data.get("deployment_env", {}).get("cloud_provider", "Unknown")
                if score >= 70 and cloud_provider not in ("Unknown", "", None):
                    st.divider()
                    st.subheader("☁️ TechZone Environment")
                    st.info(
                        f"PoC readiness score is **{score}/100** and deployment environment is "
                        f"**{cloud_provider}** — this engagement is ready for a TechZone provisioning request."
                    )
                    col_tz, _ = st.columns([1, 2])
                    with col_tz:
                        if st.button(
                            "🚀 Request TechZone environment",
                            type="primary",
                            use_container_width=True,
                            help="Opens the TechZone request form — no auto-submission",
                        ):
                            st.session_state["show_techzone_form"] = True

                    if st.session_state.get("show_techzone_form"):
                        with st.form("techzone_request_form"):
                            st.markdown("**TechZone Request Details**")
                            tz_purpose = st.selectbox(
                                "Purpose",
                                ["Demo", "Education", "Test", "Pilot"],
                                index=2,
                            )
                            tz_notes = st.text_area(
                                "Additional notes",
                                placeholder="Any specific requirements or context for the TechZone team…",
                                height=100,
                            )
                            submitted = st.form_submit_button("✅ Confirm request", type="primary")
                            if submitted:
                                st.success(
                                    "✅ TechZone request details captured. "
                                    "Hand these off to your TechZone admin to complete provisioning."
                                )
                                st.json({
                                    "deployment_env": data.get("deployment_env", {}),
                                    "purpose": tz_purpose,
                                    "readiness_score": score,
                                    "notes": tz_notes,
                                })
                                st.session_state["show_techzone_form"] = False

            st.divider()

        # Display extracted fields in 2-column grid layout
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("👥 Stakeholders", expanded=False):
                if data.get("stakeholders"):
                    for s in data["stakeholders"]:
                        st.markdown(f"**{s.get('name', 'Unknown')}** — {s.get('role', 'N/A')} at {s.get('organization', 'N/A')}")
                else:
                    st.info("No stakeholders identified")

            with st.expander("🎯 Use Cases", expanded=False):
                if data.get("use_cases"):
                    for uc in data["use_cases"]:
                        st.markdown(f"**{uc.get('title', 'Untitled')}**")
                        st.markdown(f"_{uc.get('description', 'No description')}_")
                        st.markdown("---")
                else:
                    st.info("No use cases identified")

            with st.expander("🔗 Integrations", expanded=False):
                if data.get("integrations"):
                    for integ in data["integrations"]:
                        st.markdown(f"**{integ.get('system', 'Unknown system')}** — {integ.get('purpose', 'No purpose specified')}")
                else:
                    st.info("No integrations identified")
        
        with col2:
            with st.expander("☁️ Deployment Environment", expanded=False):
                env = data.get("deployment_env", {})
                st.markdown(f"**Cloud Provider:** {env.get('cloud_provider', 'Unknown')}")
                st.markdown(f"**Region:** {env.get('region', 'Unknown')}")
                if env.get("constraints"):
                    st.markdown(f"**Constraints:** {env.get('constraints')}")

            with st.expander("✅ Success Criteria", expanded=False):
                if data.get("success_criteria"):
                    for sc in data["success_criteria"]:
                        st.markdown(f"- {sc}")
                else:
                    st.warning("No success criteria defined")

            with st.expander("⚠️ Risks", expanded=False):
                if data.get("risks"):
                    for risk in data["risks"]:
                        severity = risk.get("severity", "Unknown")
                        emoji = "🔴" if severity == "High" else "🟡" if severity == "Medium" else "🟢"
                        st.markdown(f"{emoji} **{severity}:** {risk.get('risk', 'No description')}")
                else:
                    st.info("No risks identified")

            with st.expander("📋 Action Items", expanded=False):
                if data.get("action_items"):
                    for ai in data["action_items"]:
                        owner = ai.get("owner", "Unassigned")
                        task = ai.get("task", "No task description")
                        due = ai.get("due", "TBD")
                        st.markdown(f"- [ ] **{owner}** — {task} *(Due: {due})*")
                else:
                    st.info("No action items identified")

        # Download JSON report (only shown before artifacts are generated)
        if not st.session_state.get("confirmed"):
            st.divider()
            st.download_button(
                "⬇️ Download extraction (.json)",
                data=json.dumps(data, indent=2),
                file_name="discovery_extraction.json",
                mime="application/json",
            )


def render_demo_tab():
    """Render a static pre-baked demo walkthrough with hardcoded data — no LLM calls."""
    st.subheader("🎬 Demo Walkthrough")
    st.info("👀 This is a pre-baked demo showing the complete PoC analysis flow with instant results (no API calls).")
    
    st.divider()
    
    # Display sample transcript
    st.markdown("### 📝 Sample Meeting Notes")
    with st.expander("View meeting transcript", expanded=False):
        st.text(SAMPLE_TRANSCRIPT)
    
    st.divider()
    
    # Hardcoded extraction data
    demo_extraction = {
        "stakeholders": [
            {"name": "Sarah Chen", "role": "VP Digital Transformation", "organization": "Nexus Financial"},
            {"name": "Marcus Rowe", "role": "Enterprise Architect", "organization": "Nexus Financial"},
            {"name": "Priya Nair", "role": "IBM Client Engineer", "organization": "IBM"},
            {"name": "Tom Walsh", "role": "IBM Account Executive", "organization": "IBM"}
        ],
        "use_cases": [
            {
                "title": "HR Onboarding Assistant",
                "description": "Answer new-hire questions about benefits, policies, and IT setup. Integrate with Workday for employee data and SAP SuccessFactors for policy documents. Target: reduce onboarding time from 3-4 weeks to under 5 days."
            },
            {
                "title": "Employee Helpdesk Chatbot",
                "description": "Handle IT and HR tier-1 tickets, route complex issues to ServiceNow. Goal: reduce helpdesk call volume by 40%."
            }
        ],
        "integrations": [
            {"system": "Workday", "purpose": "Employee data retrieval for onboarding"},
            {"system": "SAP SuccessFactors", "purpose": "Policy document access"},
            {"system": "ServiceNow", "purpose": "Ticket routing for complex issues"},
            {"system": "Azure Active Directory", "purpose": "SSO authentication"}
        ],
        "deployment_env": {
            "cloud_provider": "Azure",
            "region": "West Europe",
            "constraints": "GDPR compliance required. All PII must stay in EU. Data residency guarantees needed."
        },
        "success_criteria": [
            "Onboarding assistant answers 80% of new-hire questions without human escalation",
            "Helpdesk chatbot deflects 40% of tier-1 tickets",
            "PoC delivered and demoed within 8 weeks"
        ],
        "risks": [
            {"risk": "GDPR data residency — all data must remain in EU", "severity": "High"},
            {"risk": "Azure AD integration complexity with conditional access policies", "severity": "Medium"},
            {"risk": "SAP SuccessFactors API rate limits may affect document retrieval", "severity": "Medium"},
            {"risk": "Previous AI vendor failure — leadership needs measurable ROI within 90 days", "severity": "High"}
        ],
        "action_items": [
            {"owner": "Priya Nair", "task": "Send watsonx.ai architecture proposal", "due": "July 22"},
            {"owner": "Marcus Rowe", "task": "Share Azure AD tenant details and SAP API credentials", "due": "July 19"},
            {"owner": "Sarah Chen", "task": "Confirm executive sponsor for PoC kickoff meeting", "due": "TBD"},
            {"owner": "Tom Walsh", "task": "Arrange TechZone environment provisioning on IBM Cloud, Frankfurt region", "due": "TBD"}
        ]
    }
    
    # Hardcoded readiness score
    demo_score = 87
    demo_breakdown = [
        {"item": "SAP Integration detected but no mitigation plan", "points": -5, "category": "Unmitigated Risk", "severity": "Medium"},
        {"item": "Azure AD integration complexity mentioned", "points": -5, "category": "Unmitigated Risk", "severity": "Medium"},
        {"item": "GDPR compliance risk flagged", "points": -3, "category": "Unmitigated Risk", "severity": "High"}
    ]
    demo_detected_risks = {
        "GDPR Compliance": ["gdpr", "data residency", "personal data"],
        "SAP Integration": ["sap"],
        "SSO/Identity Integration": ["azure ad", "azure active directory", "sso"]
    }
    
    # Hardcoded gap check
    demo_gaps = {
        "gaps": [
            {
                "field": "SSO/IdP Details",
                "issue": "Azure AD mentioned but no details on conditional access policies or MFA requirements",
                "question": "What specific Azure AD conditional access policies are in place? Is MFA required for all users?"
            },
            {
                "field": "SAP SuccessFactors API",
                "issue": "API rate limits mentioned as a risk but no current usage metrics provided",
                "question": "What are the current API rate limits for SAP SuccessFactors? How many documents need to be accessed per day?"
            }
        ],
        "readiness": "Ready",
        "summary": "Minor clarifications needed but PoC can proceed with current information"
    }
    
    # Display readiness score
    st.markdown("### 📊 PoC Readiness Score")
    st.success(f"**Score: {demo_score}/100** — Ready to proceed")
    st.progress(demo_score / 100)
    
    with st.expander("📉 Score breakdown", expanded=False):
        st.markdown("**Point deductions:**")
        for item in demo_breakdown:
            severity_emoji = "🔴" if item["severity"] == "High" else "🟡" if item["severity"] == "Medium" else "🟢"
            st.markdown(f"- {severity_emoji}{item['item']}: **{item['points']} points**")
    
    with st.expander(f"⚠️ Detected risks ({len(demo_detected_risks)} categories)", expanded=False):
        st.markdown("**Risk triggers found in meeting notes:**")
        for risk_category, keywords in demo_detected_risks.items():
            severity = get_risk_severity(risk_category)
            severity_emoji = "🔴" if severity == "High" else "🟡" if severity == "Medium" else "🟢"
            st.markdown(f"{severity_emoji} **{risk_category}** ({severity})")
            st.markdown(f"  - Keywords: {', '.join(keywords)}")
    
    st.divider()
    
    # Display gap check
    st.success(f"✅ **PoC Readiness:** {demo_gaps['readiness']} — {demo_gaps['summary']}")
    
    if demo_gaps["gaps"]:
        with st.expander("🔍 Missing or unclear information", expanded=False):
            st.markdown("**The following items need clarification before proceeding:**")
            for gap in demo_gaps["gaps"]:
                st.markdown(f"- **{gap['field']}:** {gap['issue']}")
                st.markdown(f"  - ❓ _{gap['question']}_")
    
    st.divider()
    
    # Display extracted data in columns
    st.markdown("### 📋 Extracted Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("👥 Stakeholders", expanded=False):
            for s in demo_extraction["stakeholders"]:
                st.markdown(f"**{s['name']}** — {s['role']} at {s['organization']}")
        
        with st.expander("🎯 Use Cases", expanded=False):
            for uc in demo_extraction["use_cases"]:
                st.markdown(f"**{uc['title']}**")
                st.markdown(f"_{uc['description']}_")
                st.markdown("---")
        
        with st.expander("🔗 Integrations", expanded=False):
            for integ in demo_extraction["integrations"]:
                st.markdown(f"**{integ['system']}** — {integ['purpose']}")
    
    with col2:
        with st.expander("☁️ Deployment Environment", expanded=False):
            env = demo_extraction["deployment_env"]
            st.markdown(f"**Cloud Provider:** {env['cloud_provider']}")
            st.markdown(f"**Region:** {env['region']}")
            st.markdown(f"**Constraints:** {env['constraints']}")
        
        with st.expander("✅ Success Criteria", expanded=False):
            for sc in demo_extraction["success_criteria"]:
                st.markdown(f"- {sc}")
        
        with st.expander("⚠️ Risks", expanded=False):
            for risk in demo_extraction["risks"]:
                severity = risk["severity"]
                emoji = "🔴" if severity == "High" else "🟡" if severity == "Medium" else "🟢"
                st.markdown(f"{emoji} **{severity}:** {risk['risk']}")
        
        with st.expander("📋 Action Items", expanded=False):
            for ai in demo_extraction["action_items"]:
                st.markdown(f"- [ ] **{ai['owner']}** — {ai['task']} *(Due: {ai['due']})*")
    
    st.divider()
    
    # Hardcoded artifact previews
    st.markdown("### 📄 Generated PoC Artifacts (Preview)")
    
    demo_placemat = """# IBM watsonx Discovery PoC — Nexus Financial

## Executive Summary
Nexus Financial is implementing AI-powered HR automation to reduce onboarding time from 3-4 weeks to under 5 days and deflect 40% of tier-1 helpdesk tickets.

## Stakeholders
- **Sarah Chen** — VP Digital Transformation, Nexus Financial
- **Marcus Rowe** — Enterprise Architect, Nexus Financial
- **Priya Nair** — IBM Client Engineer
- **Tom Walsh** — IBM Account Executive

## Business Objectives
Automate HR onboarding and employee support across 4,000 employees in Europe and North America.

## Use Cases
1. **HR Onboarding Assistant** — Answer new-hire questions about benefits, policies, and IT setup
2. **Employee Helpdesk Chatbot** — Handle IT and HR tier-1 tickets, route complex issues to ServiceNow

## Technical Architecture
- **Deployment:** Azure West Europe (GDPR compliant)
- **Integrations:** Workday, SAP SuccessFactors, ServiceNow, Azure AD
- **Authentication:** Azure Active Directory SSO

## Success Criteria
- 80% of new-hire questions answered without escalation
- 40% deflection of tier-1 tickets
- PoC delivered within 8 weeks

## Risks & Mitigation
- **High:** GDPR data residency → Deploy in EU region only
- **High:** Previous vendor failure → Weekly progress demos with measurable KPIs
- **Medium:** Azure AD complexity → Early integration testing
- **Medium:** SAP API rate limits → Implement caching strategy

## Next Steps
- Priya: Architecture proposal by July 22
- Marcus: Azure AD credentials by July 19
- Sarah: Confirm executive sponsor
- Tom: Provision TechZone environment (Frankfurt)
"""
    
    demo_checklist = """# watsonx PoC Checklist

## Pre-PoC Setup
- [ ] Stakeholder kickoff meeting scheduled
- [ ] Azure West Europe environment provisioned
- [ ] Azure AD SSO configured
- [ ] Workday API access obtained
- [ ] SAP SuccessFactors API credentials received
- [ ] ServiceNow integration endpoint configured

## Technical Requirements
- [ ] GDPR compliance review completed
- [ ] Data residency verification (EU only)
- [ ] Azure AD conditional access policies documented
- [ ] SAP API rate limit testing completed

## Use Case Implementation
- [ ] HR Onboarding Assistant prototype deployed
- [ ] Workday integration tested
- [ ] SAP SuccessFactors document retrieval working
- [ ] Employee Helpdesk Chatbot prototype deployed
- [ ] ServiceNow ticket routing configured

## Testing & Validation
- [ ] 80% question deflection rate validated
- [ ] 40% ticket deflection rate validated
- [ ] 8-week delivery timeline on track

## Risk Mitigation
- [ ] GDPR compliance audit passed
- [ ] Azure AD integration tested with conditional access
- [ ] SAP API caching implemented
- [ ] Weekly progress demos scheduled

## Documentation & Handoff
- [ ] Architecture documentation complete
- [ ] User guide created
- [ ] Handoff meeting scheduled
"""
    
    demo_architecture = """# Technical Architecture Summary

## Deployment Environment
- **Cloud Provider:** Azure
- **Region:** West Europe
- **Constraints:** GDPR compliance, EU data residency required

## Core Components
- watsonx.ai foundation models (LLM for conversational AI)
- watsonx.data (vector database for document retrieval)
- watsonx Assistant (orchestration layer)

## Integration Points
- **Workday:** Employee data retrieval via REST API
- **SAP SuccessFactors:** Policy document access via OData API
- **ServiceNow:** Ticket creation and routing via REST API
- **Azure AD:** SSO authentication via SAML 2.0

## Authentication & Security
- Azure Active Directory SSO with conditional access policies
- All data encrypted in transit (TLS 1.3) and at rest (AES-256)
- GDPR-compliant data handling with EU residency guarantees

## Data Flow
1. User authenticates via Azure AD
2. Query sent to watsonx Assistant
3. Assistant retrieves context from Workday/SAP via APIs
4. LLM generates response using retrieved context
5. Complex queries routed to ServiceNow for human handling

## Scalability Considerations
- Horizontal scaling for 4,000 concurrent users
- API rate limit management with caching layer
- Load balancing across Azure availability zones
"""
    
    demo_email = """Subject: watsonx Discovery PoC — Next Steps for Nexus Financial

Hi Sarah, Marcus,

Thank you for the productive discovery call on July 14. We're excited to partner with Nexus Financial on this AI-powered HR automation initiative.

**Key Takeaways:**
- Two primary use cases: HR Onboarding Assistant and Employee Helpdesk Chatbot
- Target: Reduce onboarding from 3-4 weeks to under 5 days
- Goal: Deflect 40% of tier-1 helpdesk tickets
- Deployment: Azure West Europe with GDPR compliance

**Next Steps:**
- Priya will send the watsonx.ai architecture proposal by July 22
- Marcus to share Azure AD tenant details and SAP API credentials by July 19
- Sarah to confirm executive sponsor for kickoff meeting
- Tom will arrange TechZone environment provisioning in Frankfurt

**Timeline:**
We're targeting an 8-week PoC delivery with weekly progress demos to ensure measurable ROI.

Looking forward to kicking off this engagement!

Best regards,
Priya Nair
IBM Client Engineer
"""
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 IBM Placemat",
        "✅ PoC Checklist",
        "🏗️ Architecture",
        "📧 Kickoff Email"
    ])
    
    with tab1:
        st.markdown(demo_placemat)
    
    with tab2:
        st.markdown(demo_checklist)
    
    with tab3:
        st.markdown(demo_architecture)
    
    with tab4:
        st.markdown(demo_email)
    
    st.divider()
    st.info("💡 **This is a static demo.** Switch to the 'PoC Analyzer' tab to analyze your own meeting notes with live watsonx API calls.")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Meeting Notes Analyzer",
        page_icon="🎙️",
        layout="wide",
    )

    st.title("🎙️ Meeting Notes Analyzer")

    if not check_env():
        st.stop()

    # Sidebar: Model selector and readiness score
    with st.sidebar:
        st.header("⚙️ Configuration")
        selected_model = st.selectbox(
            "🤖 Model",
            options=SUPPORTED_MODELS,
            index=SUPPORTED_MODELS.index(DEFAULT_MODEL),
            help="Select a watsonx text-generation model",
        )
        st.caption(f"Powered by IBM watsonx")
        st.caption(f"`{selected_model}`")
        
        # Display readiness score if available (analyzer tab only)
        if "readiness_score" in st.session_state and "extracted_data" in st.session_state:
            st.divider()
            st.header("📊 Readiness")
            score = st.session_state["readiness_score"]["score"]
            if score >= 80:
                st.success(f"**{score}/100**")
                st.caption("✅ Ready to proceed")
            elif score >= 60:
                st.warning(f"**{score}/100**")
                st.caption("⚠️ Needs clarification")
            else:
                st.error(f"**{score}/100**")
                st.caption("🚫 Significant gaps")
            st.progress(score / 100)

    analyzer_tab, demo_tab = st.tabs(["🔬 PoC Analyzer", "🎬 Demo"])

    with analyzer_tab:
        render_analyzer_tab(selected_model)

    with demo_tab:
        render_demo_tab()


if __name__ == "__main__":
    main()