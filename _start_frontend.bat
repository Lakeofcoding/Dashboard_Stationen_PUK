@echo off
title PUK-Frontend
cd /d "%~dp0frontend"

:: Pruefe Node.js
where node >nul 2>&1
if %errorlevel% neq 0 goto :NO_NODE

:: Pruefe node_modules
if not exist "node_modules\." goto :INSTALL_FE

:START_FE
echo [Frontend] Starte Vite Dev-Server...
call npx vite --host 0.0.0.0
if %errorlevel% neq 0 (
    echo.
    echo Frontend-Start fehlgeschlagen!
    pause
)
goto :EOF

:INSTALL_FE
echo Frontend-Pakete fehlen. Installiere...
call npm install --loglevel error
goto :START_FE

:NO_NODE
echo FEHLER: Node.js nicht gefunden!
echo Bitte zuerst demo-prepare.bat ausfuehren.
pause
exit /b 1
