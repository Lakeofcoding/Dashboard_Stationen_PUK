#!/usr/bin/env bash
# PUK Dashboard - Quick Start Script
# Automatisierte Einrichtung und Start

set -e  # Exit bei Fehler

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Banner
echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   PUK Dashboard - Quick Start                            ║
║   Klinisches Qualitäts-Dashboard                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Funktion: Prüfe Voraussetzungen
check_prerequisites() {
    echo -e "${YELLOW}Prüfe Voraussetzungen...${NC}"
    
    # Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker nicht gefunden!${NC}"
        echo "Bitte Docker installieren: https://docs.docker.com/get-docker/"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker gefunden: $(docker --version)${NC}"
    
    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}✗ Docker Compose nicht gefunden!${NC}"
        echo "Bitte Docker Compose installieren: https://docs.docker.com/compose/install/"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker Compose gefunden: $(docker-compose --version)${NC}"
    
    # Disk Space
    available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -lt 10 ]; then
        echo -e "${YELLOW}⚠ Warnung: Nur ${available_space}GB freier Speicher (empfohlen: >10GB)${NC}"
    else
        echo -e "${GREEN}✓ Ausreichend Speicherplatz: ${available_space}GB${NC}"
    fi
}

# Funktion: Konfiguration erstellen
setup_configuration() {
    echo ""
    echo -e "${YELLOW}Erstelle Konfiguration...${NC}"
    
    if [ -f .env ]; then
        echo -e "${YELLOW}⚠ .env existiert bereits. Überschreiben? (y/N)${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Überspringe Konfiguration."
            return
        fi
    fi
    
    # .env aus Beispiel erstellen
    cp .env.example .env
    
    # Secret Key generieren
    secret_key=$(openssl rand -hex 32)
    sed -i.bak "s/SECRET_KEY=.*/SECRET_KEY=$secret_key/" .env
    
    # DB Passwort generieren
    db_password=$(openssl rand -base64 16)
    sed -i.bak "s/DB_PASSWORD=.*/DB_PASSWORD=$db_password/" .env
    
    echo -e "${GREEN}✓ Konfiguration erstellt (.env)${NC}"
    echo -e "${YELLOW}Bitte überprüfen Sie .env und passen Sie ggf. an!${NC}"
}

# Funktion: Produktions-Modus?
ask_production_mode() {
    echo ""
    echo -e "${YELLOW}Deployment-Modus wählen:${NC}"
    echo "1) Entwicklung (Demo-Auth aktiviert)"
    echo "2) Produktion (Sicher, ohne Demo-Auth)"
    read -p "Auswahl (1/2): " mode_choice
    
    case $mode_choice in
        2)
            echo -e "${GREEN}Produktions-Modus gewählt${NC}"
            sed -i.bak "s/ALLOW_DEMO_AUTH=.*/ALLOW_DEMO_AUTH=0/" .env
            sed -i.bak "s/DEBUG=.*/DEBUG=0/" .env
            ;;
        *)
            echo -e "${YELLOW}Entwicklungs-Modus gewählt${NC}"
            sed -i.bak "s/ALLOW_DEMO_AUTH=.*/ALLOW_DEMO_AUTH=1/" .env
            sed -i.bak "s/DEBUG=.*/DEBUG=1/" .env
            ;;
    esac
}

# Funktion: Datenbank wählen
ask_database_choice() {
    echo ""
    echo -e "${YELLOW}Datenbank wählen:${NC}"
    echo "1) SQLite (einfach, für < 5 Stationen)"
    echo "2) PostgreSQL (empfohlen für Produktion)"
    read -p "Auswahl (1/2): " db_choice
    
    case $db_choice in
        2)
            echo -e "${GREEN}PostgreSQL gewählt${NC}"
            sed -i.bak "s|DATABASE_URL=sqlite.*|DATABASE_URL=postgresql://dashboard_user:\${DB_PASSWORD}@postgres:5432/puk_dashboard|" .env
            ;;
        *)
            echo -e "${YELLOW}SQLite gewählt${NC}"
            sed -i.bak "s|DATABASE_URL=postgresql.*|DATABASE_URL=sqlite:///app/data/app.db|" .env
            ;;
    esac
}

# Funktion: Docker Images bauen
build_images() {
    echo ""
    echo -e "${YELLOW}Baue Docker-Images...${NC}"
    docker-compose build --no-cache
    echo -e "${GREEN}✓ Images gebaut${NC}"
}

# Funktion: Container starten
start_containers() {
    echo ""
    echo -e "${YELLOW}Starte Container...${NC}"
    docker-compose up -d
    echo -e "${GREEN}✓ Container gestartet${NC}"
}

# Funktion: Warte auf Services
wait_for_services() {
    echo ""
    echo -e "${YELLOW}Warte auf Services...${NC}"
    
    # Warte max 60 Sekunden
    max_wait=60
    count=0
    
    while [ $count -lt $max_wait ]; do
        if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Backend bereit${NC}"
            break
        fi
        echo -n "."
        sleep 1
        ((count++))
    done
    
    if [ $count -eq $max_wait ]; then
        echo -e "${RED}✗ Backend nicht erreichbar nach ${max_wait}s${NC}"
        echo "Logs prüfen mit: docker-compose logs backend"
        exit 1
    fi
}

# Funktion: Dummy-Daten importieren?
ask_import_dummy_data() {
    echo ""
    echo -e "${YELLOW}Dummy-Daten für Tests importieren? (y/N)${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Generiere und importiere Dummy-Daten...${NC}"
        docker-compose exec -T backend python -c "
from app.csv_import import generate_sample_csv
from pathlib import Path
csv_path = generate_sample_csv(Path('data/dummy_data.csv'), num_rows=100)
print(f'Dummy-Daten generiert: {csv_path}')
" || echo -e "${YELLOW}Hinweis: Dummy-Daten-Generator noch nicht implementiert${NC}"
    fi
}

# Funktion: Abschluss-Informationen
show_completion_info() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}║  ✓ Installation abgeschlossen!                           ║${NC}"
    echo -e "${GREEN}║                                                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Zugriff:${NC}"
    echo -e "  Frontend:  ${GREEN}http://localhost:8080${NC}"
    echo -e "  Backend:   ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    
    # Entwicklungs-Modus?
    if grep -q "ALLOW_DEMO_AUTH=1" .env 2>/dev/null; then
        echo -e "${YELLOW}Demo-Login (nur Entwicklung!):${NC}"
        echo -e "  User: ${GREEN}demo${NC}"
        echo -e "  Rolle: ${GREEN}admin${NC}"
        echo ""
    fi
    
    echo -e "${YELLOW}Nützliche Befehle:${NC}"
    echo "  make logs          # Logs anzeigen"
    echo "  make health        # Status prüfen"
    echo "  make down          # Container stoppen"
    echo "  make backup        # Backup erstellen"
    echo "  make help          # Alle Befehle"
    echo ""
    echo -e "${YELLOW}Dokumentation:${NC}"
    echo "  README.md"
    echo "  INSTALLATION.md"
    echo "  CHANGELOG.md"
    echo ""
}

# Haupt-Ablauf
main() {
    check_prerequisites
    setup_configuration
    ask_production_mode
    ask_database_choice
    build_images
    start_containers
    wait_for_services
    ask_import_dummy_data
    show_completion_info
    
    echo -e "${GREEN}Fertig! Das Dashboard ist bereit zur Verwendung.${NC}"
}

# Skript ausführen
main
