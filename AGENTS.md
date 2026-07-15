# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Status

This workspace (`watsonx2026`) is currently **empty**. Update this file once the project stack is established.

---

## IBM Bob / watsonx Ecosystem Conventions

Based on sibling projects in this environment, IBM Bob demo/lab projects in this workspace typically follow these non-obvious patterns:

### Python/FastAPI + MCP pattern (if applicable)
- **MCP server must be instantiated before FastAPI app** — `mcp = FastMCP()` must precede `app = FastAPI()` to properly combine lifespans
- **Service functions return Union types** — `ModelOut | ErrorResponse`, not exceptions. Always check `isinstance(result, ErrorResponse)` before using the result
- **MCP tool database sessions** — No dependency injection; manually create/close with `SessionLocal()` and `db.close()` in try/finally blocks
- **Tests patch two SessionLocal paths** — Both `db_module.SessionLocal` AND `server.SessionLocal` due to import timing

### React/TypeScript + Vite pattern (if applicable)
- **Env vars use `import.meta.env.VITE_*`** — Not `process.env.*`
- **API endpoints at root path** — No `/api` prefix; routes are `/resource`, not `/api/resource`
- **Error response shape** — `{ success: false, error, error_code, details }`; use an `isErrorResponse()` helper to check

### Commands

```bash
# Python backend (FastAPI)
python server.py                    # Runs on port 8080, auto-seeds DB
pytest                              # Run all tests
pytest tests/test_services.py       # Run a single test file
pytest tests/test_services.py::test_name  # Run a single test

# React frontend (Vite)
npm run dev                         # Dev server (port 5173)
npm run build                       # Production build
npm run lint                        # ESLint check
```

### MCP Servers
- Each MCP server is self-contained in its own directory under `servers/` or `mcp_servers/`
- Use `FastMCP` from the `mcp` package (not raw `anyio` transports)
- Servers expose tools as Python functions decorated with `@mcp.tool()`

---

*Update this file with project-specific non-obvious patterns as the codebase grows.*
