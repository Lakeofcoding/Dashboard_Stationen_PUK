@echo off
setlocal EnableDelayedExpansion
title PUK Dashboard - Demo-Start
color 0A
cd /d "%~dp0"
set "BASEDIR=%~dp0"

echo.
echo  +------------------------------------------------------+
echo  ^|   PUK Dashboard - One-Click Demo-Start              ^|
echo  +------------------------------------------------------+
echo.

:: ============================================================
:: Schritt 1: Python finden und TESTEN
:: ============================================================
echo [1/6] Pruefe Python...
set "PYTHON="

:: Zuerst python, dann python3 - jedes Mal TESTEN ob es wirklich laeuft
:: (Windows Store Alias wird so erkannt und uebersprungen)
for %%P in (python python3) do (
    if not defined PYTHON (
        where %%P >nul 2>&1
        if !errorlevel! equ 0 (
            %%P -c "import sys; sys.exit(0)" >nul 2>&1
            if !errorlevel! equ 0 set "PYTHON=%%P"
        )
    )
)
:: Fallback: py Launcher (Windows)
if not defined PYTHON (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        py -3 -c "import sys; sys.exit(0)" >nul 2>&1
        if !errorlevel! equ 0 set "PYTHON=py -3"
    )
)

if not defined PYTHON (
    echo.
    echo  FEHLER: Python nicht gefunden oder nicht funktionsfaehig.
    echo.
    echo  Moegliche Ursachen:
    echo    - Python nicht installiert
    echo    - Windows Store Python-Alias aktiv ^(deaktivieren in:
    echo      Einstellungen ^> Apps ^> App-Ausfuehrungsaliase^)
    echo.
    echo  Bitte Python 3.10+ von https://www.python.org/downloads/
    echo  installieren. Haken bei "Add Python to PATH" setzen!
    echo.
    goto :FATAL_ERROR
)
for /f "tokens=2 delims= " %%v in ('!PYTHON! --version 2^>^&1') do echo   Python %%v gefunden.

:: ============================================================
:: Schritt 2: Node.js
:: ============================================================
echo [2/6] Pruefe Node.js...
set "NODE_OK=0"
where node >nul 2>&1
if !errorlevel! equ 0 (
    node --version >nul 2>&1
    if !errorlevel! equ 0 set "NODE_OK=1"
)

if "!NODE_OK!"=="0" (
    echo   Node.js nicht gefunden. Versuche automatische Installation...
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Installiere via winget ^(bitte warten^)...
        winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        set "PATH=%ProgramFiles%\nodejs;%APPDATA%\npm;!PATH!"
        where node >nul 2>&1
        if !errorlevel! equ 0 set "NODE_OK=1"
    )
)

if "!NODE_OK!"=="0" (
    echo.
    echo  FEHLER: Node.js nicht gefunden.
    echo  Bitte von https://nodejs.org/ installieren ^(LTS-Version^).
    echo  Falls gerade installiert: Fenster schliessen und neu starten.
    echo.
    goto :FATAL_ERROR
)
for /f "tokens=1" %%v in ('node --version 2^>^&1') do echo   Node %%v gefunden.

:: ============================================================
:: Schritt 3: Konfiguration
:: ============================================================
echo [3/6] Pruefe Konfiguration...
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
    ) else (
        > ".env" (
            echo ALLOW_DEMO_AUTH=1
            echo DASHBOARD_ALLOW_DEMO_AUTH=1
            echo DEBUG=0
            echo LOG_LEVEL=INFO
            echo TZ=Europe/Zurich
        )
    )
    echo   .env erstellt.
) else (
    echo   .env vorhanden.
)
if not exist "backend\data" mkdir "backend\data" >nul 2>&1
if not exist "backend\logs" mkdir "backend\logs" >nul 2>&1

