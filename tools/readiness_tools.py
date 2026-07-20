"""
readiness_tools.py — watsonx Orchestrate ADK tools for the Readiness Agent.

Tools:
    calculate_readiness_score   — rules-based score from extracted meeting data
    list_techzone_environments  — list active TechZone reservations
    get_techzone_environment    — get details of a specific reservation
    provision_techzone_env      — provision a new TechZone environment
"""

import json
import os
from datetime import datetime, timezone

import httpx
from ibm_watsonx_orchestrate.agent_builder.tools import tool

# ── TechZone auth ─────────────────────────────────────────────────────────────

TECHZONE_MCP_URL = os.getenv(
    "TECHZONE_MCP_URL",
    "https://mcp.techzone.ibm.com/servers/c7442b81221647c3b36c75df4f2f88e8/mcp",
)


def _get_jwt() -> str:
    """Read TechZone JWT from itz CLI config or env override."""
    key = os.getenv("TECHZONE_API_KEY", "")
    if key:
        return key
    try:
        import yaml
        with open(os.path.expanduser("~/.itz/cli-config.yaml")) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("techzone", {}).get("api", {}).get("token", "")
    except Exception:
        return ""


def _call_techzone_mcp(tool_name: str, arguments: dict) -> dict:
    """Call a tool on the IBM-hosted TechZone MCP server via JSON-RPC."""
    jwt = _get_jwt()
    if not jwt:
        return {"error": "No TechZone token — run `itz login` in terminal"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": {**arguments, "bearerToken": jwt},
        },
    }
    try:
        response = httpx.post(
            TECHZONE_MCP_URL,
            json=payload,
            headers={
                "TechZone-Token": jwt,
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("result", {}).get("content", [{}])
        text = content[0].get("text", "") if content else ""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"raw": text}
    except Exception as e:
        return {"error": str(e)}


# ── Tool 1: Calculate readiness score ─────────────────────────────────────────

@tool
def calculate_readiness_score(extracted_json: str) -> str:
    """
    Calculate a PoC readiness score (0-100) from extracted meeting data.

    Uses a rules engine — no LLM call needed. Scores based on completeness
    of stakeholders, use cases, integrations, deployment env, success criteria,
    risks and action items.

    Args:
        extracted_json: JSON string output from the Extraction Agent's
                        extract_requirements tool.

    Returns:
        JSON string with fields: score (int), grade (str), breakdown (dict),
        missing_fields (list), recommendation (str).
    """
    try:
        data = json.loads(extracted_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid JSON input"})

    score = 0
    breakdown = {}
    missing = []

    # Stakeholders (15 pts)
    stakeholders = data.get("stakeholders", [])
    if len(stakeholders) >= 2:
        breakdown["stakeholders"] = 15
        score += 15
    elif len(stakeholders) == 1:
        breakdown["stakeholders"] = 8
        score += 8
    else:
        breakdown["stakeholders"] = 0
        missing.append("Stakeholders not identified")

    # Use cases (20 pts)
    use_cases = data.get("use_cases", [])
    if len(use_cases) >= 2:
        breakdown["use_cases"] = 20
        score += 20
    elif len(use_cases) == 1:
        breakdown["use_cases"] = 10
        score += 10
    else:
        breakdown["use_cases"] = 0
        missing.append("No use cases defined")

    # Integrations (15 pts)
    integrations = data.get("integrations", [])
    if integrations:
        breakdown["integrations"] = 15
        score += 15
    else:
        breakdown["integrations"] = 0
        missing.append("No integrations identified")

    # Deployment environment (15 pts)
    env = data.get("deployment_env", {})
    cloud = env.get("cloud_provider", "Unknown")
    if cloud not in ("Unknown", "", None):
        breakdown["deployment_env"] = 15
        score += 15
    else:
        breakdown["deployment_env"] = 0
        missing.append("Deployment environment unknown")

    # Success criteria (20 pts)
    criteria = data.get("success_criteria", [])
    if len(criteria) >= 2:
        breakdown["success_criteria"] = 20
        score += 20
    elif len(criteria) == 1:
        breakdown["success_criteria"] = 10
        score += 10
    else:
        breakdown["success_criteria"] = 0
        missing.append("No success criteria defined")

    # Risks identified (10 pts)
    risks = data.get("risks", [])
    if risks:
        breakdown["risks"] = 10
        score += 10
    else:
        breakdown["risks"] = 0
        missing.append("No risks identified")

    # Action items (5 pts)
    actions = data.get("action_items", [])
    if actions:
        breakdown["action_items"] = 5
        score += 5
    else:
        breakdown["action_items"] = 0
        missing.append("No action items defined")

    # Grade
    if score >= 85:
        grade = "Ready for PoC"
    elif score >= 70:
        grade = "Almost Ready — minor gaps"
    elif score >= 50:
        grade = "Needs Clarification"
    else:
        grade = "Blocked — critical gaps"

    # Recommendation
    if score >= 70:
        recommendation = (
            f"Score {score}/100 — {grade}. "
            f"Recommend proceeding with TechZone environment provisioning."
        )
    else:
        recommendation = (
            f"Score {score}/100 — {grade}. "
            f"Address missing fields before provisioning: {', '.join(missing[:3])}."
        )

    return json.dumps({
        "score": score,
        "grade": grade,
        "breakdown": breakdown,
        "missing_fields": missing,
        "recommendation": recommendation,
        "techzone_eligible": score >= 70,
    }, indent=2)


# ── Tool 2: List TechZone environments ────────────────────────────────────────

@tool
def list_techzone_environments(status: str = "Ready") -> str:
    """
    List active TechZone reservations for the authenticated user.

    Args:
        status: Filter by status — "Ready", "Provision", "Failed", or "" for all.

    Returns:
        JSON string with list of reservations including name, status, end date,
        environment names, and reservation IDs.
    """
    args = {"limit": 10, "expired": False}
    if status:
        args["status"] = status

    result = _call_techzone_mcp("request-mcp-techzone-list-requests", args)

    if isinstance(result, list):
        summary = []
        for r in result:
            summary.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "status": r.get("status"),
                "infrastructure": r.get("infrastructure"),
                "ends": r.get("schedule", {}).get("end", "?"),
                "environments": [
                    {"name": e.get("name"), "status": e.get("status")}
                    for e in r.get("environments", [])
                ],
            })
        return json.dumps(summary, indent=2)

    return json.dumps(result, indent=2)


