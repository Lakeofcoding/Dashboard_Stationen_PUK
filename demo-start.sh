#!/usr/bin/env bash
# =============================================================================
# PUK Dashboard - Demo-Start (Mac / Linux)
#
# Doppelklick oder: ./demo-start.sh
# Startet Backend + Frontend und öffnet den Browser.
# =============================================================================

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                   ║${NC}"
echo -e "${GREEN}║   PUK Dashboard - Demo-Start                     ║${NC}"
echo -e "${GREEN}║   Klinisches Qualitäts-Dashboard                 ║${NC}"
echo -e "${GREEN}║                                                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# PID-Tracking für Cleanup
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}Beende Dashboard...${NC}"
    [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null
    echo -e "${GREEN}Fertig.${NC}"
}
trap cleanup EXIT INT TERM

# ─── Prüfe Python ───────────────────────────────────────
echo -e "[1/5] Prüfe Python..."
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo -e "${RED}FEHLER: Python nicht gefunden!${NC}"
    echo "  Bitte Python 3.11+ installieren."
    echo "  Mac: brew install python3"
    echo "  Linux: sudo apt install python3 python3-pip"
    exit 1
fi
PY=$(command -v python3 || command -v python)
echo -e "  ${GREEN}OK: $($PY --version)${NC}"

# ─── Prüfe Node.js ──────────────────────────────────────
echo -e "[2/5] Prüfe Node.js..."
if ! command -v node &>/dev/null; then
    echo -e "${RED}FEHLER: Node.js nicht gefunden!${NC}"
    echo "  Bitte Node.js 20+ installieren: https://nodejs.org/"
    exit 1
fi
echo -e "  ${GREEN}OK: Node.js $(node --version)${NC}"

# ─── Backend-Abhängigkeiten ─────────────────────────────
echo -e "[3/5] Prüfe Backend-Abhängigkeiten..."
cd backend
if [ -d ".venv" ]; then
    echo -e "  Nutze vorbereitete Python-Umgebung (.venv)"
    source .venv/bin/activate
elif ! $PY -c "import fastapi" 2>/dev/null; then
    echo -e "  ${YELLOW}Erstelle Python-Umgebung und installiere Abhängigkeiten...${NC}"
    $PY -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt --quiet
else
    echo -e "  System-Python mit installierten Paketen."
fi
echo -e "  ${GREEN}Backend OK.${NC}"
cd ..

# ─── Frontend-Abhängigkeiten ────────────────────────────
echo -e "[4/5] Prüfe Frontend-Abhängigkeiten..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo -e "  ${YELLOW}Installiere Frontend-Abhängigkeiten...${NC}"
    npm install --silent
fi
echo -e "  ${GREEN}Frontend OK.${NC}"
cd ..

# ─── Starte Server ──────────────────────────────────────
echo -e "[5/5] Starte Dashboard..."

# Backend starten (nutzt venv wenn vorhanden)
cd backend
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

sleep 2

# Frontend starten
cd frontend
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!
cd ..

sleep 3

# ─── IP-Adresse für Netzwerk ────────────────────────────
LOCAL_IP=""
if command -v ifconfig &>/dev/null; then
    LOCAL_IP=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}')
elif command -v ip &>/dev/null; then
    LOCAL_IP=$(ip -4 addr show scope global 2>/dev/null | grep inet | head -1 | awk '{print $2}' | cut -d/ -f1)
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                   ║${NC}"
echo -e "${GREEN}║   ✓ Dashboard gestartet!                         ║${NC}"
echo -e "${GREEN}║                                                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Auf DIESEM Rechner:${NC}"
echo -e "    ${GREEN}http://localhost:5173${NC}"
echo ""
if [ -n "$LOCAL_IP" ]; then
    echo -e "  ${BOLD}Für ANDERE Rechner im Netzwerk:${NC}"
    echo -e "    ${GREEN}http://${LOCAL_IP}:5173${NC}"
    echo ""
fi
echo -e "  Login: User ${BOLD}demo${NC} / Station wählen"
echo ""
echo -e "  ─────────────────────────────────────────────────"
echo -e "  ${YELLOW}Ctrl+C zum Beenden${NC}"
echo -e "  ─────────────────────────────────────────────────"

# Browser öffnen
if command -v open &>/dev/null; then
    open "http://localhost:5173"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:5173"
fi

# Warten
wait
