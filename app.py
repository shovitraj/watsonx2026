import os
import io
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

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
        gap_data = json.loads(raw_response)
        return gap_data
    except json.JSONDecodeError:
        # Fallback if parsing fails
        return {
            "gaps": [],
            "readiness": "Needs clarification",
            "summary": "Unable to parse gap analysis response"
        }


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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Meeting Notes Analyzer",
        page_icon="🎙️",
        layout="wide",
    )

    st.title("🎙️ Meeting Notes Analyzer")

    selected_model = st.selectbox(
        "🤖 Model",
        options=SUPPORTED_MODELS,
        index=SUPPORTED_MODELS.index(DEFAULT_MODEL),
        help="Select a watsonx text-generation model",
    )
    st.caption(f"Powered by IBM watsonx · `{selected_model}`")

    if not check_env():
        st.stop()

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
        notes_text = st.text_area(
            "Paste your meeting notes here",
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
        with st.spinner("Extracting structured data from watsonx…"):
            try:
                import json
                raw_response = call_watsonx(
                    EXTRACTION_PROMPT.format(notes=notes_text),
                    model_id=selected_model,
                    max_new_tokens=2000
                )
                
                # Parse JSON response
                try:
                    extracted_data = json.loads(raw_response)
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

    # ── results ───────────────────────────────────────────────────────────────
    if "extracted_data" in st.session_state:
        st.divider()
        data = st.session_state["extracted_data"]
        
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
                with st.expander("🔍 Missing or unclear information", expanded=True):
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
        
        # Display extracted fields in expander cards
        with st.expander("👥 Stakeholders", expanded=True):
            if data.get("stakeholders"):
                for s in data["stakeholders"]:
                    st.markdown(f"**{s.get('name', 'Unknown')}** — {s.get('role', 'N/A')} at {s.get('organization', 'N/A')}")
            else:
                st.info("No stakeholders identified")
        
        with st.expander("🎯 Use Cases", expanded=True):
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
        
        # Download JSON report
        st.divider()
        report_json = json.dumps(data, indent=2)
        st.download_button(
            "⬇️ Download extraction (.json)",
            data=report_json,
            file_name="discovery_extraction.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
