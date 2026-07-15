# 🎙️ Meeting Notes Analyzer

A Streamlit app that uses **IBM watsonx · Granite 3 8B Instruct** to generate a structured summary and extract action items from meeting notes.

## Features

- **Paste text** directly into a text area
- **Upload** `.txt`, `.docx`, or `.pdf` files
- Generates a **summary** (overview, key points, decisions)
- Extracts **action items** with owner and due date when present
- **Download** the combined report as a Markdown file

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to find it |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud → Manage → API keys |
| `WATSONX_PROJECT_ID` | watsonx.ai → Project → Manage → General |
| `WATSONX_URL` | Default: `https://us-south.ml.cloud.ibm.com` (change region if needed) |

### 3. Run

```bash
streamlit run app.py
```

App opens at `http://localhost:8501`.

## Model

Uses `ibm/granite-3-8b-instruct` via the `ibm-watsonx-ai` SDK. Swap the `model_id` in [`app.py`](app.py) to use a different model (e.g. `ibm/granite-13b-chat-v2`, `meta-llama/llama-3-1-70b-instruct`).
