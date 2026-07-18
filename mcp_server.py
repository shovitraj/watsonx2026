"""
mcp_server.py — FastMCP server exposing the Discovery PoC Orchestrator tools.

Run locally (stdio transport, works with any MCP client):
    python mcp_server.py

Tools exposed:
    analyze_notes(notes_text, model_id)     — extract structured JSON from meeting notes
    check_gaps(extracted_json, model_id)    — gap analysis on extracted data
    generate_artifacts(extracted_json, model_id) — generate placemat, checklist, architecture, email
"""

import json

from fastmcp import FastMCP
from watsonx_helpers import (
    DEFAULT_MODEL,
    analyze_notes as _analyze_notes,
    check_gaps as _check_gaps,
    generate_artifacts as _generate_artifacts,
)

mcp = FastMCP(
    name="discovery-poc-orchestrator",
    instructions=(
        "Tools for IBM watsonx Discovery PoC analysis. "
        "Use analyze_notes first, then check_gaps, then generate_artifacts."
    ),
)


@mcp.tool()
def analyze_notes(notes_text: str, model_id: str = DEFAULT_MODEL) -> str:
    """
    Extract structured data from client meeting notes.

    Args:
        notes_text: Raw meeting notes text (paste or transcription).
        model_id:   watsonx model ID to use (defaults to llama-3-3-70b-instruct).

    Returns:
        JSON string with fields: stakeholders, use_cases, integrations,
        deployment_env, success_criteria, risks, action_items.
    """
    result = _analyze_notes(notes_text, model_id=model_id)
    return json.dumps(result, indent=2)


@mcp.tool()
def check_gaps(extracted_json: str, model_id: str = DEFAULT_MODEL) -> str:
    """
    Identify missing or vague fields in extracted meeting data.

    Args:
        extracted_json: JSON string from analyze_notes output.
        model_id:       watsonx model ID to use.

    Returns:
        JSON string with fields: gaps (list), readiness (Ready/Needs clarification/Blocked), summary.
    """
    try:
        data = json.loads(extracted_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})
    result = _check_gaps(data, model_id=model_id)
    return json.dumps(result, indent=2)


@mcp.tool()
def generate_artifacts(extracted_json: str, model_id: str = DEFAULT_MODEL) -> str:
    """
    Generate all four PoC artifacts from extracted meeting data.

    Args:
        extracted_json: JSON string from analyze_notes output.
        model_id:       watsonx model ID to use.

    Returns:
        JSON string with fields: placemat, checklist, architecture, email (all markdown strings).
    """
    try:
        data = json.loads(extracted_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON input: {e}"})
    result = _generate_artifacts(data, model_id=model_id)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
