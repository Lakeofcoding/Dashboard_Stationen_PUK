@echo off
title PUK-Backend
cd /d "%~dp0backend"

:: Versuche venv
if exist ".venv\Scripts\python.exe" goto :USE_VENV

:: Kein venv -> System-Python
where python >nul 2>&1
if %errorlevel% neq 0 goto :NO_PYTHON

:: Pruefe uvicorn
python -c "import uvicorn" >nul 2>&1
if %errorlevel% neq 0 goto :INSTALL_DEPS

:USE_SYSTEM
echo [Backend] Starte mit System-Python...
python -m uvicorn main:app --host 0.0.0.0 --port 8000
goto :CHECK_EXIT

:USE_VENV
echo [Backend] Starte mit venv...
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
goto :CHECK_EXIT

:INSTALL_DEPS
echo Backend-Pakete fehlen. Installiere...
pip install -r requirements.txt -q --break-system-packages 2>nul
if %errorlevel% neq 0 pip install -r requirements.txt -q
goto :USE_SYSTEM

:NO_PYTHON
echo FEHLER: Python nicht gefunden!
echo Bitte zuerst demo-prepare.bat ausfuehren.
pause
exit /b 1

:CHECK_EXIT
if %errorlevel% neq 0 (
    echo.
    echo Backend-Start fehlgeschlagen!
    pause
)
