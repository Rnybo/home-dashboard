# Deploy til Android — Komplet Guide

Denne guide beskriver alt hvad der er nødvendigt for at sætte et nyt Android tablet op som et låst Aula-dashboard, samt daglig drift.

---

## Forudsætninger

**PC (Windows):**
- Python 3.12+ med `venv312` virtualenv i projektmappen
- ADB installeret og på PATH (`adb version` virker)
- `venv312\Scripts\pip install paramiko` er kørt

**Android tablet:**
- Fully Kiosk Browser installeret og sat som Device Owner
- Termux installeret (fra F-Droid, ikke Play Store)
- Termux:Boot installeret (fra F-Droid)

---

## Del 1 — Første gang: Opsætning af ny tablet

### Trin 1 — Termux grundpakker

Åbn Termux på tabletten og kør:

```bash
pkg update && pkg upgrade -y
pkg install -y python git openssh nodejs x11-repo
pkg install -y chromium
pip install fastapi uvicorn requests beautifulsoup4 python-dotenv icalendar recurring-ical-events
npm install playwright-core@1.52.0
```

### Trin 2 — Patch playwright-core til Android

playwright-core 1.52 understøtter ikke Android direkte. To filer skal patches:

**Patch 1** — `hostPlatform.js`: Erstat `'<unknown>'` fallback med `'ubuntu22.04-arm64'`:
```
fil: node_modules/playwright-core/lib/server/utils/hostPlatform.js
find:     hostPlatform: '<unknown>',
erstat:   hostPlatform: 'ubuntu22.04-arm64',
```

**Patch 2** — `registry/index.js`: Tillad android i cache-dir check:
```
fil: node_modules/playwright-core/lib/server/registry/index.js
find:   if (process.platform === "linux")
erstat: if (process.platform === "linux" || process.platform === "android")
```

Fra PC kan disse patches køres automatisk:
```
venv312\Scripts\python.exe patch_playwright_all.py
```
*(Se scripts-sektionen nedenfor)*

### Trin 3 — SSH adgang fra PC til tablet

**På tabletten** (i Termux):
```bash
ssh-keygen -t ed25519   # tryk Enter 3 gange
sshd
```

**På PC:**
```powershell
# Forward tablet SSH port via USB
adb forward tcp:8022 tcp:8022

# Generer RSA nøgle til PC→tablet forbindelse
venv312\Scripts\python.exe gen_ssh_key.py   # genererer tablet_key + tablet_key.pub

# Push public key til tablet (kræver at Termux er åben)
adb push tablet_key.pub /sdcard/tablet_key.pub
```

**Tilføj nøgle i Termux:**
```bash
mkdir -p ~/.ssh && cat /sdcard/tablet_key.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
```

Test forbindelsen:
```powershell
venv312\Scripts\python.exe tablet_ssh.py "echo OK"
```

### Trin 4 — Deploy projektet

```powershell
adb forward tcp:8022 tcp:8022
venv312\Scripts\python.exe full_sync.py
```

Dette pusher: `main.py`, `aula_client.py`, `aula_playwright.py` (Android stub), `login_node.js`, `requirements.txt`, `.env`, `static/index.html`

### Trin 5 — Start server

```powershell
venv312\Scripts\python.exe termux_start.py
```

Dette sender kommandoen direkte til Termux via ADB og starter uvicorn.

### Trin 6 — Sæt Termux:Boot op (auto-start ved genstart)

I Termux:
```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-aula.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/aula-dashboard
pkill -f uvicorn 2>/dev/null
sleep 1
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start-aula.sh
```

### Trin 7 — Konfigurer Fully Kiosk Browser

Gå til Fully Settings:
- **Start URL:** `http://127.0.0.1:8000`
- **Advanced Web Settings → Cache Mode:** `No Cache` (eller slå "Clear cache on reload" til)
- **Kiosk Mode:** aktivér
- **Keep Screen On** ved strøm: aktivér
- **Start on Boot:** aktivér

### Trin 8 — Log ind på Aula (første session)

```powershell
venv312\Scripts\python.exe tablet_ssh.py "curl -s -X POST http://127.0.0.1:8000/api/login/start -H 'x-api-key: <DIN_API_KEY>'"
```

Godkend i MitID-appen. API key hentes med:
```powershell
venv312\Scripts\python.exe tablet_ssh.py "curl -s http://127.0.0.1:8000/api/config"
```

---

## Del 2 — Daglig drift

### Session udløbet (typisk hver 30–90 dage)

Dashboardet viser "⚠️ Aula offline" banneret med login-knapper.