# ── Tool 3: Get environment details ───────────────────────────────────────────

@tool
def get_techzone_environment(reservation_id: str) -> str:
    """
    Get full details of a specific TechZone reservation by ID.

    Args:
        reservation_id: The TechZone reservation ID
                        (e.g. 6a5a8450dc3b1311fe5e326c).

    Returns:
        JSON string with full reservation details including service links,
        credentials, VM info, and status.
    """
    result = _call_techzone_mcp(
        "request-mcp-techzone-get-request",
        {"requestId": reservation_id}
    )
    return json.dumps(result, indent=2)


# ── Tool 4: Provision TechZone environment ────────────────────────────────────

@tool
def provision_techzone_env(
    platform_id: str,
    purpose: str = "Test",
    geography: str = "americas",
    start: str = "",
) -> str:
    """
    Provision a new TechZone environment for a PoC.

    Automatically triggered when readiness score >= 70. Submits a reservation
    request to the IBM-hosted TechZone MCP server.

    Args:
        platform_id:  TechZone platform ID to provision
                      (e.g. 69caed724b629d96da28b7a3 for watsonx Orchestrate).
        purpose:      One of: Demo, Education, Event, Pilot, Test.
                      Defaults to "Test".
        geography:    Region preference — "americas", "europe", or "asia".
                      Defaults to "americas".
        start:        Start time in ISO 8601 UTC format
                      (e.g. 2026-07-21T09:00:00Z).
                      Defaults to now if not provided.

    Returns:
        JSON string with reservation ID, status, and environment details.
    """
    if not start:
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = _call_techzone_mcp(
        "request-mcp-techzone-create-request",
        {
            "platformId": platform_id,
            "purpose": purpose,
            "geography": geography,
            "start": start,
        },
    )
    return json.dumps(result, indent=2)
