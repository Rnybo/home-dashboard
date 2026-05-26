#!/data/data/com.termux/files/usr/bin/sh
# =============================================================================
# Familieoverblik — Install Script til Android/Termux
# Kør: sh install.sh
# =============================================================================

set +e
export PATH="/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:$PATH"
export HOME="/data/data/com.termux/files/home"
export PREFIX="/data/data/com.termux/files/usr"
REPO="https://github.com/Rnybo/aula-dashboard.git"
INSTALL_DIR="$HOME/aula-dashboard"
LOG="/sdcard/familieoverblik_install.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; exit 1; }
step() { echo -e "\n${YELLOW}▶ $1${NC}"; }

echo "=================================================="
echo "  Familieoverblik — Installation"
echo "=================================================="

# ── Trin 1: Grundpakker ───────────────────────────────────────────────────────
step "Installerer Termux-pakker..."
DEBIAN_FRONTEND=noninteractive pkg update -y >> "$LOG" 2>&1 || true
DEBIAN_FRONTEND=noninteractive pkg install -y bash python git openssh nodejs curl >> "$LOG" 2>&1 || warn "Nogle pakker fejlede — fortsætter"
ok "Termux-pakker installeret"

# ── Trin 2: Python afhængigheder ──────────────────────────────────────────────
step "Installerer Python pakker..."
pip install --quiet --break-system-packages \
    fastapi uvicorn requests beautifulsoup4 python-dotenv \
    icalendar recurring-ical-events zeroconf httpx >> "$LOG" 2>&1
if [ $? -eq 0 ]; then ok "Python pakker installeret"
else warn "Nogle Python pakker fejlede — tjek $LOG"; fi

# ── Trin 3: Node.js / Playwright ─────────────────────────────────────────────
step "Installerer Node.js pakker..."
if [ ! -d "$INSTALL_DIR/node_modules" ]; then
    cd "$INSTALL_DIR" 2>/dev/null || true
    npm install playwright-core@1.52.0 --silent >> "$LOG" 2>&1 \
        || warn "npm install fejlede — Playwright login virker muligvis ikke"
    ok "Node.js pakker installeret"
else
    ok "Node.js pakker allerede installeret"
fi

# ── Trin 4: Patch playwright til Android ─────────────────────────────────────
step "Patcher Playwright til Android..."
PLAYWRIGHT_HOST="$INSTALL_DIR/node_modules/playwright-core/lib/server/utils/hostPlatform.js"
PLAYWRIGHT_REG="$INSTALL_DIR/node_modules/playwright-core/lib/server/registry/index.js"

if [ -f "$PLAYWRIGHT_HOST" ]; then
    sed -i "s/hostPlatform: '<unknown>'/hostPlatform: 'ubuntu22.04-arm64'/" "$PLAYWRIGHT_HOST"
    ok "hostPlatform.js patchet"
fi
if [ -f "$PLAYWRIGHT_REG" ]; then
    sed -i 's/if (process.platform === "linux")/if (process.platform === "linux" || process.platform === "android")/' "$PLAYWRIGHT_REG"
    ok "registry/index.js patchet"
fi

# ── Trin 5: Klon/opdater repo ─────────────────────────────────────────────────
step "Henter Familieoverblik kode..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull origin main >> "$LOG" 2>&1
    ok "Kode opdateret"
elif [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/main.py" ]; then
    ok "Kode allerede til stede"
else
    # Prøv clone — kræver at token er konfigureret eller repo er public
    git clone "$REPO" "$INSTALL_DIR" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then
        ok "Kode hentet"
    else
        warn "Git clone fejlede — brug ADB til at kopiere koden manuelt"
        warn "Kør fra PC: adb push . /sdcard/aula-dashboard && cp -r /sdcard/aula-dashboard ~/aula-dashboard"
    fi
fi

# ── Trin 6: .env setup ────────────────────────────────────────────────────────
step "Konfiguration..."
cd "$INSTALL_DIR"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env oprettet fra .env.example — konfigurér via http://familiekalender.local:8000/settings.html"
    else
        touch .env
        warn ".env oprettet tom — konfigurér via settings-siden"
    fi
else
    ok ".env findes allerede"
fi

# ── Trin 7: Termux:Boot auto-start ───────────────────────────────────────────
step "Opsætter auto-start ved boot..."
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-familieoverblik.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/aula-dashboard
pkill -f uvicorn 2>/dev/null
sleep 2
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ~/aula-dashboard/server.log 2>&1 &
BOOT
chmod +x "$HOME/.termux/boot/start-familieoverblik.sh"
ok "Auto-start konfigureret"

# ── Trin 8: Termux:API storage adgang ────────────────────────────────────────
step "Anmoder om storage-adgang..."
termux-setup-storage 2>/dev/null || warn "Kør 'termux-setup-storage' manuelt hvis nødvendigt"

# ── Trin 9: Start server ──────────────────────────────────────────────────────
step "Starter Familieoverblik..."
cd "$INSTALL_DIR"
pkill -f uvicorn 2>/dev/null || true
sleep 1
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
sleep 3

if pgrep -f uvicorn > /dev/null; then
    ok "Server kører!"
    echo ""
    echo "=================================================="
    echo -e "  ${GREEN}Familieoverblik er klar!${NC}"
    echo ""
    echo "  Åbn i browser:"
    echo "  http://familiekalender.local:8000"
    echo ""
    echo "  Konfigurér her:"
    echo "  http://familiekalender.local:8000/settings.html"
    echo "=================================================="
else
    err "Server startede ikke — tjek $INSTALL_DIR/server.log"
fi
