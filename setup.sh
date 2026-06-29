#!/bin/bash
# ─────────────────────────────────────────────────────────────
# WSDA Video Engine — macOS Setup
# MacBook Air M2 / macOS
# Run once: bash setup.sh
# ─────────────────────────────────────────────────────────────

set -e  # Exit on any error

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
step() { echo -e "\n${BOLD}── $1${NC}"; }

echo ""
echo -e "${BOLD}WSDA Video Engine — Setup${NC}"
echo "MacBook Air M2 / macOS"
echo "────────────────────────────────────"

# ── 1. Homebrew ───────────────────────────────────────────────
step "Homebrew"
if command -v brew &>/dev/null; then
    ok "Homebrew found: $(brew --version | head -1)"
else
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for M2
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
    ok "Homebrew installed"
fi

# ── 2. Python 3.11+ ───────────────────────────────────────────
step "Python"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VERSION"
    else
        warn "Python $PY_VERSION found but 3.11+ recommended. Installing via Homebrew..."
        brew install python@3.11
        ok "Python 3.11 installed"
    fi
else
    warn "Python not found. Installing..."
    brew install python@3.11
    ok "Python 3.11 installed"
fi

# ── 3. FFmpeg ─────────────────────────────────────────────────
step "FFmpeg"
if command -v ffmpeg &>/dev/null; then
    ok "FFmpeg found: $(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f1-3)"
else
    warn "FFmpeg not found. Installing..."
    brew install ffmpeg
    ok "FFmpeg installed"
fi

# ── 4. pip packages ───────────────────────────────────────────
step "Python packages"
pip3 install -r requirements.txt --quiet
ok "Python packages installed"

# ── 5. Playwright + Chromium ──────────────────────────────────
step "Playwright / Chromium"
pip3 install playwright --quiet
playwright install chromium
ok "Playwright + Chromium installed"

# ── 6. Create output directory ────────────────────────────────
step "Output directory"
mkdir -p output
ok "output/ ready"

# ── 7. Build demo database ────────────────────────────────────
step "NovaBridge demo database"
if [ -f "courses/novabridge/video_1_1/assets/novabridge.db" ]; then
    ok "novabridge.db already exists"
else
    python3 create_db.py
    ok "novabridge.db created"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}────────────────────────────────────${NC}"
echo -e "${GREEN}${BOLD}Setup complete.${NC}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Verify everything works:"
echo "     ${BOLD}python3 test_env.py${NC}"
echo ""
echo "  2. Rehearse the lesson (no recording, 2x speed):"
echo "     ${BOLD}python3 rehearse.py courses/novabridge/video_1_1/production_card.yml${NC}"
echo ""
echo "  3. Record the lesson:"
echo "     ${BOLD}python3 run.py courses/novabridge/video_1_1/production_card.yml${NC}"
echo ""
echo "  Output lands in: ${BOLD}output/${NC}"
echo ""
