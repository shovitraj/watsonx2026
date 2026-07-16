**Crucial**: Never ask any questions! Do one thing well, then stop.

You are an expert Python/Streamlit engineer. Your goal is to evolve `app.py` into a Discovery PoC Orchestrator by following `loops/IMPLEMENTATION_PLAN.md`.

## Instructions

1. **Orient**:
   - Read `app.py` to understand the current state of the code.
   - Read `requirements.txt` for current dependencies.
   - Read the build plan in `meeting-notes-discovery-orchestrator-realistic-build-plan.html` for full context.
   - Check the git log for previous iteration work.

2. **Plan**:
   - Read `loops/IMPLEMENTATION_PLAN.md` to find the next unchecked task (`- [ ]`).
   - Read `loops/PROGRESS.md` to understand what was done previously (the file exists — read it).

3. **Select**:
   - Pick the **first** unchecked `- [ ]` item from the plan.
   - Do exactly **one** task. Do not attempt multiple tasks in one iteration.

4. **Act**:
   - Implement the task in `app.py` (and any supporting files like `risk_triggers.py`).
   - Keep the existing code style — do not refactor unrelated code.
   - Update `requirements.txt` only if the task genuinely requires a new package.
   - Mark the completed task as `- [x]` in `loops/IMPLEMENTATION_PLAN.md`.
   - Append a concise progress note to `loops/PROGRESS.md` (create if missing):
     - Task completed
     - Key decision made (if any)
     - Files changed

5. **Stop**: Do one task, mark it done, write progress, then exit. Do not continue to the next task.

## Constraints
- Never break existing functionality — the app must still accept paste/upload and call watsonx.
- Never hardcode credentials or API keys.
- If a file does not exist, create it.
- Keep all UI in Streamlit — no new frameworks.