**Via dashboard:** Tryk "Login Rasmus" eller "Login Maja" direkte på skærmen → godkend i MitID-appen.

**Via PC (hvis dashboard ikke svarer):**
```powershell
adb forward tcp:8022 tcp:8022
venv312\Scripts\python.exe termux_start.py   # sikr server kører
# Tryk login på tablet og godkend i MitID
```

**Manuel session opdatering** (hvis login-flow fejler):
1. Log ind på aula.dk i browser → F12 → Application → Cookies
2. Kopiér `PHPSESSID` og `Csrfp-Token`
3. Kør:
```powershell
venv312\Scripts\python.exe update_session.py <PHPSESSID> <Csrfp-Token>
```

### Opdater konfiguration (.env ændringer)

```powershell
# Rediger .env på PC, gem, kør derefter:
venv312\Scripts\python.exe push_env.py
venv312\Scripts\python.exe termux_start.py
```

### Deploy opdateret kode

```powershell
adb forward tcp:8022 tcp:8022
venv312\Scripts\python.exe full_sync.py
venv312\Scripts\python.exe termux_start.py
```

### Tilføj Majas rigtige MitID brugernavn

Rediger `.env` på PC:
```
MITID_USERNAME_2=<majas_mitid_brugernavn>
```
Kør derefter `push_env.py` + `termux_start.py`.

---

## Del 3 — Projektstruktur

### Filer på PC (C:\Users\rnf\Projects\aula-dashboard\)

| Fil | Formål |
|-----|--------|
| `main.py` | FastAPI server — alle API endpoints |
| `aula_client.py` | Aula API klient (HTTP requests, session) |
| `aula_playwright.py` | MitID login via Playwright (køres på PC) |
| `aula_playwright_android.py` | Android stub — kalder login_node.js via subprocess |
| `login_node.js` | MitID login i Node.js med system-Chromium |
| `static/index.html` | Dashboard frontend (alt-i-én HTML/CSS/JS) |
| `.env` | Konfiguration (credentials, API keys, destinationer) |
| `session.json` | Aktiv Aula session (PHPSESSID + CSRF_TOKEN) |
| `tablet_key` | SSH privat nøgle til tablet-forbindelse |
| `tablet_key.pub` | SSH offentlig nøgle |

### Operationelle scripts på PC

| Script | Hvornår bruges det |
|--------|--------------------|
| `full_sync.py` | Deploy alle filer til tablet |
| `push_env.py` | Push kun .env + genstart |
| `termux_start.py` | Start/genstart server på tablet via ADB |
| `tablet_ssh.py` | Kør en SSH-kommando på tabletten |
| `update_session.py` | Manuel session-opdatering med cookies |
| `deploy_android.py` | Hurtig deploy uden .env |

### Filer på tablet (~/aula-dashboard/)

| Fil | Formål |
|-----|--------|
| `main.py` | Server (samme som PC) |
| `aula_client.py` | Aula klient (samme som PC) |
| `aula_playwright.py` | Android stub (≠ PC version) |
| `login_node.js` | Node.js MitID login |
| `login_node.js` | Node.js MitID login |
| `static/index.html` | Dashboard frontend |
| `.env` | Konfiguration |
| `session.json` | Aktiv session |
| `package.json` | Node.js dependencies |
| `node_modules/` | playwright-core + patches |

---

## Del 4 — .env reference

```env
# Aula session (opdateres automatisk ved login)
AULA_PHPSESSID=                    # legacy, bruges ikke hvis session.json findes
AULA_CSRF_TOKEN=                   # legacy

# MitID login (bruges til automatisk session-fornyelse)
MITID_USERNAME=RasmusNybo          # Rasmus MitID brugernavn
MITID_IDENTITY=Rasmus Fogh Nybo    # Fuldt navn som det står i MitID
MITID_USERNAME_2=Maja_Raabjerg     # Maja MitID brugernavn
MITID_IDENTITY_2=Maja Raabjerg Jensen

# API sikkerhed
API_KEY=                           # Auto-genereret ved første start

# Google Kalender (offentlige ICS links)
GOOGLE_CALENDAR_ICS_RASMUS=https://calendar.google.com/calendar/ical/...
GOOGLE_CALENDAR_ICS_MAJA=https://calendar.google.com/calendar/ical/...

# Vejr (koordinater for din adresse)
WEATHER_LAT=56.127
WEATHER_LON=10.178

# Rejsetider (OpenRouteService)
ORS_API_KEY=
ORS_ORIGIN_LAT=56.113586
ORS_ORIGIN_LON=10.196946
ORS_DEST_1_NAME=Systematic
ORS_DEST_1_LAT=56.152004
ORS_DEST_1_LON=10.176888
ORS_DEST_1_DEFAULT=cycling-regular
ORS_DEST_2_NAME=Skejby Sygehus
ORS_DEST_2_LAT=56.190518
ORS_DEST_2_LON=10.173182
ORS_DEST_2_DEFAULT=cycling-regular
ORS_DEST_3_NAME=Kragelundskolen
ORS_DEST_3_LAT=56.115202
ORS_DEST_3_LON=10.200216
ORS_DEST_3_DEFAULT=foot-walking
```

