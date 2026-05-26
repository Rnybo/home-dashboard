@echo off
echo Saetter netvaerksprofil til Private (kraever admin)...
powershell -Command "Set-NetConnectionProfile -NetworkCategory Private" 2>nul
echo Starter Familieoverblik...
if exist venv312\Scripts\uvicorn.exe (
    venv312\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000
) else if exist venv\Scripts\uvicorn.exe (
    venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000
) else (
    echo Ingen venv fundet - kør: python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
)
