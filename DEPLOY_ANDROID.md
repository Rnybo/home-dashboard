# Deploy til Android via ADB + Termux

## Forudsætninger
- ADB installeret på pc (`adb devices` viser din tablet)
- Termux installeret på tabletten
- Git, Python, Node.js og Playwright allerede installeret i Termux

## Trin 1 — Push filer via ADB

Fra pc:
```bash
# Kopiér projektet til tabletten
adb push C:\Users\rnf\Projects\aula-dashboard /data/local/tmp/aula-dashboard
```

Eller klon direkte i Termux (nemmere):
```bash
adb shell
```

## Trin 2 — Opsætning i Termux

Åbn Termux på tabletten (eller via ADB shell):

```bash
# Opdater pakker
pkg update && pkg upgrade

# Klon repo (nemmeste metode)
cd ~
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

## Trin 3 — Python environment

```bash
# Installer Python dependencies
pip install -r requirements.txt

# Installer system Chromium (anbefalet på Android/Termux)
pkg install chromium

# Alternativt: Playwright's egen Chromium (virker måske ikke på arm64)
playwright install chromium
```

> **Bemærk:** På Android/Termux bruges system-Chromium automatisk hvis den findes.
> Serveren søger selv efter Chromium på følgende steder (i prioriteret rækkefølge):
> 1. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` miljøvariabel
> 2. `/data/data/com.termux/files/usr/bin/chromium-browser`
> 3. `/usr/bin/chromium-browser`
> 4. Playwright's medfølgende Chromium (fallback)

## Trin 4 — Konfigurer .env

```bash
cp .env.example .env
nano .env   # eller: vi .env
```

Udfyld med dine værdier (kopiér fra pc-versionen).

## Trin 5 — Start serveren

```bash
cd ~/aula-dashboard
uvicorn main:app --host 127.0.0.1 --port 8080
```

For at køre i baggrunden (selv efter Termux lukkes):
```bash
nohup uvicorn main:app --host 127.0.0.1 --port 8080 &> server.log &
echo $! > server.pid
```

Stop serveren:
```bash
kill $(cat server.pid)
```

## Trin 6 — Åbn i browser

Åbn **http://127.0.0.1:8080** i Chrome/Firefox på tabletten.

## Auto-start ved boot (valgfrit)

Installer Termux:Boot fra F-Droid, og tilføj et startup-script:

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-aula.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/aula-dashboard
nohup uvicorn main:app --host 127.0.0.1 --port 8080 &> server.log &
EOF
chmod +x ~/.termux/boot/start-aula.sh
```

## Opdatering

Når der er nye commits:
```bash
cd ~/aula-dashboard
git pull
# Genstart serveren
kill $(cat server.pid)
nohup uvicorn main:app --host 127.0.0.1 --port 8080 &> server.log &
echo $! > server.pid
```

## Fejlfinding

**`playwright install chromium` fejler:**
```bash
# Prøv med --with-deps
playwright install --with-deps chromium
```

**Port allerede i brug:**
```bash
pkill -f uvicorn
```

**Se server logs:**
```bash
tail -f server.log
```
