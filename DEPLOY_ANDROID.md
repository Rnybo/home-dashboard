# Deploy til Android via ADB + Termux

## Forudsætninger
- ADB installeret på pc (`adb devices` viser din tablet)
- Termux installeret på tabletten
- Git, Python, Node.js og Playwright allerede installeret i Termux

## Trin 1 — Klon repo i Termux

Åbn Termux på tabletten (eller via ADB shell):

```bash
pkg update && pkg upgrade
cd ~
git clone https://github.com/Rnybo/aula-dashboard.git
cd aula-dashboard
```

## Trin 2 — Python environment

```bash
pip install -r requirements.txt
```

## Trin 3 — Chromium til MitID login

```bash
# Anbefalet: brug system Chromium fra Termux
pkg install chromium

# Alternativt: Playwright's egen (virker måske ikke på arm64)
playwright install chromium
```

Serveren søger automatisk efter Chromium i denne rækkefølge:
1. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` miljøvariabel
2. `/data/data/com.termux/files/usr/bin/chromium-browser`
3. `/usr/bin/chromium-browser`
4. Playwright's medfølgende Chromium (fallback)

## Trin 4 — Konfigurer .env

Kopiér `.env` fra pc via ADB:
```bash
adb push C:\Users\rnf\Projects\aula-dashboard\.env /sdcard/aula.env
```

Flyt den ind i Termux:
```bash
# I Termux:
cp /sdcard/aula.env ~/aula-dashboard/.env
```

Eller opret den manuelt:
```bash
cp .env.example .env
nano .env
```

## Trin 5 — Start serveren

```bash
cd ~/aula-dashboard
uvicorn main:app --host 127.0.0.1 --port 8080
```

Kør i baggrunden:
```bash
nohup uvicorn main:app --host 127.0.0.1 --port 8080 &> server.log &
echo $! > server.pid
```

Stop serveren:
```bash
kill $(cat server.pid)
```

## Trin 6 — Åbn i browser

Åbn **http://127.0.0.1:8080** i Chrome på tabletten.

## Tilgå fra andre enheder på netværket

Start serveren med `--host 0.0.0.0` for at tilgå fra mobil eller pc på samme netværk:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

Find tabletens IP under Indstillinger → WiFi → dit netværk, og åbn `http://<tablet-ip>:8080` på en anden enhed.

## Auto-start ved boot (valgfrit)

Installer Termux:Boot fra F-Droid:
```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-aula.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/aula-dashboard
nohup uvicorn main:app --host 0.0.0.0 --port 8080 &> server.log &
EOF
chmod +x ~/.termux/boot/start-aula.sh
```

## Opdatering

```bash
cd ~/aula-dashboard
git pull
kill $(cat server.pid)
nohup uvicorn main:app --host 0.0.0.0 --port 8080 &> server.log &
echo $! > server.pid
```

## Fejlfinding

**`playwright install chromium` fejler:**
```bash
pkg install chromium
```

**Port allerede i brug:**
```bash
pkill -f uvicorn
```

**Se server logs:**
```bash
tail -f server.log
```
