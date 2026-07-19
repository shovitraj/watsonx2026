# Project Coding Rules (Non-Obvious Only)

## Stack

- **Frontend/app**: Streamlit (`app.py`) — single-file app, no separate backend
- **LLM layer**: `ibm_watsonx_ai` — `ModelInference` via `get_watsonx_client()` / `call_watsonx()`
- **Risk module**: `risk_triggers.py` — keyword dict + two pure functions, no state
- **File parsers**: `parse_txt`, `parse_docx`, `parse_pdf` in `app.py` — all return plain `str`
- **Loop driver**: `loops/loop.sh` + `loops/iteration.sh` — bash outer loop calling Bob Shell

---

## Non-Obvious Coding Patterns

### JSON extraction — always use `_extract_json()` before `json.loads()`
The watsonx model may wrap JSON in prose or truncate it. Never call `json.loads(raw_response)` directly — always go through `_extract_json(raw_response)` first, which strips preamble and attempts to repair truncation by walking closing-brace positions.

### `call_watsonx` — `max_new_tokens` is caller-controlled, not default
Different calls set different token budgets: extraction=4000, gap check=1000, artifacts=800–2000. Never change the default (800) without checking caller intent. Do not add streaming; the app uses `generate_text()`, not `generate_text_stream()`.

### Streamlit session state keys — fixed set, always cleared together
The five state keys (`extracted_data`, `gap_check`, `readiness_score`, `artifacts`, `confirmed`) form an atomic unit. Whenever a new analysis starts OR the sample is loaded, ALL five must be popped. Adding a new key that participates in the analysis flow must be added to that clear-list in both places (Analyse button handler and sample-load handler).

### Gated artifact generation — `confirmed` key is the gate
`generate_artifacts()` must only be called when `st.session_state.get("confirmed")` is `True`. Never move artifact generation before the confirmation button. The gate exists to let the user review extracted data and gap checks before spending 4 × LLM calls.

### `detect_risks()` is case-insensitive via `text.lower()` — keywords must be lowercase
All keys in `RISK_TRIGGERS` must be lowercase. The detector converts the input to lowercase once and does `in` substring matching. Do not use regex here; the design is intentionally simple.

### `calculate_readiness_score()` deducts, never adds
The score starts at 100 and only goes down. Never add bonus points. The floor is `max(0, score)`. Cross-referencing detected risks with extracted risks uses lowercase `in` substring matching — do not change to exact equality.

### Prompts use `<|system|>` / `<|user|>` / `<|assistant|>` chat format
All prompts in `app.py` follow the Granite/Llama instruct chat template. New prompts must follow the same pattern. `{notes}` and `{extracted_json}` are the only `.format()` placeholders — keep them.

### ZIP download bundles all four artifacts + raw JSON
`poc_artifacts.zip` always contains: `ibm_placemat.md`, `poc_checklist.md`, `architecture_summary.md`, `kickoff_email.txt`, `discovery_extraction.json`. If a new artifact is added, it must be added to the ZIP as well.

### TechZone button — conditions are score ≥ 70 AND known cloud_provider
The button only renders when both conditions are true. Do not relax either threshold without product intent. The form uses `st.form` to prevent reruns on every widget interaction.

---

## Commands

```bash
# Run the app
streamlit run app.py

# Run the agentic loop (picks next unchecked task from loops/IMPLEMENTATION_PLAN.md)
bash loops/loop.sh

# Install dependencies
pip install -r requirements.txt
```

---

## File Roles

| File | Purpose |
|---|---|
| `app.py` | Entire Streamlit app — UI, prompts, watsonx calls, parsers |
| `risk_triggers.py` | Pure keyword→risk mapping; `detect_risks()` and `get_risk_severity()` |
| `requirements.txt` | Python deps — update only when a task genuinely requires a new package |
| `loops/IMPLEMENTATION_PLAN.md` | Task checklist — mark `- [ ]` → `- [x]` after each iteration |
| `loops/PROGRESS.md` | Append-only progress log — one entry per loop iteration |
| `loops/prompt.md` | Loop agent prompt — do not edit during a loop run |