:: ============================================================
:: Schritt 4: Backend-Abhaengigkeiten
:: ============================================================
echo [4/6] Backend-Abhaengigkeiten...
pushd backend
if not exist "requirements.txt" (
    echo   FEHLER: backend/requirements.txt nicht gefunden!
    popd
    goto :FATAL_ERROR
)

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import fastapi" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   venv OK.
        goto :BACKEND_DEPS_DONE
    )
    echo   venv veraltet, erstelle neu...
    rmdir /s /q .venv >nul 2>&1
)

echo   Erstelle venv...
!PYTHON! -m venv .venv
if !errorlevel! neq 0 (
    echo   FEHLER: venv konnte nicht erstellt werden!
    echo   Tipp: Pruefen ob Python korrekt installiert ist.
    popd
    goto :FATAL_ERROR
)

echo   Installiere Pakete ^(bitte warten, kann 2-5 Min. dauern^)...
.venv\Scripts\python.exe -m pip install --upgrade pip -q --no-warn-script-location >nul 2>&1
.venv\Scripts\python.exe -m pip install -r requirements.txt -q --no-warn-script-location
if !errorlevel! neq 0 (
    echo.
    echo   FEHLER: pip install fehlgeschlagen!
    echo   Moegliche Ursachen:
    echo     - Kein Internet ^(wird fuer erstmalige Installation benoetigt^)
    echo     - Inkompatible Python-Version
    echo   Tipp: Manuell versuchen:
    echo     cd backend
    echo     .venv\Scripts\pip install -r requirements.txt
    popd
    goto :FATAL_ERROR
)

:BACKEND_DEPS_DONE
popd
echo   Backend bereit.

:: ============================================================
:: Schritt 5: Frontend-Abhaengigkeiten
:: ============================================================
echo [5/6] Frontend-Abhaengigkeiten...
pushd frontend
if not exist "package.json" (
    echo   FEHLER: frontend/package.json nicht gefunden!
    popd
    goto :FATAL_ERROR
)

if not exist "node_modules\vite" (
    echo   Installiere npm-Pakete ^(bitte warten^)...
    call npm install --loglevel warn --no-fund --no-audit
    if !errorlevel! neq 0 (
        echo   FEHLER: npm install fehlgeschlagen!
        popd
        goto :FATAL_ERROR
    )
) else (
    echo   node_modules OK.
)
popd

:: ============================================================
:: Schritt 6: Starten
:: ============================================================
echo [6/6] Starte Backend und Frontend...

:: --- Alte Prozesse aufräumen (Port 8000 + 5173) ---
echo   Raeume alte Prozesse auf...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173.*LISTENING" 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)
taskkill /f /fi "WINDOWTITLE eq PUK-Backend*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq PUK-Frontend*" >nul 2>&1
timeout /t 1 /nobreak >nul

:: --- SECRET_KEY: kurzer Demo-Key (unter 32 Zeichen, damit HARD FUSE nicht greift) ---
:: main.py blockiert absichtlich: langer Key + Demo-Modus = vermutlich Produktionsfehler
:: Fuer echten Betrieb: SECRET_KEY in .env setzen und ALLOW_DEMO_AUTH=0

:: --- Backend-Launcher als separate Datei schreiben ---
:: (Vermeidet komplexes Escaping in Klammer-Bloecken)
set "LAUNCHER_BE=%TEMP%\puk_backend_start.bat"
> "!LAUNCHER_BE!" echo @echo off
>> "!LAUNCHER_BE!" echo setlocal EnableDelayedExpansion
>> "!LAUNCHER_BE!" echo title PUK-Backend
>> "!LAUNCHER_BE!" echo cd /d "!BASEDIR!backend"
>> "!LAUNCHER_BE!" echo if not exist "!BASEDIR!.env" goto :puk_skip_env
>> "!LAUNCHER_BE!" echo for /f "usebackq eol=# tokens=1,* delims==" %%%%a in ("!BASEDIR!.env") do if not "%%%%a"=="" set "%%%%a=%%%%b"
>> "!LAUNCHER_BE!" echo :puk_skip_env
>> "!LAUNCHER_BE!" echo if not defined SECRET_KEY set "SECRET_KEY=demo-dev-key-only"
>> "!LAUNCHER_BE!" echo set PYTHONPATH=
>> "!LAUNCHER_BE!" echo echo Backend startet auf http://127.0.0.1:8000 ...
>> "!LAUNCHER_BE!" echo if exist ".venv\Scripts\python.exe" (.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000) else (python -m uvicorn main:app --host 127.0.0.1 --port 8000)
>> "!LAUNCHER_BE!" echo echo.
>> "!LAUNCHER_BE!" echo echo Backend wurde beendet. Druecke eine Taste...
>> "!LAUNCHER_BE!" echo pause

