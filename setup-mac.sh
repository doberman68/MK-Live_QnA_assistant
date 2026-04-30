#!/usr/bin/env bash
# MK-Live Q&A Assistant — Mac setup script
# Run from the repo root: bash setup-mac.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

echo ""
echo "  MK-Live Q&A Assistant — Mac Setup"
echo "  ===================================="
echo ""

# ── Prerequisites check ─────────────────────────────────────────────────────

info "Checking prerequisites..."

# Python 3.11+
if ! command -v python3 &>/dev/null; then
  error "Python 3 not found. Install from https://python.org or: brew install python"
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  error "Python 3.11+ required (found $PY_VERSION). Install: brew install python"
fi
info "  Python $PY_VERSION ✓"

# Node 18+
if ! command -v node &>/dev/null; then
  error "Node.js not found. Install from https://nodejs.org or: brew install node"
fi
NODE_VERSION=$(node --version | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
  error "Node.js 18+ required (found $NODE_VERSION). Install: brew install node"
fi
info "  Node.js v$NODE_VERSION ✓"

# npm
if ! command -v npm &>/dev/null; then
  error "npm not found. It should come with Node.js."
fi
info "  npm $(npm --version) ✓"

# Homebrew (optional but needed for BlackHole)
if command -v brew &>/dev/null; then
  info "  Homebrew ✓"
  HAS_BREW=1
else
  warn "  Homebrew not found — skipping BlackHole install (system audio won't work)"
  HAS_BREW=0
fi

echo ""

# ── Python backend ───────────────────────────────────────────────────────────

info "Installing Python dependencies..."
info "  (openai-whisper includes PyTorch — this may take a few minutes on first run)"
cd "$BACKEND_DIR"
pip3 install -q -r requirements.txt
info "  Python deps installed ✓"
echo ""

# ── Node / Electron frontend ─────────────────────────────────────────────────

info "Installing Electron dependencies..."
cd "$FRONTEND_DIR"
npm install --silent
info "  Node deps installed ✓"
echo ""

# ── BlackHole (system audio loopback) ────────────────────────────────────────

if [ "$HAS_BREW" -eq 1 ]; then
  if system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole"; then
    info "  BlackHole already installed ✓"
  else
    info "Installing BlackHole (system audio loopback)..."
    brew install --quiet blackhole-2ch
    info "  BlackHole 2ch installed ✓"
    echo ""
    echo -e "  ${YELLOW}ACTION REQUIRED — finish BlackHole setup:${NC}"
    echo "  1. Open Audio MIDI Setup (Spotlight → 'Audio MIDI Setup')"
    echo "  2. Click + → Create Multi-Output Device"
    echo "  3. Check both your speakers/headphones AND BlackHole 2ch"
    echo "  4. Set your Mac System Output to this Multi-Output Device"
    echo "  5. In the app Settings → Loopback device → BlackHole 2ch"
  fi
fi

echo ""

# ── Write a launcher script ──────────────────────────────────────────────────

LAUNCHER="$REPO_ROOT/run.sh"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# Launch MK-Live Q&A Assistant (backend + frontend)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start Python backend in background
python3 "$REPO_ROOT/backend/main.py" --port 8765 &
BACKEND_PID=$!
echo "[run] Backend started (PID $BACKEND_PID)"

# Wait for backend to be ready
for i in $(seq 1 20); do
  if curl -sf http://localhost:8765/api/status >/dev/null 2>&1; then
    echo "[run] Backend ready"
    break
  fi
  sleep 0.5
done

# Launch Electron
cd "$REPO_ROOT/frontend"
npm start

# When Electron exits, kill backend
kill $BACKEND_PID 2>/dev/null
LAUNCHER_EOF
chmod +x "$LAUNCHER"
info "Launcher script created: ./run.sh"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}  Setup complete!${NC}"
echo ""
echo "  To start the app:"
echo "    bash run.sh"
echo ""
echo "  Then in the app:"
echo "    1. Click the gear (Settings)"
echo "    2. Choose your LLM provider and paste an API key"
echo "       (or install Ollama from https://ollama.com for a free local model)"
echo "    3. Save Settings"
echo "    4. Click Start → speak → click Get Answer"
echo ""
