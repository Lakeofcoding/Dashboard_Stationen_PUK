@echo off
chcp 65001 >nul 2>&1
title PUK Dashboard - Vorbereitung
color 0E

echo.
echo  PUK Dashboard - Offline-Vorbereitung
echo  ========================================
echo.

cd /d "%~dp0"

:: 1) Python
echo [1/4] Pruefe Python...
where python >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   %%v
goto :CHECK_NODE

:NO_PYTHON
echo  FEHLER: Python nicht gefunden!
echo  Bitte installieren: https://www.python.org/downloads/
pause
exit /b 1

:: 2) Node.js
:CHECK_NODE
echo [2/4] Pruefe Node.js...
where node >nul 2>&1
if %errorlevel% equ 0 goto :NODE_OK
echo  FEHLER: Node.js nicht gefunden!
echo  Bitte installieren: https://nodejs.org/ (LTS)
echo  Oder:  winget install OpenJS.NodeJS.LTS
pause
exit /b 1

:NODE_OK
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   Node %%v

:: 3) Backend
echo [3/4] Backend vorbereiten...
pushd backend
if not exist ".venv" (
    python -m venv .venv
    echo   venv erstellt.
) else (
    echo   venv vorhanden.
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
python -c "import fastapi, sqlalchemy, yaml; print('  Backend-Module OK')"
popd

:: 4) Frontend
echo [4/4] Frontend vorbereiten...
pushd frontend
call npm install --loglevel error
echo   Frontend-Pakete OK.
popd

echo.
echo  ========================================
echo  Vorbereitung abgeschlossen!
echo  Zum Starten: Doppelklick auf demo-start.bat
echo  ========================================
echo.
pause
