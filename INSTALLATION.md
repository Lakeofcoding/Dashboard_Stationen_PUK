# PUK Dashboard - Installations- und Deployment-Anleitung

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Systemvoraussetzungen](#systemvoraussetzungen)
3. [Installation](#installation)
4. [Konfiguration](#konfiguration)
5. [Deployment-Optionen](#deployment-optionen)
6. [Sicherheit](#sicherheit)
7. [Wartung und Backup](#wartung-und-backup)
8. [Troubleshooting](#troubleshooting)

---

## Überblick

Das PUK Dashboard ist ein Intranet-orientiertes System zur Überwachung der Datenqualität und Vollständigkeit auf psychiatrischen Stationen. Das System ist **vollständig offline-fähig** und für den Einsatz in klinischen Umgebungen ohne Internetzugang konzipiert.

### Architektur

- **Backend**: Python/FastAPI mit SQLite oder PostgreSQL
- **Frontend**: React/TypeScript mit Nginx
- **Deployment**: Docker Container (empfohlen) oder direkte Installation
- **Datenschutz**: Keine externe Kommunikation, alle Daten bleiben im lokalen Netzwerk

---

## Systemvoraussetzungen

### Minimale Anforderungen

- **CPU**: 2 Kerne
- **RAM**: 2 GB
- **Disk**: 10 GB freier Speicher
- **OS**: Linux (Ubuntu 22.04+, RHEL 8+) oder Windows Server 2019+

### Empfohlene Konfiguration

- **CPU**: 4 Kerne
- **RAM**: 4-8 GB
- **Disk**: 50 GB (inkl. Logs und Backups)
- **OS**: Ubuntu 24.04 LTS

### Software-Voraussetzungen

#### Für Docker-Deployment (empfohlen):
- Docker Engine 24.0+
- Docker Compose 2.20+

#### Für manuelle Installation:
- Python 3.11+
- Node.js 20+
- PostgreSQL 16+ (optional, aber empfohlen für Produktion)
- Nginx (für Frontend-Hosting)

---

## Installation

### Option 1: Docker-Deployment (EMPFOHLEN)

Dies ist die einfachste und sicherste Methode für den Produktiveinsatz.

#### Schritt 1: Repository klonen oder ZIP entpacken

```bash
# Falls Git verfügbar (nur auf Admin-Workstation):
git clone <repository-url> puk-dashboard
cd puk-dashboard

# ODER: ZIP-Datei auf Server kopieren und entpacken
unzip puk-dashboard.zip
cd puk-dashboard
```

#### Schritt 2: Umgebungsvariablen konfigurieren

```bash
# .env-Datei erstellen
cp .env.example .env

# .env-Datei bearbeiten
nano .env
```

**Wichtige Einstellungen in `.env`:**

```bash
# Datenbank (für Produktion PostgreSQL verwenden)
DATABASE_URL=postgresql://dashboard_user:SICHERES_PASSWORT@postgres:5432/puk_dashboard
DB_PASSWORD=SICHERES_PASSWORT

# Sicherheit (WICHTIG!)
ALLOW_DEMO_AUTH=0  # Muss 0 sein in Produktion!
DEBUG=0             # Muss 0 sein in Produktion!

# Secret Key generieren:
# openssl rand -hex 32
SECRET_KEY=<hier-zufälligen-string-einfügen>

# Logging
LOG_LEVEL=INFO

# Zeitzone
TZ=Europe/Zurich
```

#### Schritt 3: Container starten

```bash
# Alle Container starten
docker-compose up -d

# Logs überwachen
docker-compose logs -f

# Status prüfen
docker-compose ps
```

#### Schritt 4: Initiale Konfiguration

```bash
# Datenbank-Schema initialisieren (automatisch beim ersten Start)
# Demo-User, Admin-Rollen und Demo-Fälle werden automatisch angelegt
```

#### Schritt 5: Zugriff testen

```bash
# Frontend: http://<server-ip>:8080
# Backend API: http://<server-ip>:8000/health

# Health-Check
curl http://localhost:8000/health
```

### Option 2: Manuelle Installation

Für Umgebungen ohne Docker oder bei spezifischen Anforderungen.

#### Backend-Installation

```bash
cd backend

# Virtuelle Python-Umgebung erstellen
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ODER: .venv\Scripts\activate  # Windows

# Dependencies installieren
pip install --upgrade pip
pip install -r requirements.txt

# Datenbank konfigurieren
export DATABASE_URL="postgresql://user:password@localhost:5432/puk_dashboard"
export SECRET_KEY="<zufälliger-key>"
export ALLOW_DEMO_AUTH=0

# Datenbank initialisieren
python -c "from app.db import init_db; init_db()"

# Server starten
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

#### Frontend-Installation

```bash
cd frontend

# Dependencies installieren
npm ci --only=production

# Build erstellen
npm run build

# Mit Nginx ausliefern (nginx.conf siehe Projekt)
# Nginx-Konfiguration kopieren:
sudo cp nginx.conf /etc/nginx/sites-available/puk-dashboard
sudo ln -s /etc/nginx/sites-available/puk-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Konfiguration

### Datenbank-Auswahl

#### SQLite (Standard, für Entwicklung/kleine Installationen)

```bash
DATABASE_URL=sqlite:///./data/app.db
```

**Vorteile:**
- Keine separate Datenbank-Installation nötig
- Einfache Backups (Datei kopieren)
- Gut für < 5 Stationen

**Nachteile:**
- Begrenzte Concurrent-Users
- Keine erweiterten DB-Features

#### PostgreSQL (Empfohlen für Produktion)

```bash
DATABASE_URL=postgresql://dashboard_user:PASSWORD@postgres:5432/puk_dashboard
```

**Vorteile:**
- Bessere Performance bei vielen Usern
- Erweiterte Features (Volltextsuche, etc.)
- Bessere Backup-Optionen
- Skalierbar für > 5 Stationen

**Nachteile:**
- Separate Installation/Verwaltung erforderlich

### CSV-Datenimport konfigurieren

```bash
# Limits für CSV-Import
MAX_CSV_ROWS=10000
MAX_CSV_FILE_SIZE_MB=50
```

### Session-Timeout

```bash
# Session-Timeout in Minuten (Standard: 8 Stunden)
SESSION_TIMEOUT_MINUTES=480
```

### Logging

```bash
# Log-Level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Logs werden in folgende Dateien geschrieben:
# - logs/app.log (Allgemein)
# - logs/audit.log (Audit-Trail)
# - logs/security.log (Security-Events)
```

---

## Deployment-Optionen

### Production-Deployment mit Reverse Proxy

Für den Produktiveinsatz sollte ein Reverse Proxy (z.B. Nginx) vor der Anwendung laufen:

```nginx
# /etc/nginx/sites-available/puk-dashboard-prod

upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    server_name dashboard.klinik.local;

    # SSL-Zertifikate
    ssl_certificate /etc/ssl/certs/dashboard.crt;
    ssl_certificate_key /etc/ssl/private/dashboard.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;

    # Client-Zertifikat (optional)
    # ssl_client_certificate /etc/ssl/certs/ca.crt;
    # ssl_verify_client on;

    # Authentifizierung über SSO/Header
    # auth_request /auth;
    # auth_request_set $auth_user $upstream_http_x_user_id;
    # auth_request_set $auth_station $upstream_http_x_station_id;

    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # User-Context weiterleiten
        # proxy_set_header X-User-Id $auth_user;
        # proxy_set_header X-Station-Id $auth_station;
    }

    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # User-Context weiterleiten
        # proxy_set_header X-User-Id $auth_user;
        # proxy_set_header X-Station-Id $auth_station;
    }
}
```

### Firewall-Konfiguration

```bash
# Nur notwendige Ports öffnen (UFW Beispiel)
sudo ufw allow 443/tcp  # HTTPS (Reverse Proxy)
sudo ufw deny 8000/tcp  # Backend direkt blockieren
sudo ufw deny 8080/tcp  # Frontend direkt blockieren
sudo ufw deny 5432/tcp  # PostgreSQL blockieren
```

### Systemd-Service (für manuelle Installation)

```ini
# /etc/systemd/system/puk-dashboard-backend.service

[Unit]
Description=PUK Dashboard Backend
After=network.target postgresql.service

[Service]
Type=simple
User=puk-dashboard
Group=puk-dashboard
WorkingDirectory=/opt/puk-dashboard/backend
Environment="PATH=/opt/puk-dashboard/backend/.venv/bin"
Environment="DATABASE_URL=postgresql://user:pass@localhost/puk_dashboard"
Environment="SECRET_KEY=<secret>"
ExecStart=/opt/puk-dashboard/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable puk-dashboard-backend
sudo systemctl start puk-dashboard-backend
sudo systemctl status puk-dashboard-backend
```

---

## Sicherheit

### Sicherheits-Checkliste für Produktion

- [ ] `ALLOW_DEMO_AUTH=0` gesetzt
- [ ] `DEBUG=0` gesetzt
- [ ] Starker `SECRET_KEY` generiert
- [ ] Starke Datenbank-Passwörter verwendet
- [ ] Reverse Proxy mit TLS konfiguriert
- [ ] Security Headers gesetzt
- [ ] Firewall konfiguriert
- [ ] Direkter Zugriff auf Backend/DB blockiert
- [ ] SSO/Authentication konfiguriert
- [ ] Regelmäßige Backups eingerichtet
- [ ] Log-Monitoring eingerichtet
- [ ] Ressourcen-Limits gesetzt

### Netzwerk-Isolation

```bash
# Docker-Netzwerk isolieren (in docker-compose.yml)
networks:
  puk_network:
    driver: bridge
    internal: true  # Kein Zugriff nach außen
```

### Benutzer-Authentifizierung

Das System unterstützt mehrere Authentifizierungsmethoden:

1. **Demo-Auth** (nur Entwicklung!)
2. **Header-based Auth** (für SSO-Integration)
3. **Client-Zertifikate** (für höchste Sicherheit)

Produktiv-Konfiguration:

```python
# In Reverse Proxy: User-ID aus SSO in Header setzen
# X-User-Id: <user-id>
# X-Station-Id: <station-id>

# Backend validiert gegen Datenbank und Rollen
```

---

## Wartung und Backup

### Automatische Backups

```bash
# Cron-Job für tägliche Backups (SQLite)
0 2 * * * cp /opt/puk-dashboard/backend/data/app.db /opt/backups/app_$(date +\%Y\%m\%d).db
```

### Manuelles Backup

```bash
# SQLite
cp data/app.db backups/app_$(date +%Y%m%d).db

# PostgreSQL
pg_dump -U dashboard_user -d puk_dashboard | gzip > backups/backup_$(date +%Y%m%d).sql.gz
```

### Restore von Backup

```bash
# SQLite
cp backups/app_20260213.db data/app.db

# PostgreSQL
gunzip < backups/backup_20260213.sql.gz | psql -U dashboard_user -d puk_dashboard
```

### Log-Rotation

```bash
# /etc/logrotate.d/puk-dashboard

/opt/puk-dashboard/backend/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0640 puk-dashboard puk-dashboard
    sharedscripts
    postrotate
        docker-compose exec backend kill -USR1 1 2>/dev/null || true
    endscript
}
```

### Datenbank-Wartung

```bash
# Wöchentliche Optimierung (SQLite)
docker-compose exec backend python -c "from app.db import SessionLocal; db=SessionLocal(); db.execute('VACUUM'); db.execute('ANALYZE'); db.close()"

# PostgreSQL VACUUM (automatisch, aber kann manuell getriggert werden)
docker-compose exec postgres psql -U dashboard_user -d puk_dashboard -c "VACUUM ANALYZE;"
```

---

## Troubleshooting

### Backend startet nicht

```bash
# Logs prüfen
docker-compose logs backend

# Häufige Probleme:
# 1. Datenbank nicht erreichbar
docker-compose ps postgres

# 2. Fehlende Umgebungsvariablen
docker-compose config

# 3. Port bereits belegt
sudo netstat -tlnp | grep 8000
```

### Frontend zeigt "Cannot connect to backend"

```bash
# Backend-Erreichbarkeit testen
curl http://localhost:8000/health

# Nginx-Konfiguration prüfen
docker-compose exec frontend nginx -t

# Proxy-Einstellungen prüfen (nginx.conf)
```

### Datenbank-Verbindungsfehler

```bash
# PostgreSQL Status
docker-compose exec postgres pg_isready

# Logs
docker-compose logs postgres

# Connection-String prüfen
echo $DATABASE_URL
```

### Performance-Probleme

```bash
# System-Ressourcen prüfen
docker stats

# Datenbank-Performance
docker-compose exec backend python -c "from app.health import *; import json; from app.db import SessionLocal, engine; print(json.dumps(get_detailed_health(SessionLocal(), engine).dict(), indent=2))"

# Indizes prüfen (PostgreSQL)
docker-compose exec postgres psql -U dashboard_user -d puk_dashboard -c "\di"
```

### CSV-Import schlägt fehl

```bash
# Datei-Encoding prüfen
file -i import.csv

# Logs prüfen
docker-compose logs backend | grep import

# Validierung testen
docker-compose exec backend python -c "import pandas as pd; df = pd.read_csv('import.csv'); print(df.head())"
```

---

## Support und Kontakt

Für technische Fragen und Support:

- **Dokumentation**: Siehe README.md und API-Dokumentation unter `/api/docs`
- **Logs**: Siehe `logs/` Verzeichnis
- **Health-Check**: `http://<server>/health`

---

*Letzte Aktualisierung: 2026-02-13*
