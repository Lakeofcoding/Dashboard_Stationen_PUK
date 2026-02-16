@echo off
chcp 65001 >nul 2>&1
title PUK Dashboard - Vorbereitung
color 0E

echo.
echo  PUK Dashboard - Offline-Vorbereitung
echo  ========================================
echo  Installiert alle Pakete, damit die Demo
echo  spaeter OHNE Internet funktioniert.
echo  ========================================
echo.

cd /d "%~dp0"

echo [1/3] Erstelle Python-Umgebung...
pushd backend
if not exist ".venv" (
    python -m venv .venv
    echo   venv erstellt.
) else (
    echo   venv existiert bereits.
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo   Backend-Pakete installiert.
popd

echo [2/3] Installiere Frontend-Pakete...
pushd frontend
call npm install
echo   Frontend-Pakete installiert.
popd

echo [3/3] Teste...
pushd backend
call .venv\Scripts\activate.bat
python -c "import fastapi, sqlalchemy, yaml; print('  Backend OK')"
popd

echo.
echo  ========================================
echo  Vorbereitung abgeschlossen!
echo.
echo  In der Klinik:
echo    Doppelklick auf demo-start.bat
echo.
echo  Voraussetzung am Ziel-PC:
echo    Python 3.11+ und Node.js 20+
echo  ========================================
echo.
pause
