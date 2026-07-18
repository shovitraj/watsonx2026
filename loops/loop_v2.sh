#!/usr/bin/env bash
# loop_v2.sh — outer loop for Discovery PoC Orchestrator UI Refresh (V2)
#
# Usage: bash loops/loop_v2.sh
# Runs Bob Shell iterations until all tasks in IMPLEMENTATION_PLAN_V2.md are done
# or MAX_ITERATIONS is reached.

# Re-exec under bash if invoked via plain sh (e.g. "sh loops/loop_v2.sh")
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -euo pipefail

# ── Resolve repo root ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLAN_FILE="$REPO_ROOT/loops/IMPLEMENTATION_PLAN_V2.md"
MAX_ITERATIONS=20
ITERATION=0

echo "======================================================"
echo "  Discovery PoC Orchestrator — UI Refresh Loop V2"
echo "======================================================"
echo ""

# ── Setup Bob Shell (once, before the loop) ───────────────────────────────────
source "$REPO_ROOT/.bob/skills/generate-loop/scripts/setup.sh" --env-file "$REPO_ROOT/.env"

# ── Ensure we are on a feature branch ────────────────────────────────────────
CURRENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    BRANCH_NAME="feature/poc-orchestrator-v2"
    echo "Creating branch: $BRANCH_NAME"
    git -C "$REPO_ROOT" checkout -b "$BRANCH_NAME" 2>/dev/null || git -C "$REPO_ROOT" checkout "$BRANCH_NAME"
fi

while true; do
    # ── DONE CHECK — no unchecked tasks remain ────────────────────────────────
    if [ -f "$PLAN_FILE" ]; then
        if ! grep -q "\- \[ \]" "$PLAN_FILE"; then
            echo ""
            echo "✅ All tasks complete — no remaining '- [ ]' items in $PLAN_FILE"
            echo "Discovery PoC Orchestrator V2 build loop finished."
            break
        fi
    fi

    # ── MAX ITERATIONS CHECK ──────────────────────────────────────────────────
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo ""
        echo "🛑 Reached max iterations: $MAX_ITERATIONS"
        echo "Run the loop again to continue where it left off."
        break
    fi

    echo ""
    echo "------ Iteration $ITERATION ------"

    bash "$REPO_ROOT/loops/iteration_v2.sh" "$ITERATION"

    ITERATION=$((ITERATION + 1))
done
