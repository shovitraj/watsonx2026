#!/usr/bin/env bash
# setup.sh — Platform-agnostic Bob Shell setup script (macOS / Linux)
# Usage: bash setup.sh [--env-file <path>]   (default env file: .env in cwd)
set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $*"; }
error() { echo -e "${RED}[setup] ERROR:${NC} $*" >&2; }

# ── Argument parsing ──────────────────────────────────────────────────────────
ENV_FILE="${1:-.env}"
if [[ "$1" == "--env-file" && -n "${2:-}" ]]; then
  ENV_FILE="$2"
fi

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  perl -i -pe 's/^[^A-Za-z#]*(BOBSHELL_API_KEY)/$1/' "$ENV_FILE"
  info "Loading environment from $ENV_FILE"
  # Export only lines that look like KEY=VALUE (skip comments and blanks).
  # Use a temp file instead of source <(...) — bash 3.2 on macOS does not
  # propagate variable assignments from process-substitution fds back to the
  # caller's scope, so the API key would silently vanish.
  _TMP_ENV="$(mktemp)"
  grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" > "$_TMP_ENV" || true
  set -o allexport
  # shellcheck disable=SC1090
  source "$_TMP_ENV"
  set +o allexport
  rm -f "$_TMP_ENV"
else
  warn ".env file not found at '$ENV_FILE'. Continuing without it."
fi

# ── Fall back to git config for GIT_USER_EMAIL / GIT_USER_NAME ───────────────
if [[ -z "${GIT_USER_EMAIL:-}" ]]; then
  GIT_USER_EMAIL="$(git config --global user.email 2>/dev/null || git config user.email 2>/dev/null || true)"
  [[ -n "$GIT_USER_EMAIL" ]] && info "GIT_USER_EMAIL read from git config: $GIT_USER_EMAIL"
fi
if [[ -z "${GIT_USER_NAME:-}" ]]; then
  GIT_USER_NAME="$(git config --global user.name 2>/dev/null || git config user.name 2>/dev/null || true)"
  [[ -n "$GIT_USER_NAME" ]] && info "GIT_USER_NAME read from git config: $GIT_USER_NAME"
fi
export GIT_USER_EMAIL GIT_USER_NAME

# ── Validate required env vars ────────────────────────────────────────────────
MISSING=()
[[ -z "${BOBSHELL_API_KEY:-}" ]] && MISSING+=("BOBSHELL_API_KEY")
[[ -z "${GIT_USER_EMAIL:-}" ]]   && MISSING+=("GIT_USER_EMAIL (not set in .env and not found in git config)")
[[ -z "${GIT_USER_NAME:-}" ]]    && MISSING+=("GIT_USER_NAME (not set in .env and not found in git config)")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  error "The following required values are missing:"
  for v in "${MISSING[@]}"; do
    echo "    • $v"
  done
  echo ""
  echo "  Copy the template and fill in the missing values:"
  echo "    cp .bob/skills/generate-loop/assets/.env-template .env"
  echo "  Then re-run: bash setup.sh"
  exit 1
fi

info "All required environment variables are present."

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="$(uname -s 2>/dev/null || echo unknown)"
case "$OS" in
  Darwin|Linux) ;;
  *)
    error "Unsupported OS: $OS. On Windows run setup.ps1 instead."
    exit 1
    ;;
esac

# ── Required minimum version ──────────────────────────────────────────────────
REQUIRED_VERSION="1.0.6"

# ── Check whether bob is installed and at the right version ───────────────────
CURRENT_VERSION=""
if command -v bob &>/dev/null; then
  CURRENT_VERSION="$(bob --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
fi

install_bob() {
  info "Installing Bob Shell …"
  curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash
  # Reload PATH so the freshly installed binary is found in this shell session
  export PATH="$HOME/.local/bin:$PATH"
  CURRENT_VERSION="$(bob --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
}

if [[ -z "$CURRENT_VERSION" ]]; then
  install_bob
elif [[ "$CURRENT_VERSION" != "$REQUIRED_VERSION" ]]; then
  warn "Found bob $CURRENT_VERSION, required $REQUIRED_VERSION. Re-installing …"
  install_bob
else
  info "bob $CURRENT_VERSION is already installed and up to date."
fi

# ── Final version verification ────────────────────────────────────────────────
if [[ "$(bob --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)" != "$REQUIRED_VERSION" ]]; then
  error "Installation failed — expected bob $REQUIRED_VERSION."
  exit 1
fi

info "✅ Bob Shell $REQUIRED_VERSION is ready."
info "   BOBSHELL_API_KEY is configured. GIT_USER_EMAIL=$GIT_USER_EMAIL, GIT_USER_NAME=$GIT_USER_NAME"
