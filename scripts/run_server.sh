#!/data/data/com.termux/files/usr/bin/sh
# =============================================================================
# scripts/run_server.sh — Starter Mosquitto + uvicorn med automatisk genstart
# ved crash.
#
# Brugt BÅDE af Termux:Boot (~/.termux/boot/start-familieoverblik.sh) OG af
# install.sh's sidste trin. Før denne fil eksisterede havde KUN boot-vejen en
# genstarts-watchdog — en almindelig "git pull && bash install.sh" efterlod
# serveren uden nogen automatisk gendannelse ved crash, indtil næste fysiske
# genstart af tabletten. Det var den mest sandsynlige forklaring på "serveren
# stopper og skal genstartes manuelt" for crashes der skete mellem deploys.
# =============================================================================
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
export HOME="/data/data/com.termux/files/home"
INSTALL_DIR="$HOME/home-dashboard"
cd "$INSTALL_DIR" || exit 1

pkill -f mosquitto 2>/dev/null
sleep 1
nohup mosquitto -c "$INSTALL_DIR/mosquitto.conf" > "$INSTALL_DIR/mosquitto.log" 2>&1 &
sleep 2

while true; do
    uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --loop uvloop \
        --timeout-keep-alive 30 \
        >> "$INSTALL_DIR/server.log" 2>&1
    EXIT_CODE=$?
    echo "$(date '+%Y-%m-%d %H:%M:%S'): uvicorn stoppede (exit code $EXIT_CODE) - genstarter om 5 sek" >> "$INSTALL_DIR/server.log"
    sleep 5
done
