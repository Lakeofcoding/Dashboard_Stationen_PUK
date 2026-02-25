@echo off
chcp 65001 >nul 2>&1
title PUK Dashboard - Demo
color 0A

echo.
echo  PUK Dashboard - Demo-Start
echo  ========================================
echo.

cd /d "%~dp0"

:: 1) Python pruefen
echo [1/4] Pruefe Python...
where python >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   %%v
goto :CHECK_NODE

:NO_PYTHON
echo.
echo  FEHLER: Python nicht gefunden!
echo  Bitte installieren: https://www.python.org/downloads/
echo  WICHTIG: "Add Python to PATH" ankreuzen!
echo.
pause
exit /b 1

:: 2) Node.js pruefen
:CHECK_NODE
echo [2/4] Pruefe Node.js...
where node >nul 2>&1
if %errorlevel% equ 0 goto :NODE_OK
echo.
echo  FEHLER: Node.js nicht gefunden!
echo  Bitte installieren: https://nodejs.org/ (LTS-Version)
echo  Oder per Terminal:  winget install OpenJS.NodeJS.LTS
echo  Danach dieses Fenster schliessen und neu starten.
echo.
pause
exit /b 1

:NODE_OK
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   Node %%v

:: 3) Abhaengigkeiten
echo [3/4] Pruefe Abhaengigkeiten...

pushd backend
if exist ".venv\Scripts\python.exe" goto :BE_OK
python -c "import fastapi" >nul 2>&1
if %errorlevel% equ 0 goto :BE_OK
echo   Installiere Backend-Pakete...
pip install -r requirements.txt -q --break-system-packages 2>nul
if %errorlevel% neq 0 pip install -r requirements.txt -q
:BE_OK
popd

if exist "frontend\node_modules\." goto :FE_OK
echo   Installiere Frontend-Pakete (1-2 Min.)...
pushd frontend
call npm install --loglevel error
popd
:FE_OK
echo   OK.

:: 4) Starten
echo [4/4] Starte Dashboard...
echo.

taskkill /f /fi "WINDOWTITLE eq PUK-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq PUK-Frontend" >nul 2>&1

start "" /min "%~dp0_start_backend.bat"
echo  Backend gestartet. Warte 5 Sek...
timeout /t 5 /nobreak >nul

start "" /min "%~dp0_start_frontend.bat"
echo  Frontend gestartet. Warte 5 Sek...
timeout /t 5 /nobreak >nul

echo.
echo  ========================================
echo  Dashboard laeuft!
echo  ========================================
echo  http://localhost:5173
echo  Login: User "demo", Station waehlen
echo  ========================================
echo  Fenster OFFEN lassen. ENTER = Beenden.
echo  ========================================

timeout /t 2 /nobreak >nul
start "" "http://localhost:5173"
pause

taskkill /f /fi "WINDOWTITLE eq PUK-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq PUK-Frontend" >nul 2>&1
