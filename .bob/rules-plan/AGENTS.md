# Project Architecture Rules (Non-Obvious Only)

This workspace is currently empty. Add architectural constraints here as the project is designed.

## Constraints common to this IBM Bob environment

- **MCP servers must be stateless** — No in-memory state between tool calls; use DB or file persistence
- **FastAPI + MCP lifespan coupling** — The combined lifespan pattern requires MCP to be instantiated first (hidden dependency)
- **Frontend/backend split** — Backend on :8080, frontend dev on :5173; CORS must be configured explicitly
- **DB seeds on startup** — Auto-seed functions run at app startup; disable via monkeypatch in tests to avoid state pollution
- **No rollback migrations** — If using Alembic, design forward-only migrations from the start
