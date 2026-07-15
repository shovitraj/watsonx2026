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

SUMMARY_PROMPT = """\
<|system|>
You are a world-class meeting analyst and executive communicator. Your job is to transform raw \
meeting notes into a sharp, insightful summary that a senior executive can act on in 60 seconds.

Follow this exact structure — do not add extra sections:

## 🗂 Overview
Write 2–3 crisp sentences capturing the meeting's purpose, who was involved, and the single most \
important outcome or unresolved tension. Be direct — no filler phrases like "the team discussed".

## 💬 Key Discussion Points
List the most substantive topics raised. For each point:
- Lead with the **topic** in bold
- Follow with one sentence of context or the core argument made
- Include any notable disagreements, risks, or trade-offs surfaced
- Aim for 3–6 bullets; skip small talk and logistics

## ✅ Decisions Made
List every explicit decision or commitment reached. If a decision has a clear owner or deadline, \
include it inline. If no decisions were made, write: *No decisions recorded.*

## ⚠️ Risks & Open Questions
Call out anything unresolved, blocked, or flagged as a concern — even if briefly mentioned. \
If nothing was flagged, write: *None identified.*

Rules:
- Use plain, confident language. No corporate jargon or padding.
- If information for a section is genuinely absent from the notes, say so briefly — do not invent.
- Output only the structured summary. No preamble, no sign-off.
<|user|>
Meeting notes:
{notes}
<|assistant|>
"""

ACTION_ITEMS_PROMPT = """\
<|system|>
You are a world-class meeting analyst specialising in accountability and follow-through. \
Your job is to extract every commitment, task, and follow-up from the meeting notes and \
present them in a format a project manager can immediately drop into a tracker.

For each action item output a line in this exact format:
- [ ] **[Owner]** — Task description *(Due: date or "TBD")*

Guidelines:
- **Owner**: use the person's name if mentioned; otherwise write *Unassigned*
- **Task**: be specific — include enough context so the owner knows exactly what to do \
without re-reading the notes
- **Due date**: use the exact date or phrase from the notes; if none given, write *TBD*
- If an action item implies a demo, proof-of-concept, or product showcase, append the \
tag `#demo` at the end of that line
- Group items by owner if there are 4 or more items; otherwise list chronologically
- If no action items are present, respond with exactly: *No action items identified.*

Rules:
- Do not invent tasks — only extract what was explicitly stated or clearly implied
- Do not include vague statements like "we should look into this" unless a person was assigned
- Output only the action item list. No preamble, no sign-off.
<|user|>
Meeting notes:
{notes}
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
        with st.spinner("Contacting watsonx…"):
            try:
                summary = call_watsonx(SUMMARY_PROMPT.format(notes=notes_text), model_id=selected_model)
                actions = call_watsonx(ACTION_ITEMS_PROMPT.format(notes=notes_text), model_id=selected_model)
                st.session_state["summary"] = summary
                st.session_state["actions"] = actions
            except Exception as e:
                st.error(f"watsonx error: {e}")
                st.stop()

    # ── results ───────────────────────────────────────────────────────────────
    if "summary" in st.session_state and "actions" in st.session_state:
        st.divider()
        render_results(st.session_state["summary"], st.session_state["actions"])

        # download combined report
        report = (
            "# Meeting Analysis Report\n\n"
            "## Summary\n\n" + st.session_state["summary"] + "\n\n"
            "## Action Items\n\n" + st.session_state["actions"]
        )
        st.download_button(
            "⬇️ Download report (.md)",
            data=report,
            file_name="meeting_report.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
