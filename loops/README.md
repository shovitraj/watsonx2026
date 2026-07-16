# Discovery PoC Orchestrator — Agentic Build Loop

This loop uses [IBM Bob Shell](https://bob.ibm.com) to autonomously evolve `app.py` from a basic Meeting Notes Analyzer into a full **Discovery PoC Orchestrator**, one task at a time, committing after every iteration.

## What the loop builds

Each iteration picks the next unchecked task from `loops/IMPLEMENTATION_PLAN.md` and implements it:

| Phase | What gets built |
|---|---|
| 1 | Structured JSON extraction (replaces free-text summary) |
| 2 | Gap check — LLM flags missing/vague fields with questions |
| 3 | Risk detection + PoC readiness score (0–100) |
| 4 | Artifact tabs: IBM Placemat · PoC Checklist · Architecture · Kickoff email |
| 5 | ZIP download · sample transcript button · TechZone provision button |

**Done condition**: no `- [ ]` items remain in `loops/IMPLEMENTATION_PLAN.md`.

---

## Prerequisites

1. Copy the environment template and fill in your values:
   ```sh
   cp .bob/skills/generate-loop/assets/.env-template .env
   ```

2. Edit `.env` and set `BOBSHELL_API_KEY` (get it from https://bob.ibm.com/admin/apikeys).

3. Start the loop:
   - macOS / Linux: `bash loops/loop.sh`
   - Windows:       `.\loops\loop.ps1`

---

## Resuming after a stop

The loop commits after every iteration. If it stops (max iterations reached or error), just run it again — it reads the plan and picks up from the next unchecked task.

## Checking progress

```sh
cat loops/IMPLEMENTATION_PLAN.md   # see which tasks are done
cat loops/PROGRESS.md              # see what each iteration did
git log --oneline                  # see all iteration commits
```
