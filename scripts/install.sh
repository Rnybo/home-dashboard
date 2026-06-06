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

printf "==================================================\n"
printf "  Familieoverblik — Installation/Opdatering\n"
printf "==================================================\n"

# ── Trin 1: Grundpakker ───────────────────────────────────────────────────────
step "Tjekker Termux-pakker..."
MISSING_PKG=""
for p in git python mosquitto; do
    command -v $p > /dev/null 2>&1 || MISSING_PKG="$MISSING_PKG $p"
done
if [ -n "$MISSING_PKG" ]; then
    step "Installerer:$MISSING_PKG..."
    pkg update -y >> "$LOG" 2>&1 || true
    pkg install -y $MISSING_PKG >> "$LOG" 2>&1 || warn "Nogle pakker fejlede"
fi
ok "Termux-pakker OK"

# ── Trin 2: Hent/opdater kode (ALTID) ────────────────────────────────────────
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

# ── Trin 3: Python afhængigheder (ALTID) ─────────────────────────────────────
step "Installerer Python pakker..."

# 3a: cryptography via pkg (ARM-kompatibel)
if ! python -c "import cryptography" > /dev/null 2>&1; then
    printf "  cryptography (via pkg)...\n"
    pkg install -y python-cryptography >> "$LOG" 2>&1 \
        && ok "cryptography OK" || warn "cryptography fejlede"
else
    ok "cryptography OK"
fi

# 3b: Alle øvrige pakker via pip
PIP="$(command -v pip3 || command -v pip)"
PKGS="fastapi uvicorn websockets requests beautifulsoup4 python-dotenv \
      icalendar recurring-ical-events zeroconf httpx paho-mqtt pychromecast \
      qrcode Pillow html2text"

for pkg in $PKGS; do
    # map pip name til import name
    case $pkg in
        beautifulsoup4) mod="bs4" ;;
        python-dotenv)  mod="dotenv" ;;
        paho-mqtt)      mod="paho.mqtt" ;;
        recurring-ical-events) mod="recurring_ical_events" ;;
        Pillow)         mod="PIL" ;;
        *)              mod="$pkg" ;;
    esac
    if ! python -c "import $mod" > /dev/null 2>&1; then
        printf "  $pkg...\n"
        $PIP install --quiet --break-system-packages "$pkg" >> "$LOG" 2>&1 \
            && ok "$pkg OK" || warn "$pkg fejlede"
    else
        ok "$pkg OK"
    fi
done

# ── Trin 4: Verificér alle afhængigheder ─────────────────────────────────────
step "Verificerer afhængigheder..."
if python backend/check_deps.py; then
    ok "Alle pakker OK"
else
    warn "Nogle pakker mangler — se output ovenfor. Server starter måske ikke."
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

pkill -f mosquitto 2>/dev/null; sleep 1
nohup mosquitto -c mosquitto.conf > ~/home-dashboard/mosquitto.log 2>&1 &
sleep 2

pkill -f uvicorn 2>/dev/null; sleep 1
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > ~/home-dashboard/server.log 2>&1 &
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
    warn "Server startede ikke — tjek $INSTALL_DIR/server.log"
    tail -20 "$INSTALL_DIR/server.log" 2>/dev/null
fi
