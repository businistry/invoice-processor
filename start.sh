#!/bin/bash
set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
info() { echo -e "${CYAN}→ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗"
echo -e "║     Invoice Processor — Web App     ║"
echo -e "╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Python ─────────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  err "Python 3 is not installed. Download it from https://python.org"
  exit 1
fi
ok "Python 3 found ($(python3 --version))"

# ── 2. Poppler ────────────────────────────────────────────────────────────────
if command -v pdftoppm &>/dev/null; then
  ok "Poppler already installed"
else
  info "Installing Poppler..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &>/dev/null; then
      err "Homebrew not found. Install it from https://brew.sh then re-run this script."
      exit 1
    fi
    brew install poppler
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt-get update -qq && sudo apt-get install -y poppler-utils
  else
    warn "Could not auto-install Poppler on this OS."
    warn "Windows: download from https://github.com/oschwartz10612/poppler-windows/releases"
    warn "Then set POPPLER_PATH to the bin folder and re-run."
  fi
fi

# ── 3. Virtual environment ────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
  info "Creating virtual environment..."
  python3 -m venv venv
fi
ok "Virtual environment ready"

# Activate venv
source venv/bin/activate

# ── 4. Python dependencies ────────────────────────────────────────────────────
# Only install if flask isn't already present (fast subsequent starts)
if ! python -c "import flask" &>/dev/null 2>&1; then
  info "Installing Python dependencies..."
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  ok "Dependencies installed"
else
  ok "Dependencies already installed"
fi

# ── 5. Check for API keys ─────────────────────────────────────────────────────
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  warn "No API keys found in environment."
  warn "You can enter them in the browser, or set them here to avoid typing each time:"
  echo -e "  ${YELLOW}export OPENAI_API_KEY=sk-...${NC}"
  echo -e "  ${YELLOW}export ANTHROPIC_API_KEY=sk-ant-...${NC}"
  echo ""
else
  [ -n "$OPENAI_API_KEY" ]     && ok "OPENAI_API_KEY set"
  [ -n "$ANTHROPIC_API_KEY" ]  && ok "ANTHROPIC_API_KEY set"
fi

# ── 6. Open browser after short delay ────────────────────────────────────────
PORT=${PORT:-5000}
(
  sleep 1.5
  if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:$PORT"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "http://localhost:$PORT" &>/dev/null || true
  fi
) &

# ── 7. Start Flask ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Starting Invoice Processor on http://localhost:$PORT${NC}"
echo -e "${CYAN}Press Ctrl+C to stop.${NC}"
echo ""

python app.py