---

## Del 5 — Fejlfinding

### Server starter ikke
```powershell
venv312\Scripts\python.exe tablet_ssh.py "tail -20 ~/aula-dashboard/server.log"
```

### ADB kan ikke se tabletten
1. Tjek USB-kabel (skal være datakabel, ikke kun strøm)
2. Gå til Settings → Developer options → Revoke USB debugging authorizations
3. Genisæt kabel og acceptér popup på tabletten
4. `adb kill-server && adb start-server && adb devices`

### SSH timeout
```powershell
adb forward tcp:8022 tcp:8022   # skal køres hver gang PC genstarter
```
Og sikr at sshd kører i Termux: `sshd`

### playwright-core fejler efter npm update
Hvis `npm install` opdaterer playwright-core skal patches genansøges:
```powershell
venv312\Scripts\python.exe patch_playwright_all.py
venv312\Scripts\python.exe termux_start.py
```

### Fully viser gammel version
Gå til Fully Settings → Advanced Web Settings → Clear Cache og reload.
Eller slå "Clear cache on reload" til permanent.

### Session udløber meget ofte
Det skyldes at der logges ind fra flere steder (browser + Playwright). Brug kun én login-metode og log ikke ind manuelt på aula.dk mens dashboard kører.

---

## Del 6 — mDNS: Tilgå dashboardet via navn (familiekalender.local)

I stedet for at huske tablet-IP (`192.168.86.250:8000`) kan du tilgå dashboardet og ICS-feeden via et fast navn på dit netværk:

```
http://familiekalender.local:8000
http://familiekalender.local:8000/api/custom-events.ics
```

Virker automatisk på **iPhone, iPad, Mac, Windows og Android** via mDNS — ingen router-opsætning nødvendig.

### Opsætning i Termux (én gang)

```bash
pkg update
pkg install -y avahi
```

Start Avahi mDNS daemon:
```bash
avahi-daemon --daemonize
```

Verificer at det virker — fra en anden enhed på netværket:
```bash
ping familiekalender.local
```

### Auto-start Avahi ved boot (via Termux:Boot)

Opdater boot-scriptet til også at starte Avahi:
```bash
cat > ~/.termux/boot/start-aula.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Start mDNS (familiekalender.local)
avahi-daemon --daemonize 2>/dev/null || true

# Start dashboard server
cd ~/aula-dashboard
pkill -f uvicorn 2>/dev/null
sleep 1
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
EOF
chmod +x ~/.termux/boot/start-aula.sh
```

### Avahi konfiguration (hostname)

Avahi bruger som standard enhedens Android-hostname. For at sætte det til `familiekalender`:

```bash
# Sæt hostname i Avahi config
mkdir -p $PREFIX/etc/avahi
cat > $PREFIX/etc/avahi/avahi-daemon.conf << 'EOF'
[server]
host-name=familiekalender
domain-name=local
use-ipv4=yes
use-ipv6=no
allow-interfaces=wlan0
EOF
```

Genstart Avahi efter konfigurationsændring:
```bash
pkill avahi-daemon; avahi-daemon --daemonize
```

### Tilmeld ICS-feed i kalender-app

**Google Kalender (Android/Web):**
1. Åbn calendar.google.com
2. Indstillinger → Andre kalendere → Fra URL
3. Indsæt: `http://familiekalender.local:8000/api/custom-events.ics`
4. Tryk "Tilføj kalender"

**Apple Kalender (iPhone/iPad):**
1. Indstillinger → Kalender → Konti → Tilføj konto → Andet
2. Vælg "Tilføj abonnementskalender"
3. Indsæt: `http://familiekalender.local:8000/api/custom-events.ics`

> **Bemærk:** Google og Apple synkroniserer abonnementskalendere ca. hvert 24. time — ikke realtid. Nye events fra dashboardet vises i din telefons kalender inden for én dag.
