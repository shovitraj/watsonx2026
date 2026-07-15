#!/usr/bin/env bash
# iteration.sh — runs one Bob Shell iteration for the Discovery PoC Orchestrator loop
#
# Usage: bash loops/iteration.sh [ITERATION_NUMBER]

# Re-exec under bash if invoked via plain sh (e.g. "sh loops/iteration.sh")
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

# ── Resolve repo root ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ITERATION="${1:-}"
PROMPT_FILE="$REPO_ROOT/loops/prompt.md"
PLAN_FILE="$REPO_ROOT/loops/IMPLEMENTATION_PLAN.md"

# ── Setup Bob Shell ───────────────────────────────────────────────────────────
source "$REPO_ROOT/.bob/skills/generate-loop/scripts/setup.sh" --env-file "$REPO_ROOT/.env"

# ── Git setup ─────────────────────────────────────────────────────────────────
git config --global --add safe.directory "$REPO_ROOT" 2>/dev/null || true

# ── Ensure git repo exists ────────────────────────────────────────────────────
if [ ! -d "$REPO_ROOT/.git" ]; then
    echo "No .git found — initialising repository"
    git -C "$REPO_ROOT" init
    git -C "$REPO_ROOT" add .
    git -C "$REPO_ROOT" commit -m "Initial commit" --allow-empty
fi

# ── Determine iteration number ────────────────────────────────────────────────
if [ -z "$ITERATION" ]; then
    LAST_COMMIT=$(git -C "$REPO_ROOT" log --all --grep="PoC Orchestrator Iteration" --format="%s" -n 1 2>/dev/null || true)
    if [ -n "$LAST_COMMIT" ]; then
        LAST_NUM=$(echo "$LAST_COMMIT" | grep -oE '[0-9]+$' || true)
        if [ -n "$LAST_NUM" ]; then
            ITERATION=$((LAST_NUM + 1))
        else
            ITERATION=1
        fi
    else
        ITERATION=1
    fi
fi
echo "--- Iteration $ITERATION ---"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [ ! -f "$PROMPT_FILE" ]; then
    echo "Error: prompt file not found at $PROMPT_FILE"
    exit 1
fi
if [ ! -f "$PLAN_FILE" ]; then
    echo "Error: implementation plan not found at $PLAN_FILE"
    exit 1
fi

# ── Run Bob ───────────────────────────────────────────────────────────────────
cd "$REPO_ROOT"

BOB_OUTPUT=$(cat "$PROMPT_FILE" | bob \
    --auth-method api-key \
    --accept-license \
    --sandbox \
    --yolo \
    --allowed-tools read_file,write_todos,write_to_file,run_shell_command \
    --output-format=stream-json)
echo "$BOB_OUTPUT"

# ── Usage summary ─────────────────────────────────────────────────────────────
LAST_LINE=$(echo "$BOB_OUTPUT" | tail -n 1)
INPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.input_tokens // "n/a"')
OUTPUT_TOKENS=$(echo "$LAST_LINE" | jq -r '.usage.output_tokens // "n/a"')
BOB_COINS=$(echo "$LAST_LINE"   | jq -r '.usage.bob_coins     // "n/a"')
echo ""
echo "📊 Iteration $ITERATION usage — input tokens: $INPUT_TOKENS | output tokens: $OUTPUT_TOKENS | bobcoins: $BOB_COINS"

# ── Commit changes ────────────────────────────────────────────────────────────
git -C "$REPO_ROOT" add .
git -C "$REPO_ROOT" commit -m "PoC Orchestrator Iteration $ITERATION" --allow-empty
