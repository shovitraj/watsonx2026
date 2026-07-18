# 🎙️ Discovery PoC Orchestrator

A Streamlit app that uses **IBM watsonx** to analyse client meeting notes and generate a complete Discovery PoC package — readiness score, gap analysis, IBM Placemat, PoC checklist, architecture summary, and kickoff email.

Also ships as a **FastMCP server** so any MCP-capable agent can call the analysis tools directly.

## Features

- **🔬 PoC Analyzer tab** — paste or upload meeting notes, get structured extraction, gap check, readiness score (0–100), and four generated artifacts
- **🎬 Demo tab** — instant pre-baked walkthrough with no API calls (great for demos)
- **📦 ZIP download** — all four artifacts + raw JSON in one bundle
- **☁️ TechZone integration** — live environment provisioning request via TechZone MCP API (requires `TECHZONE_API_KEY`)
- **🤖 MCP server** — `mcp_server.py` exposes `analyze_notes`, `check_gaps`, `generate_artifacts` as MCP tools

---

## Quickstart

```bash
# 1. Clone and enter the repo
git clone https://github.com/shovitraj/watsonx2026.git
cd watsonx2026

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp .env.example .env
# then edit .env with your WATSONX_API_KEY and WATSONX_PROJECT_ID

# 4. Run
streamlit run app.py
```

App opens at **http://localhost:8501**.

---

## Detailed Setup

### Prerequisites

- Python 3.10 or later (`python --version`)
- An [IBM Cloud](https://cloud.ibm.com) account with a watsonx.ai project

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> If `pip` isn't on your PATH, use `pip3` or `python -m pip`.

### 2. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

| Variable | Required | Where to find it |
|---|---|---|
| `WATSONX_API_KEY` | ✅ | [IBM Cloud](https://cloud.ibm.com) → Manage → Access (IAM) → API keys |
| `WATSONX_PROJECT_ID` | ✅ | [watsonx.ai](https://dataplatform.cloud.ibm.com) → your project → Manage → General → Project ID |
| `WATSONX_URL` | optional | Default: `https://us-south.ml.cloud.ibm.com` — change for other regions (see below) |
| `TECHZONE_API_KEY` | optional | [techzone.ibm.com](https://techzone.ibm.com) → your profile → API keys |
| `TECHZONE_MCP_URL` | optional | Override TechZone MCP endpoint — default is pre-set, no change needed |

**watsonx.ai regions:**

| Region | URL |
|---|---|
| Dallas (default) | `https://us-south.ml.cloud.ibm.com` |
| Frankfurt | `https://eu-de.ml.cloud.ibm.com` |
| London | `https://eu-gb.ml.cloud.ibm.com` |
| Tokyo | `https://jp-tok.ml.cloud.ibm.com` |

### 3. Run the app

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**. Use **Ctrl+C** to stop.

### 4. Try it with the sample transcript

1. Open the **🔬 PoC Analyzer** tab
2. Click **📋 Load sample** — pre-fills a Nexus Financial / Azure / GDPR / SAP scenario
3. Click **🔍 Analyse** — runs extraction + gap check + readiness score (~15–30 s)
4. Review the score and gaps, then click **✅ Confirm and continue**
5. Four artifacts are generated (~30–60 s) — browse the tabs and download the ZIP

Or switch to the **🎬 Demo** tab for an instant pre-baked walkthrough with no API calls.

---

## MCP Server (optional)

Exposes the analysis pipeline as MCP tools for any MCP-compatible agent or client:

```bash
python mcp_server.py
```

Runs on **stdio** transport. Register it in your MCP client config (e.g. `.bob/mcp.json` or Claude Desktop):

```json
{
  "mcpServers": {
    "discovery-poc": {
      "command": "python",
      "args": ["/path/to/watsonx2026/mcp_server.py"],
      "env": {
        "WATSONX_API_KEY": "your-ibm-cloud-api-key",
        "WATSONX_PROJECT_ID": "your-watsonx-project-id"
      }
    }
  }
}
```

**Tools exposed:**

| Tool | Description |
|---|---|
| `analyze_notes(notes_text, model_id)` | Extract structured JSON from raw meeting notes |
| `check_gaps(extracted_json, model_id)` | Identify missing or vague fields; return readiness status |
| `generate_artifacts(extracted_json, model_id)` | Generate placemat, checklist, architecture summary, kickoff email |

---

## Project structure

```
watsonx2026/
├── app.py                 # Streamlit UI (two tabs: Analyzer + Demo)
├── mcp_server.py          # FastMCP server (stdio)
├── watsonx_helpers.py     # Shared watsonx client, prompts, analysis functions
├── risk_triggers.py       # Keyword → risk category mapping
├── requirements.txt       # Python dependencies
├── .env.example           # Credential template — copy to .env
└── loops/                 # Agentic build loop scripts (Bob Shell)
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: streamlit` | Run `pip install -r requirements.txt` first |
| `Missing environment variables` | Copy `.env.example` → `.env` and fill in credentials |
| `Failed to parse watsonx response as JSON` | Try a different model — Granite instruct models are most reliable |
| TechZone button not appearing | Score must be ≥ 70 and cloud provider must be detected (not "Unknown") |
| TechZone button shows info message | Add `TECHZONE_API_KEY` to `.env` |
