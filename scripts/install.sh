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

$PIP install --break-system-packages pytesseract >> "$LOG" 2>&1 \
    && ok "pytesseract" || warn "pytesseract fejlede"

# ── Trin 3b: python-docx (ugebrev.py henter skoleugebreve som .docx, ikke
# .html — Googles anonyme HTML-export hænger uden svar, se backend/CLAUDE.md)
# — kræver lxml. Ren `pip install lxml`/`python-docx` FEJLER i en frisk
# Termux (bekræftet i praksis) fordi bygning fra kildekode kræver en
# C-compiler (`clang`) som IKKE er installeret som standard, uanset om
# libxml2/libxslt-headerne er der. Prøver derfor Termux's EGEN
# prækompilerede `python-lxml`-pakke først (samme mønster som
# `python-cryptography` ovenfor — undgår compiler-afhængigheden helt);
# falder kun tilbage til en kildekode-bygning (med clang installeret) hvis
# pkg-pakken skulle mangle/fejle.
step "Installerer python-docx (prøver Termux's prækompilerede lxml først)..."
if pkg install -y python-lxml >> "$LOG" 2>&1; then
    ok "lxml (Termux pkg, prækompileret — ingen bygning nødvendig)"
else
    warn "python-lxml (pkg) fejlede/findes ikke — bygger lxml fra kildekode i stedet"
    # pkg-config er BEVIDST med her, ikke bare libxml2/libxslt selv — lxmls
    # setup.py bruger pkg-config/xml2-config til at FINDE dem. Uden pkg-config
    # fejler bygningen med "please make sure the libxml2 and libxslt
    # development package are installed" UANSET om libxml2/libxslt reelt er
    # installeret — bekræftet i praksis (september 2026), ikke en antagelse.
    pkg install -y clang libxml2 libxslt pkg-config >> "$LOG" 2>&1 \
        && ok "clang/libxml2/libxslt/pkg-config (build-værktøjer)" \
        || warn "clang/libxml2/libxslt/pkg-config fejlede — lxml-bygning vil sandsynligvis også fejle"
    $PIP install --break-system-packages lxml >> "$LOG" 2>&1 \
        && ok "lxml (bygget fra kildekode)" \
        || warn "lxml fejlede at bygge — python-docx/ugebrev-featuren vil ikke virke"
fi
$PIP install --break-system-packages typing_extensions >> "$LOG" 2>&1 \
    && ok "typing_extensions" || warn "typing_extensions fejlede"
# --no-deps: lxml/typing_extensions er allerede håndteret eksplicit ovenfor —
# uden dette kunne pip finde på at forsøge sin EGEN (fejlende) kildekode-
# bygning af lxml alligevel, uafhængigt af om Termux-pakken lige er lykkedes.
$PIP install --break-system-packages --no-deps python-docx >> "$LOG" 2>&1 \
    && ok "python-docx" || warn "python-docx fejlede — ugebrev-featuren vil ikke virke"

# ── Trin 3c: Tesseract OCR (SFO/billed-ugeplaner, se backend/ugebrev.py) ─────
step "Installerer Tesseract OCR..."
pkg install -y tesseract >> "$LOG" 2>&1 \
    && ok "tesseract" || warn "tesseract fejlede — billed-ugeplaner (SFO) vil ikke kunne læses"

TESSDATA_DIR="$PREFIX/share/tessdata"
if [ ! -f "$TESSDATA_DIR/dan.traineddata" ]; then
    mkdir -p "$TESSDATA_DIR"
    curl -sSL "https://github.com/tesseract-ocr/tessdata_fast/raw/main/dan.traineddata" \
        -o "$TESSDATA_DIR/dan.traineddata" >> "$LOG" 2>&1 \
        && ok "Dansk OCR-sprogpakke" \
        || warn "Kunne ikke hente dansk OCR-sprogpakke — SFO-billeder læses da kun med engelsk"
else
    ok "Dansk OCR-sprogpakke OK"
fi

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
chmod +x "$INSTALL_DIR/scripts/run_server.sh"
cat > "$HOME/.termux/boot/start-familieoverblik.sh" << 'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
nohup sh ~/home-dashboard/scripts/run_server.sh >> ~/home-dashboard/server.log 2>&1 &
BOOT
chmod +x "$HOME/.termux/boot/start-familieoverblik.sh"
ok "Auto-start konfigureret"

# ── Trin 7: Start server ─────────────────────────────────────────────────────
step "Genstarter server..."
pkill -f uvicorn 2>/dev/null || true
pkill -f mosquitto 2>/dev/null || true
pkill -f run_server.sh 2>/dev/null || true
sleep 2
PID=$(ss -tlnp 2>/dev/null | awk '/:8000 /{match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}')
[ -n "$PID" ] && kill -9 "$PID" 2>/dev/null || true
sleep 1
nohup sh "$INSTALL_DIR/scripts/run_server.sh" >> "$INSTALL_DIR/server.log" 2>&1 &
sleep 5

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

# ── Trin 8: Robusthed — Android dræber jævnligt Termux i baggrunden ─────────
# Ingen watchdog inde i Termux kan reparere DETTE — Android lukker hele
# processen, ikke bare uvicorn. Kun en OS-indstilling løser det.
printf "\n${YELLOW}⚠ For at undgå at Android lukker serveren ned i baggrunden:${NC}\n"
printf "  Indstillinger → Apps → Termux → Batteri → 'Ingen begrænsninger'\n"
printf "  (samme sted som 'Tillad baggrundsaktivitet'/batterioptimering)\n"
printf "  Kør evt. også: termux-wake-lock (i en separat Termux-session)\n"
