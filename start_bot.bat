@echo off
cd /d "%~dp0"

echo [1/3] Checking for updates...
REM 친구 PC는 코드를 건드리지 않는다는 전제 — 강제로 origin/main과 동기화.
REM ff-only는 conflict가 한 번 나면 영영 stale이 되는 함정이 있음.
git fetch origin
git reset --hard origin/main
if errorlevel 1 (
  echo [WARN] Update skipped ^(network issue?^). Continuing with current code.
)

echo [2/3] Syncing dependencies...
REM py -m pip: pip.exe가 PATH에 없는 환경에서도 동작.
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo [WARN] Dependency sync failed. Continuing with currently installed packages.
)

echo [3/3] Starting bot...
py bot_gui.py
if %errorlevel% neq 0 (
  echo.
  echo Bot exited with error. Press any key to close.
  pause >nul
)
