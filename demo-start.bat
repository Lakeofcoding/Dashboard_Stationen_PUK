@echo off
chcp 65001 >nul 2>&1
title PUK Dashboard - Demo
color 0A

echo.
echo  PUK Dashboard - Demo-Start
echo  ========================================
echo.

cd /d "%~dp0"

:: Pruefe Python
echo [1/4] Pruefe Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  FEHLER: Python nicht gefunden!
    echo  Bitte installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

:: Pruefe Node
echo [2/4] Pruefe Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  FEHLER: Node.js nicht gefunden!
    echo  Bitte installieren: https://nodejs.org/
    pause
    exit /b 1
)
node --version

:: Backend-Pakete pruefen
echo [3/4] Pruefe Abhaengigkeiten...
if exist "backend\.venv\Scripts\python.exe" (
    echo   Python-venv gefunden.
) else (
    python -c "import fastapi" >nul 2>&1
    if %errorlevel% neq 0 (
        echo   Installiere Backend-Pakete...
        pushd backend
        pip install -r requirements.txt -q
        popd
    )
)
if not exist "frontend\node_modules\." (
    echo   Installiere Frontend-Pakete...
    pushd frontend
    call npm install
    popd
)
echo   OK.

:: Server starten
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

:: Fertig
echo.
echo  ========================================
echo  Dashboard laeuft!
echo  ========================================
echo.
echo  Dieser PC:     http://localhost:5173
echo.
echo  Im Netzwerk:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set "IP=%%a"
    setlocal enabledelayedexpansion
    set "IP=!IP: =!"
    echo                  http://!IP!:5173
    endlocal
)
echo.
echo  Login: User "demo", dann Station waehlen
echo  API-Docs: http://localhost:8000/docs
echo.
echo  ========================================
echo  Dieses Fenster OFFEN lassen!
echo  ENTER zum Beenden.
echo  ========================================

timeout /t 2 /nobreak >nul
start "" "http://localhost:5173"

echo.
pause

echo Beende...
taskkill /f /fi "WINDOWTITLE eq PUK-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq PUK-Frontend" >nul 2>&1
echo Fertig.
timeout /t 2 /nobreak >nul
