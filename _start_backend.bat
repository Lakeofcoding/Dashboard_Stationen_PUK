@echo off
setlocal EnableDelayedExpansion
title PUK-Backend
cd /d "%~dp0backend"

:: .env laden (liegt eine Ebene hoeher)
if exist "..\.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("..\.env") do (
        if not "%%a"=="" set "%%a=%%b"
    )
)

:: SECRET_KEY: kurzer Demo-Key wenn nicht gesetzt
if not defined SECRET_KEY set "SECRET_KEY=demo-dev-key-only"

:: Python aus venv bevorzugen
set "PYTHON="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON=python"
    ) else (
        where python3 >nul 2>&1
        if !errorlevel! equ 0 set "PYTHON=python3"
    )
)
if not defined PYTHON (
    echo FEHLER: Python nicht gefunden.
    echo Bitte RUN_DEMO.bat verwenden oder Python installieren.
    pause
    exit /b 1
)

echo Backend startet auf http://127.0.0.1:8000 ...

:: Port 8000 freigeben falls noch belegt
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   Beende alten Prozess auf Port 8000 ^(PID %%p^)...
    taskkill /f /pid %%p >nul 2>&1
    timeout /t 1 /nobreak >nul
)

!PYTHON! -m uvicorn main:app --host 127.0.0.1 --port 8000
echo.
echo Backend wurde beendet.
pause
