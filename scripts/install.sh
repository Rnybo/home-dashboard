#!/data/data/com.termux/files/usr/bin/sh
# =============================================================================
# Familieoverblik — Install/Update Script til Android/Termux
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

printf "==================================================\n"
printf "  Familieoverblik — Installation/Opdatering\n"
printf "==================================================\n"

# ── Trin 1: Grundpakker ───────────────────────────────────────────────────────
step "Tjekker Termux-pakker..."
for p in git python mosquitto; do
    if ! command -v $p > /dev/null 2>&1; then
        pkg update -y >> "$LOG" 2>&1 || true
        pkg install -y git python mosquitto >> "$LOG" 2>&1 || warn "pkg install fejlede"
        break
    fi
done
ok "Termux-pakker OK"

# ── Trin 2: Hent/opdater kode ────────────────────────────────────────────────
step "Henter seneste kode..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull origin main >> "$LOG" 2>&1
    ok "Kode opdateret"
else
    rm -rf "$INSTALL_DIR"
    git clone "$REPO" "$INSTALL_DIR" >> "$LOG" 2>&1 \
        && ok "Kode hentet" \
        || err "Git clone fejlede — tjek netværk"
fi
cd "$INSTALL_DIR"

# ── Trin 3: Python pakker — installer alle, ingen checks ─────────────────────
step "Installerer Python pakker..."
PIP="$(command -v pip3 || command -v pip)"

pkg install -y python-cryptography >> "$LOG" 2>&1 \
    && ok "cryptography" || warn "cryptography fejlede"

$PIP install --break-system-packages fastapi >> "$LOG" 2>&1 \
    && ok "fastapi" || warn "fastapi fejlede"

$PIP install --break-system-packages "uvicorn[standard]" >> "$LOG" 2>&1 \
    && ok "uvicorn" || warn "uvicorn fejlede"

$PIP install --break-system-packages uvloop >> "$LOG" 2>&1 \
    && ok "uvloop" || warn "uvloop fejlede (ikke kritisk)"

$PIP install --break-system-packages websockets >> "$LOG" 2>&1 \
    && ok "websockets" || warn "websockets fejlede"

$PIP install --break-system-packages requests >> "$LOG" 2>&1 \
    && ok "requests" || warn "requests fejlede"

$PIP install --break-system-packages beautifulsoup4 >> "$LOG" 2>&1 \
    && ok "beautifulsoup4" || warn "beautifulsoup4 fejlede"

$PIP install --break-system-packages python-dotenv >> "$LOG" 2>&1 \
    && ok "python-dotenv" || warn "python-dotenv fejlede"

$PIP install --break-system-packages icalendar >> "$LOG" 2>&1 \
    && ok "icalendar" || warn "icalendar fejlede"

$PIP install --break-system-packages recurring-ical-events >> "$LOG" 2>&1 \
    && ok "recurring-ical-events" || warn "recurring-ical-events fejlede"

$PIP install --break-system-packages zeroconf >> "$LOG" 2>&1 \
    && ok "zeroconf" || warn "zeroconf fejlede"

$PIP install --break-system-packages httpx >> "$LOG" 2>&1 \
    && ok "httpx" || warn "httpx fejlede"

$PIP install --break-system-packages paho-mqtt >> "$LOG" 2>&1 \
    && ok "paho-mqtt" || warn "paho-mqtt fejlede"

$PIP install --break-system-packages pychromecast >> "$LOG" 2>&1 \
    && ok "pychromecast" || warn "pychromecast fejlede"

$PIP install --break-system-packages qrcode >> "$LOG" 2>&1 \
    && ok "qrcode" || warn "qrcode fejlede"

$PIP install --break-system-packages Pillow >> "$LOG" 2>&1 \
    && ok "Pillow" || warn "Pillow fejlede"

$PIP install --break-system-packages html2text >> "$LOG" 2>&1 \
    && ok "html2text" || warn "html2text fejlede"

# ── Trin 4: Verificér ────────────────────────────────────────────────────────
step "Verificerer afhængigheder..."
if python backend/check_deps.py; then
    ok "Alle pakker OK"
else
    warn "Nogle pakker mangler stadig — se output ovenfor"
fi

# ── Trin 5: .env setup ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    step "Opretter .env..."
    [ -f ".env.example" ] && cp .env.example .env || touch .env
    warn "Åbn settings: http://familiekalender.local:8000/settings.html"
else
    ok ".env OK"
fi

# ── Trin 6: Termux:Boot auto-start ───────────────────────────────────────────
step "Konfigurerer auto-start..."
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-familieoverblik.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
cd ~/home-dashboard

# Start Mosquitto
pkill -f mosquitto 2>/dev/null; sleep 1
nohup mosquitto -c mosquitto.conf > ~/home-dashboard/mosquitto.log 2>&1 &
sleep 2

# Start uvicorn med watchdog — genstarter automatisk ved crash
while true; do
    uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --loop uvloop \
        --timeout-keep-alive 30 \
        >> ~/home-dashboard/server.log 2>&1
    echo "$(date): uvicorn crashed — genstarter om 5 sek" >> ~/home-dashboard/server.log
    sleep 5
done &
BOOT
chmod +x "$HOME/.termux/boot/start-familieoverblik.sh"
ok "Auto-start konfigureret"

# ── Trin 7: Start server ─────────────────────────────────────────────────────
step "Genstarter server..."
pkill -f uvicorn 2>/dev/null || true
pkill -f mosquitto 2>/dev/null || true
sleep 2
PID=$(ss -tlnp 2>/dev/null | awk '/:8000 /{match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
[ -n "$PID" ] && kill -9 "$PID" 2>/dev/null || true
sleep 1
nohup mosquitto -c "$INSTALL_DIR/mosquitto.conf" > "$INSTALL_DIR/mosquitto.log" 2>&1 &
sleep 2
nohup uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --loop uvloop \
    --timeout-keep-alive 30 \
    > "$INSTALL_DIR/server.log" 2>&1 &
sleep 3

if pgrep -f uvicorn > /dev/null; then
    ok "Server kører!"
    printf "\n==================================================\n"
    printf "  ${GREEN}Familieoverblik er klar!${NC}\n\n"
    printf "  Dashboard:     http://familiekalender.local:8000\n"
    printf "  Indstillinger: http://familiekalender.local:8000/settings.html\n"
    printf "==================================================\n"
else
    warn "Server startede ikke — tjek $INSTALL_DIR/server.log"
    tail -20 "$INSTALL_DIR/server.log" 2>/dev/null
fi
