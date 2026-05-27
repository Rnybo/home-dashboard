@echo off
echo Saetter netvaerksprofil til Private (kraever admin)...
powershell -Command "Set-NetConnectionProfile -NetworkCategory Private" 2>nul

echo Tjekker Mosquitto MQTT broker...
sc query mosquitto >nul 2>&1
if %errorlevel% == 0 (
    sc start mosquitto >nul 2>&1
    echo Mosquitto service startet.
) else (
    netstat -ano | findstr ":1883" >nul 2>&1
    if %errorlevel% neq 0 (
        if exist "C:\Program Files\mosquitto\mosquitto.exe" (
            start /B "" "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf
            echo Mosquitto startet som proces.
        ) else (
            echo ADVARSEL: Mosquitto ikke fundet - installer via: winget install mosquitto
        )
    ) else (
        echo Mosquitto korer allerede.
    )
)

echo Starter Familieoverblik...
if exist venv312\Scripts\uvicorn.exe (
    venv312\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000
) else if exist venv\Scripts\uvicorn.exe (
    venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000
) else (
    echo Ingen venv fundet - koer: python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
)
