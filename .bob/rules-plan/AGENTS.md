# Project Architecture Rules (Non-Obvious Only)

## Architecture Overview

This is a **single-process Streamlit application** with no backend server, no database, and no API layer. All logic — LLM calls, file parsing, risk detection, scoring — runs in the Streamlit process.

```
app.py  ←→  ibm_watsonx_ai (ModelInference)
  └─ risk_triggers.py  (pure module, no I/O)
```

The loop system (`loops/`) is a separate concern — a bash outer loop that drives Bob Shell to evolve `app.py` iteratively. It does not run alongside the app.

---

## Architectural Constraints

### Single-file app — no new modules without strong reason
All Streamlit UI, prompts, watsonx calls, and file parsers live in `app.py`. The only split-out module is `risk_triggers.py`, which is pure Python with no I/O. Before creating a new file, ask whether it is genuinely a separate concern. Do not create a `services.py`, `utils.py`, or `config.py` — keep things in `app.py`.

### No backend server — Streamlit IS the server
There is no FastAPI, Flask, or any HTTP server. Do not add one. File parsing, LLM calls, and scoring happen synchronously in the Streamlit request-response cycle (inside `st.spinner` blocks for UX).

### Stateless between reruns — all state goes in `st.session_state`
Streamlit reruns `app.py` top-to-bottom on every user interaction. Any value that must survive a rerun (extracted data, artifacts, scores, confirmation status) must be stored in `st.session_state`. Never use module-level mutable variables for per-session state.

### LLM calls are sequential, not concurrent
`generate_artifacts()` makes four watsonx calls in sequence (placemat → checklist → architecture → email). Parallelism would complicate error handling and Streamlit spinner UX. Do not convert to `asyncio` or `ThreadPoolExecutor` without explicit product intent.

### `risk_triggers.py` must stay pure
`risk_triggers.py` has no imports beyond the standard library. It must not import `streamlit`, `ibm_watsonx_ai`, or any external package. Keep it as a data module with two helper functions.

### Credentials via environment variables only
`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, and `WATSONX_URL` are loaded from `.env` via `python-dotenv`. Never hardcode credentials. `check_env()` gates the app startup — it must remain as the first guard in `main()` after page config.

### Loop and app are independent concerns
`loops/` is a build-time automation layer. It does not affect how the app runs. The loop reads `loops/IMPLEMENTATION_PLAN.md` for unchecked tasks and evolves `app.py` one task at a time. Do not entangle loop state (e.g. `PROGRESS.md`) with runtime app state.

### Supported models list is curated, not auto-discovered
`SUPPORTED_MODELS` in `app.py` is a manually maintained list of text-generation models. Do not auto-discover models from the watsonx API — the list intentionally excludes embedding, reranker, and TTM models that cannot generate text.

---

## Data Flow (Analysis Pipeline)

```
User input (paste / upload)
  → extract_text()              # file → plain str
  → EXTRACTION_PROMPT           # str → structured JSON (via call_watsonx + _extract_json)
  → check_gaps()                # JSON → gap list + readiness verdict
  → calculate_readiness_score() # JSON + raw text → score (0–100) + breakdown
  → [user confirms]
  → generate_artifacts()        # JSON → 4 × markdown/text artifacts
  → ZIP download + TechZone button
```

Each step stores its output in `st.session_state` and re-uses it on reruns. Steps never re-execute unless the user starts a new analysis.

---

## Loop Architecture

```
loops/loop.sh
  └─ loops/iteration.sh         # runs one Bob Shell call per iteration
       └─ loops/prompt.md       # agent instruction: read plan, pick next task, implement, stop
            └─ loops/IMPLEMENTATION_PLAN.md  # checklist of tasks (- [ ] / - [x])
            └─ loops/PROGRESS.md             # append-only iteration log
```

**Done condition**: no `- [ ]` items in `IMPLEMENTATION_PLAN.md`.  
**Max iterations**: 20 (configurable in `loop.sh`).  
Each iteration commits its changes to git.
