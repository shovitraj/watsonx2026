# Project Coding Rules (Non-Obvious Only)

This workspace is currently empty. Add rules here as the project is built.

## Patterns to enforce when code exists

- **MCP + FastAPI lifespan ordering** — `FastMCP()` before `FastAPI()`, always
- **Service return types** — Return `ModelOut | ErrorResponse`; never raise HTTP exceptions from service layer
- **MCP tool DB sessions** — No `Depends()`; use manual `try/finally` with `SessionLocal()`
- **Test DB patching** — Patch both `db_module.SessionLocal` and `server.SessionLocal` when mocking the database in tests
- **Vite env** — `import.meta.env.VITE_*`, never `process.env.*`