start "PUK-Backend" cmd /c "!LAUNCHER_BE!"
echo   Backend gestartet ^(eigenes Fenster^).
echo   Warte auf Startbereitschaft...

set /a WAITED=0
:HEALTHCHECK
timeout /t 3 /nobreak >nul
!PYTHON! -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >nul 2>&1
if !errorlevel! equ 0 goto :BACKEND_UP
set /a WAITED+=3
if !WAITED! geq 90 (
    echo.
    echo  WARNUNG: Backend antwortet nicht nach 90 Sek.
    echo  Bitte im Backend-Fenster nach Fehlermeldungen schauen.
    echo  Typische Fehler:
    echo    - Port 8000 bereits belegt ^(anderes Programm beenden^)
    echo    - Paket-Fehler ^(.venv loeschen und BAT neu starten^)
    echo.
    echo  Trotzdem fortfahren? ^(ENTER^)
    pause >nul
)
:BACKEND_UP
echo   Backend laeuft.

:: --- Frontend-Launcher schreiben ---
set "LAUNCHER_FE=%TEMP%\puk_frontend_start.bat"
> "!LAUNCHER_FE!" echo @echo off
>> "!LAUNCHER_FE!" echo title PUK-Frontend
>> "!LAUNCHER_FE!" echo cd /d "!BASEDIR!frontend"
>> "!LAUNCHER_FE!" echo echo Frontend startet auf http://localhost:5173 ...
>> "!LAUNCHER_FE!" echo call npm run dev
>> "!LAUNCHER_FE!" echo echo.
>> "!LAUNCHER_FE!" echo echo Frontend wurde beendet. Druecke eine Taste...
>> "!LAUNCHER_FE!" echo pause

start "PUK-Frontend" cmd /c "!LAUNCHER_FE!"
echo   Frontend gestartet...
timeout /t 6 /nobreak >nul

echo.
echo  +----------------------------------------------------------+
echo  ^|  PUK Dashboard laeuft!                                  ^|
echo  +----------------------------------------------------------+
echo.
echo  URL:    http://localhost:5173
echo.
echo  DEMO-LOGIN ^(kein Passwort^):
echo    demo       - Admin ^(alle Stationen^)
echo    arzt.a1    - Arzt Station A1
echo    sl.zape    - Schichtleitung
echo    admin      - System Administrator
echo.
echo  ENTER = Dashboard beenden
echo  +----------------------------------------------------------+

timeout /t 2 /nobreak >nul
start "" "http://localhost:5173"
echo.
pause
goto :SHUTDOWN

:: ============================================================
:: Fehlerbehandlung - faengt ALLE Fehler ab
:: ============================================================
:FATAL_ERROR
echo.
echo  +----------------------------------------------------------+
echo  ^|  FEHLER: Start abgebrochen. Siehe Meldungen oben.       ^|
echo  +----------------------------------------------------------+
echo.
echo  Druecke eine Taste zum Schliessen...
pause >nul
exit /b 1

:: ============================================================
:: Sauberes Beenden
:: ============================================================
:SHUTDOWN
echo   Beende...
taskkill /f /fi "WINDOWTITLE eq PUK-Backend*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq PUK-Frontend*" >nul 2>&1
del /q "!LAUNCHER_BE!" >nul 2>&1
del /q "!LAUNCHER_FE!" >nul 2>&1
echo   Fertig. Fenster schliesst in 3 Sekunden...
timeout /t 3 /nobreak >nul
exit /b 0
