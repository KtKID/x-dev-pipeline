#!/usr/bin/env bash
set -euo pipefail

# x-dev-pipeline installer
# Usage: curl -fsSL https://raw.githubusercontent.com/KtKID/x-dev-pipeline/main/install.sh | bash

REPO="https://github.com/KtKID/x-dev-pipeline.git"
INSTALL_DIR="${HOME}/.claude/plugins/x-dev-pipeline"
BRANCH="main"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}[info]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[ok]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${NC}  %s\n" "$*"; }
fail()  { printf "${RED}[error]${NC} %s\n" "$*"; exit 1; }

# --- Pre-checks ---
command -v git >/dev/null 2>&1 || fail "git is not installed. Please install git first."

# --- Install / Update ---
if [ -d "$INSTALL_DIR" ]; then
  info "Existing installation found at $INSTALL_DIR"
  info "Pulling latest changes..."
  git -C "$INSTALL_DIR" fetch origin "$BRANCH" --quiet
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" --quiet
  ok "Updated to latest version."
else
  info "Cloning x-dev-pipeline..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR" --quiet
  ok "Cloned to $INSTALL_DIR"
fi

# --- Register plugin ---
if command -v claude >/dev/null 2>&1; then
  info "Registering plugin marketplace..."
  if claude plugin marketplace add "$INSTALL_DIR/.claude-plugin/marketplace.json" 2>/dev/null; then
    ok "Marketplace registered."
    info "Installing plugin..."
    if claude plugin install x-dev-pipeline@x-dev-pipeline --scope user 2>/dev/null; then
      ok "Plugin installed."
    else
      warn "Auto-install failed. Run manually:"
      echo "  claude plugin install x-dev-pipeline@x-dev-pipeline --scope user"
    fi
  else
    warn "Marketplace registration failed. Run manually:"
    echo "  claude plugin marketplace add $INSTALL_DIR/.claude-plugin/marketplace.json"
    echo "  claude plugin install x-dev-pipeline@x-dev-pipeline --scope user"
  fi
else
  warn "claude CLI not found in PATH. After installing Claude Code, run:"
  echo "  claude plugin marketplace add $INSTALL_DIR/.claude-plugin/marketplace.json"
  echo "  claude plugin install x-dev-pipeline@x-dev-pipeline --scope user"
fi

echo ""
ok "x-dev-pipeline is ready!"
echo ""
echo "  Get started:  /x-qdev add dark mode toggle to the settings page"
echo ""
echo "  Commands:     /x-qdev  /x-cr  /x-fix  /x-req  /x-plan  /x-dev  /x-spec"
echo "  Docs:         https://github.com/KtKID/x-dev-pipeline"
echo ""
