@echo off
cd /d "%~dp0"

echo [1/3] Checking for updates...
git pull

echo [2/3] Syncing dependencies...
pip install -r requirements.txt -q

echo [3/3] Starting bot...
py bot_gui.py
if %errorlevel% neq 0 (
  echo.
  echo Bot exited with error. Press any key to close.
  pause >nul
)
