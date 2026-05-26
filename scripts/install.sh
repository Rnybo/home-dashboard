#!/data/data/com.termux/files/usr/bin/sh
# =============================================================================
# Familieoverblik — Install/Update Script til Android/Termux
# Kør: sh install.sh
# Scriptet er idempotent — kan køres igen for at opdatere
# =============================================================================

set +e
export PATH="/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/bin/applets:$PATH"
export HOME="/data/data/com.termux/files/home"
export PREFIX="/data/data/com.termux/files/usr"

REPO="https://github.com/Rnybo/home-dashboard.git"
INSTALL_DIR="$HOME/home-dashboard"
LOG="/sdcard/familieoverblik_install.log"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { printf "${GREEN}✓ %s${NC}\n" "$1"; }
warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
err()  { printf "${RED}✗ %s${NC}\n" "$1"; exit 1; }
step() { printf "\n${YELLOW}▶ %s${NC}\n" "$1"; }
skip() { printf "${GREEN}↩ %s — allerede installeret${NC}\n" "$1"; }

printf "==================================================\n"
printf "  Familieoverblik — Installation/Opdatering\n"
printf "==================================================\n"

# ── Trin 1: Grundpakker ───────────────────────────────────────────────────────
if ! command -v git > /dev/null 2>&1 || ! command -v python > /dev/null 2>&1; then
    step "Installerer Termux-pakker..."
    DEBIAN_FRONTEND=noninteractive pkg update -y >> "$LOG" 2>&1 || true
    DEBIAN_FRONTEND=noninteractive pkg install -y bash python git openssh nodejs curl >> "$LOG" 2>&1 \
        || warn "Nogle pakker fejlede — fortsætter"
    ok "Termux-pakker installeret"
else
    skip "Termux-pakker"
fi

# ── Trin 2: Hent/opdater kode (ALTID) ────────────────────────────────────────
step "Henter seneste kode..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull origin main >> "$LOG" 2>&1
    ok "Kode opdateret"
else
    # Gem node_modules hvis de findes, slet resten og klon
    if [ -d "$INSTALL_DIR/node_modules" ]; then
        mv "$INSTALL_DIR/node_modules" /tmp/nm_backup 2>/dev/null
    fi
    rm -rf "$INSTALL_DIR"
    git clone "$REPO" "$INSTALL_DIR" >> "$LOG" 2>&1 \
        && ok "Kode hentet" \
        || err "Git clone fejlede — tjek netværk"
    # Gendan node_modules
    if [ -d /tmp/nm_backup ]; then
        mv /tmp/nm_backup "$INSTALL_DIR/node_modules" 2>/dev/null
    fi
fi

# ── Trin 3: Python afhængigheder ─────────────────────────────────────────────
if ! python -c "import fastapi" > /dev/null 2>&1; then
    step "Installerer Python pakker..."
    pip install --quiet --break-system-packages \
        fastapi uvicorn requests beautifulsoup4 python-dotenv \
        icalendar recurring-ical-events zeroconf httpx >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then ok "Python pakker installeret"
    else warn "Nogle Python pakker fejlede — tjek $LOG"; fi
else
    skip "Python pakker"
fi

# ── Trin 4: Node.js / Playwright ─────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR/node_modules/playwright-core" ]; then
    step "Installerer Node.js pakker..."
    npm install playwright-core@1.52.0 --prefix "$INSTALL_DIR" --silent >> "$LOG" 2>&1 \
        || warn "npm install fejlede — Playwright login virker muligvis ikke"
    ok "Node.js pakker installeret"
else
    skip "Node.js / Playwright"
fi

# ── Trin 5: .env setup ───────────────────────────────────────────────────────
cd "$INSTALL_DIR"
if [ ! -f ".env" ]; then
    step "Opretter .env..."
    [ -f ".env.example" ] && cp .env.example .env || touch .env
    warn "Åbn settings: http://familiekalender.local:8000/settings.html"
else
    skip ".env konfiguration"
fi

# ── Trin 6: Termux:Boot auto-start ───────────────────────────────────────────
step "Konfigurerer auto-start..."
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-familieoverblik.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
cd ~/home-dashboard
pkill -f uvicorn 2>/dev/null
sleep 2
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > ~/home-dashboard/server.log 2>&1 &
BOOT
chmod +x "$HOME/.termux/boot/start-familieoverblik.sh"
ok "Auto-start konfigureret"

# ── Trin 7: Start server ─────────────────────────────────────────────────────
step "Starter server..."
pkill -f uvicorn 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 1
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "$INSTALL_DIR/server.log" 2>&1 &
sleep 3

if pgrep -f uvicorn > /dev/null; then
    ok "Server kører!"
    printf "\n==================================================\n"
    printf "  ${GREEN}Familieoverblik er klar!${NC}\n\n"
    printf "  Dashboard:     http://familiekalender.local:8000\n"
    printf "  Indstillinger: http://familiekalender.local:8000/settings.html\n"
    printf "==================================================\n"
else
    err "Server startede ikke — tjek $INSTALL_DIR/server.log"
fi
