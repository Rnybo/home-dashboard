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
INSTALL_DIR="$HOME/aula-dashboard"
LOG="/sdcard/familieoverblik_install.log"
MARKER="$HOME/.familieoverblik_installed"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { printf "${GREEN}✓ %s${NC}\n" "$1"; }
warn() { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
err()  { printf "${RED}✗ %s${NC}\n" "$1"; exit 1; }
step() { printf "\n${YELLOW}▶ %s${NC}\n" "$1"; }
skip() { printf "${GREEN}↩ %s — allerede installeret${NC}\n" "$1"; }

is_first_install() { [ ! -f "$MARKER" ]; }

printf "==================================================\n"
printf "  Familieoverblik — %s\n" "$(is_first_install && echo 'Installation' || echo 'Opdatering')"
printf "==================================================\n"

# ── Trin 1: Grundpakker ───────────────────────────────────────────────────────
if is_first_install || ! command -v python > /dev/null 2>&1; then
    step "Installerer Termux-pakker..."
    DEBIAN_FRONTEND=noninteractive pkg update -y >> "$LOG" 2>&1 || true
    DEBIAN_FRONTEND=noninteractive pkg install -y bash python git openssh nodejs curl >> "$LOG" 2>&1 \
        || warn "Nogle pakker fejlede — fortsætter"
    ok "Termux-pakker installeret"
else
    skip "Termux-pakker"
fi

# ── Trin 2: Python afhængigheder ──────────────────────────────────────────────
if is_first_install || ! python -c "import fastapi" > /dev/null 2>&1; then
    step "Installerer Python pakker..."
    pip install --quiet --break-system-packages \
        fastapi uvicorn requests beautifulsoup4 python-dotenv \
        icalendar recurring-ical-events zeroconf httpx >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then ok "Python pakker installeret"
    else warn "Nogle Python pakker fejlede — tjek $LOG"; fi
else
    skip "Python pakker"
fi

# ── Trin 3: Node.js / Playwright ─────────────────────────────────────────────
if is_first_install || [ ! -d "$INSTALL_DIR/node_modules/playwright-core" ]; then
    step "Installerer Node.js pakker..."
    cd "$INSTALL_DIR" 2>/dev/null || true
    npm install playwright-core@1.52.0 --silent >> "$LOG" 2>&1 \
        || warn "npm install fejlede — Playwright login virker muligvis ikke"
    ok "Node.js pakker installeret"
else
    skip "Node.js / Playwright"
fi

# ── Trin 4: Patch playwright til Android ─────────────────────────────────────
# (køres efter git pull i trin 5)

# ── Trin 5: Hent/opdater kode ─────────────────────────────────────────────────
step "Henter seneste kode..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull origin main >> "$LOG" 2>&1
    ok "Kode opdateret"
elif [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/main.py" ]; then
    ok "Kode til stede (ikke git-managed)"
else
    git clone "$REPO" "$INSTALL_DIR" >> "$LOG" 2>&1
    if [ $? -eq 0 ]; then ok "Kode hentet"
    else warn "Git clone fejlede — kopiér koden manuelt fra PC"; fi
fi

# Patch playwright stub efter kode er hentet
if [ -f "$INSTALL_DIR/aula_playwright_android.py" ]; then
    cp "$INSTALL_DIR/aula_playwright_android.py" "$INSTALL_DIR/aula_playwright.py"
    ok "Playwright Android stub aktiveret"
fi

# ── Trin 6: .env setup ────────────────────────────────────────────────────────
cd "$INSTALL_DIR"
if [ ! -f ".env" ]; then
    step "Opretter .env..."
    [ -f ".env.example" ] && cp .env.example .env || touch .env
    warn "Åbn settings: http://familiekalender.local:8000/settings.html"
else
    skip ".env konfiguration"
fi

# ── Trin 7: Termux:Boot auto-start ───────────────────────────────────────────
step "Konfigurerer auto-start..."
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-familieoverblik.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
cd ~/aula-dashboard
pkill -f uvicorn 2>/dev/null
sleep 2
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8080 > ~/aula-dashboard/server.log 2>&1 &
BOOT
chmod +x "$HOME/.termux/boot/start-familieoverblik.sh"
ok "Auto-start konfigureret"

# ── Trin 8: Marker installation som fuldført ─────────────────────────────────
touch "$MARKER"

# ── Trin 9: (Gen)start server ─────────────────────────────────────────────────
step "Starter server..."
pkill -f uvicorn 2>/dev/null || true
fuser -k 8080/tcp 2>/dev/null || true
sleep 1
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8080 > "$INSTALL_DIR/server.log" 2>&1 &
sleep 3

if pgrep -f uvicorn > /dev/null; then
    ok "Server kører!"
    printf "\n==================================================\n"
    printf "  ${GREEN}Familieoverblik er klar!${NC}\n\n"
    printf "  Dashboard:     http://familiekalender.local:8080\n"
    printf "  Indstillinger: http://familiekalender.local:8080/settings.html\n"
    printf "==================================================\n"
else
    err "Server startede ikke — tjek $INSTALL_DIR/server.log"
fi
