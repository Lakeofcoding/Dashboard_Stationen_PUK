# Dashboard Stationen (PUK) – Klinisches Qualitäts-Dashboard

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourorg/puk-dashboard)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](docker-compose.yml)

## 🎯 Projektziel

Dieses System ist ein **offline-fähiges, datenschutzkonformes Dashboard** für psychiatrische Stationen zur Überwachung der Datenqualität und Vollständigkeit von Falldokumentation.

### Kernziele

- 🏥 **Klinischer Fokus**: Speziell für psychiatrische Stationen entwickelt
- 🔒 **Datenschutz**: Vollständig offline-fähig, keine externe Kommunikation
- ⚡ **Performance**: Optimiert für schnelle Übersicht und tagesbezogene Arbeit
- 🛡️ **Sicherheit**: RBAC, Audit-Logging, Break-Glass-Access
- 📊 **Qualität**: Regelbasierte Alerts für HONOS, BSCL, BFS und weitere Metriken
- 🔄 **Workflow**: Tagesbezogenes Quittieren und Schieben von Meldungen
- 🐳 **Deployment**: Vollständig containerisiert und produktionsbereit

### Hauptmerkmale

✅ **Schnelle Übersicht pro Station** mit Severity-Priorisierung (OK/WARN/CRITICAL)  
✅ **Tagesbezogene Arbeitsliste** mit Quittieren und Schieben (a/b/c)  
✅ **Reset-Funktion** für Geschäftstag  
✅ **CSV/Excel-Import** für Testdaten und Migration  
✅ **PostgreSQL oder SQLite** je nach Skalierungsanforderung  
✅ **Umfangreiches RBAC-System** mit Rollen und Permissions  
✅ **Break-Glass-Access** für Notfallzugriffe  
✅ **Vollständiges Audit-Logging** aller sicherheitsrelevanten Aktionen  
✅ **Health-Checks** für Monitoring und Kubernetes  
✅ **Automatische Backups** mit Rotation  

---

## 📋 Inhaltsverzeichnis

- [Schnellstart](#-schnellstart)
- [Architektur](#-architektur)
- [Installation](#-installation)
- [Konfiguration](#-konfiguration)
- [Verwendung](#-verwendung)
- [Entwicklung](#-entwicklung)
- [Deployment](#-deployment)
- [Sicherheit](#-sicherheit)
- [Wartung](#-wartung)
- [API-Dokumentation](#-api-dokumentation)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Schnellstart

### Mit Docker (EMPFOHLEN)

```bash
# 1. Repository klonen oder ZIP entpacken
cd puk-dashboard

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env  # Passwörter und SECRET_KEY anpassen!

# 3. Container starten
docker-compose up -d

# 4. Zugriff testen
curl http://localhost:8000/api/health
# Frontend: http://localhost:8080
# Backend API: http://localhost:8000
```

### Ohne Docker (Entwicklung)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DASHBOARD_ALLOW_DEMO_AUTH=1
uvicorn main:app --reload

# Frontend (neues Terminal)
cd frontend
npm install
npm run dev
```

**Standard-Login (nur Entwicklung!):**
- User: `demo`
- Rolle: `admin`

⚠️ **WICHTIG:** Für Produktion `DASHBOARD_ALLOW_DEMO_AUTH=0` setzen!

---

## 🏗️ Architektur

### Technologie-Stack

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (React)                   │
│  React 19 + TypeScript + Vite                      │
│  Port: 8080 (Nginx)                                │
└────────────────┬────────────────────────────────────┘
                 │ HTTP/REST
┌────────────────┴────────────────────────────────────┐
│                Backend (FastAPI)                    │
│  Python 3.11 + FastAPI + Pydantic                  │
│  Port: 8000 (Uvicorn)                              │
└────────────────┬────────────────────────────────────┘
                 │ SQLAlchemy ORM
┌────────────────┴────────────────────────────────────┐
│           Datenbank (PostgreSQL/SQLite)             │
│  - Cases & Alerts                                   │
│  - RBAC (Users, Roles, Permissions)                │
│  - Audit-Logs (Append-Only)                        │
│  - Versioned Day-State                             │
└─────────────────────────────────────────────────────┘
```

### Komponenten-Übersicht

#### Backend (`/backend`)
- **main.py**: Haupt-API mit allen Endpoints
- **app/models.py**: SQLAlchemy-Datenmodelle
- **app/rbac.py**: Role-Based Access Control
- **app/audit.py**: Audit-Logging
- **app/auth.py**: Authentifizierung
- **app/csv_import.py**: CSV/Excel-Import
- **app/health.py**: Health-Check-Endpoints
- **app/logging_config.py**: Strukturiertes Logging
- **app/db_enhanced.py**: Erweiterte DB-Konfiguration
- **scripts/backup.py**: Automatisches Backup

#### Frontend (`/frontend`)
- **App.tsx**: Haupt-Komponente
- **AdminPanel.tsx**: Admin-Interface
- **api.ts**: API-Client
- **types.ts**: TypeScript-Definitionen

#### Regelwerk (`/rules`)
- **rules.yaml**: Qualitätsregeln (editierbar via Admin-UI)

#### Deployment
- **docker-compose.yml**: Orchestrierung aller Services
- **Dockerfile** (Backend + Frontend)
- **nginx.conf**: Reverse Proxy Konfiguration

---

## 💿 Installation

Siehe [INSTALLATION.md](INSTALLATION.md) für detaillierte Installationsanleitungen.

### Kurzversion - Docker

```bash
# Voraussetzungen prüfen
docker --version  # >= 24.0
docker-compose --version  # >= 2.20

# Installation
cp .env.example .env
# .env bearbeiten (wichtig: Passwörter ändern!)
docker-compose up -d

# Status
docker-compose ps
docker-compose logs -f
```

### System-Requirements

**Minimal:**
- 2 CPU Cores
- 2 GB RAM
- 10 GB Disk

**Empfohlen (Produktion):**
- 4 CPU Cores
- 4-8 GB RAM
- 50 GB Disk (inkl. Logs/Backups)

---

## ⚙️ Konfiguration

### Umgebungsvariablen (.env)

```bash
# === DATENBANK ===
# SQLite (einfach, für < 5 Stationen)
DATABASE_URL=sqlite:///app/data/app.db

# PostgreSQL (empfohlen für Produktion)
DATABASE_URL=postgresql://dashboard_user:PASSWORD@postgres:5432/puk_dashboard
DB_PASSWORD=SECURE_PASSWORD_HERE

# === SICHERHEIT ===
# Demo-Auth NUR für Entwicklung!
ALLOW_DEMO_AUTH=0  # MUSS 0 sein in Produktion!
DEBUG=0            # MUSS 0 sein in Produktion!

# Secret Key für Sessions (generieren mit: openssl rand -hex 32)
SECRET_KEY=CHANGE_THIS_TO_RANDOM_STRING

# === LOGGING ===
LOG_LEVEL=INFO  # DEBUG|INFO|WARNING|ERROR|CRITICAL

# === FEATURES ===
MAX_CSV_ROWS=10000
MAX_CSV_FILE_SIZE_MB=50
SESSION_TIMEOUT_MINUTES=480  # 8 Stunden

# === BACKUP ===
ENABLE_AUTO_BACKUP=true
BACKUP_INTERVAL_HOURS=24
BACKUP_RETENTION_COUNT=30
```

### Datenbank-Wahl

#### SQLite (Standard)
- ✅ Keine separate Installation
- ✅ Einfache Backups
- ✅ Gut für < 5 Stationen
- ❌ Begrenzte Concurrent-Users

#### PostgreSQL (Empfohlen)
- ✅ Bessere Performance
- ✅ Skalierbar > 5 Stationen
- ✅ Erweiterte Features
- ❌ Separate Installation nötig

---

## 📖 Verwendung

### Basis-Workflow

1. **Login** als User mit entsprechenden Rechten
2. **Station wählen** im Dropdown
3. **Übersicht** zeigt alle Fälle mit Alerts
4. **Fall anklicken** für Details
5. **Meldungen bearbeiten**:
   - **Quittieren (ACK)**: Für heute ausblenden
   - **Schieben (a/b/c)**: Mit Kategorisierung verschieben
6. **Reset**: Neuer Geschäftstag (alle ACKs aufheben)

### Rollen und Rechte

Das System unterstützt folgende Basis-Rollen:

| Rolle | Rechte | Verwendung |
|-------|--------|-----------|
| `viewer` | Nur Lesen | Studierende, Hospitanten |
| `clinician` | Lesen + ACK/SHIFT | Ärzte, Pflegepersonal |
| `shift_lead` | + Reset | Schichtleiter |
| `manager` | + Break-Glass | Stationsleiter |
| `admin` | Voller Zugriff | IT-Administration |

### CSV-Import

```bash
# Via Admin-UI: "Daten" → "CSV Importieren"
# Oder via CLI:
docker-compose exec backend python -c "
from app.csv_import import CSVImporter
from app.db import SessionLocal

importer = CSVImporter()
with SessionLocal() as db:
    result = importer.import_from_file('data/import.csv', db)
    print(result)
"
```

**CSV-Format:**
```csv
case_id,station_id,patient_initials,admission_date,discharge_date,honos_entry_total,honos_discharge_total,...
CASE_001,ST01,AB,2026-01-15,2026-02-01,24,18,...
```

Siehe [sample_data.csv](backend/data/sample_data.csv) für vollständiges Beispiel.

---

## 🛠️ Entwicklung

### Lokale Entwicklung

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt

export DASHBOARD_ALLOW_DEMO_AUTH=1
export DASHBOARD_DEBUG=1

uvicorn main:app --reload --port 8000
```

```bash
# Frontend
cd frontend
npm install

# .env.local erstellen
echo "VITE_DEMO_AUTH=1" > .env.local

npm run dev
```

### Tests

```bash
# Backend-Tests
cd backend
pytest -v

# Mit Coverage
pytest --cov=app --cov-report=html
```

### Code-Qualität

```bash
# Backend
black app/  # Formatierung
pylint app/  # Linting
mypy app/  # Type-Checking

# Frontend
npm run lint
npm run build  # TypeScript-Check
```

### Datenbank-Migrationen

```bash
# Mit Alembic (für Schema-Änderungen)
cd backend

# Migration erstellen
alembic revision --autogenerate -m "Beschreibung"

# Migration anwenden
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🚢 Deployment

### Produktiv-Deployment

1. **Server vorbereiten**
   ```bash
   # Docker installieren
   curl -fsSL https://get.docker.com | sh
   
   # Firewall konfigurieren
   ufw allow 443/tcp  # HTTPS
   ufw deny 8000/tcp  # Backend direkt blockieren
   ```

2. **Anwendung deployen**
   ```bash
   # Code kopieren
   scp puk-dashboard.zip server:/opt/
   ssh server
   cd /opt && unzip puk-dashboard.zip
   
   # Konfigurieren
   cd puk-dashboard
   cp .env.example .env
   nano .env  # Konfiguration anpassen!
   
   # Starten
   docker-compose up -d
   ```

3. **Reverse Proxy konfigurieren**
   
   Siehe [INSTALLATION.md#reverse-proxy](INSTALLATION.md#reverse-proxy) für Nginx-Konfiguration mit:
   - TLS/SSL
   - SSO-Integration
   - Security Headers

4. **Monitoring einrichten**
   ```bash
   # Health-Check
   curl https://dashboard.klinik.local/api/health
   
   # Logs überwachen
   docker-compose logs -f --tail=100
   ```

### Kubernetes-Deployment

Für Kubernetes siehe [k8s/](k8s/) Verzeichnis mit:
- Deployments
- Services
- Ingress
- ConfigMaps
- Secrets

```bash
kubectl apply -f k8s/
```

---

## 🔒 Sicherheit

### Security-Features

✅ **RBAC**: Granulare Rechte-Verwaltung  
✅ **Audit-Logging**: Alle sicherheitsrelevanten Aktionen  
✅ **Break-Glass**: Notfallzugriff mit Audit  
✅ **Session-Management**: Timeout und Invalidierung  
✅ **Input-Validation**: Pydantic-Modelle  
✅ **SQL-Injection-Schutz**: SQLAlchemy ORM  
✅ **CSRF-Protection**: Token-basiert  
✅ **Security-Headers**: CSP, HSTS, X-Frame-Options  

### Datenschutz

- ✅ Vollständig offline-fähig
- ✅ Keine externe Kommunikation
- ✅ Sensible Daten gefiltert in Logs
- ✅ Patientendaten nur als Case-ID
- ✅ DSGVO-konform durch Design

### Sicherheits-Checkliste Produktion

- [ ] `ALLOW_DEMO_AUTH=0`
- [ ] `DEBUG=0`
- [ ] Starker `SECRET_KEY` (min. 32 Bytes random)
- [ ] Starke DB-Passwörter (min. 16 Zeichen)
- [ ] TLS/SSL aktiviert
- [ ] SSO/Authentication konfiguriert
- [ ] Firewall konfiguriert
- [ ] Security-Headers gesetzt
- [ ] Backups eingerichtet
- [ ] Log-Monitoring aktiviert

---

## 🔧 Wartung

### Backups

```bash
# Automatisches Backup (täglich 2 Uhr)
0 2 * * * /opt/puk-dashboard/backend/scripts/backup.py --retention-days 30

# Manuelles Backup
docker-compose exec backend python scripts/backup.py

# Backup mit Verschlüsselung
docker-compose exec backend python scripts/backup.py --encrypt --encryption-key $(openssl rand -base64 32)
```

### Monitoring

```bash
# Health-Check
curl http://localhost:8000/api/health

# Detaillierte Health-Info
curl http://localhost:8000/api/health/detailed

# Logs
docker-compose logs -f

# Ressourcen
docker stats
```

### Updates

```bash
# Code aktualisieren
git pull  # oder neue ZIP entpacken

# Container neu bauen und starten
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Datenbank-Migration
docker-compose exec backend alembic upgrade head
```

### Datenbank-Wartung

```bash
# SQLite optimieren
docker-compose exec backend python -c "
from app.db_enhanced import create_db_engine, optimize_database
engine = create_db_engine()
optimize_database(engine)
"

# PostgreSQL
docker-compose exec postgres psql -U dashboard_user -d puk_dashboard -c "VACUUM ANALYZE;"
```

---

## 📚 API-Dokumentation

Die interaktive API-Dokumentation ist verfügbar unter:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Wichtigste Endpoints

```
GET  /api/health                      # Health-Check
GET  /api/health/detailed             # Detaillierte System-Info
GET  /api/cases                       # Liste aller Fälle
GET  /api/cases/{case_id}             # Fall-Details
POST /api/ack                         # Meldung quittieren
POST /api/shift                       # Meldung schieben
POST /api/reset                       # Geschäftstag zurücksetzen
POST /api/import/csv                  # CSV-Import
GET  /api/admin/users                 # User-Verwaltung (Admin)
GET  /api/admin/audit                 # Audit-Log (Admin)
```

### Authentifizierung

```bash
# Header-basiert (Produktion mit SSO)
curl -H "X-User-Id: user123" \
     -H "X-Station-Id: ST01" \
     http://localhost:8000/api/cases

# Demo-Auth (nur Entwicklung!)
# Keine Header nötig wenn DASHBOARD_ALLOW_DEMO_AUTH=1
```

---

## 🐛 Troubleshooting

### Problem: Backend startet nicht

```bash
# Logs prüfen
docker-compose logs backend

# Häufige Ursachen:
# 1. Datenbank nicht erreichbar
docker-compose ps postgres

# 2. Port bereits belegt
sudo netstat -tlnp | grep 8000

# 3. Fehlende Umgebungsvariablen
docker-compose config
```

### Problem: Keine Verbindung zu Datenbank

```bash
# PostgreSQL Status
docker-compose exec postgres pg_isready

# Connection testen
docker-compose exec backend python -c "
from app.db_enhanced import check_database_connection, create_db_engine
engine = create_db_engine()
print('OK' if check_database_connection(engine) else 'FAILED')
"
```

### Problem: CSV-Import schlägt fehl

```bash
# Encoding prüfen
file -i import.csv

# Manuell testen
docker-compose exec backend python -c "
import pandas as pd
df = pd.read_csv('import.csv')
print(df.head())
print(df.columns)
"
```

### Problem: Frontend zeigt "Cannot connect"

```bash
# Backend erreichbar?
curl http://localhost:8000/api/health

# Nginx-Konfiguration prüfen
docker-compose exec frontend nginx -t

# Browser-Konsole prüfen (F12)
```

Weitere Lösungen: [INSTALLATION.md#troubleshooting](INSTALLATION.md#troubleshooting)

---

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

---

## 🤝 Beitragen

Contributions sind willkommen! Bitte beachten Sie:

1. Fork des Repositories
2. Feature-Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request erstellen

---

## 📞 Support

- **Dokumentation**: Siehe [INSTALLATION.md](INSTALLATION.md) und [API Docs](http://localhost:8000/docs)
- **Issues**: GitHub Issues
- **Security**: Sicherheitsprobleme bitte an security@example.com

---

## 🗺️ Roadmap

- [ ] FHIR-Integration für Datenimport
- [ ] Erweiterte Statistik-Dashboards
- [ ] Mobile App (iOS/Android)
- [ ] SAML2/OIDC Single Sign-On
- [ ] Erweiterte Regel-Engine mit ML-Support
- [ ] Multi-Tenancy für mehrere Kliniken

---

## 📜 Changelog

Siehe [CHANGELOG.md](CHANGELOG.md) für vollständige Versions-Historie.

### Version 1.0.0 (2026-02-13)

**Neu:**
- 🐳 Docker-Containerisierung
- 📊 CSV/Excel-Import
- 🗄️ PostgreSQL-Support
- 🔒 Erweiterte Sicherheit (CSRF, Security-Headers)
- 📝 Strukturiertes Logging
- 💾 Automatische Backups
- 🏥 Health-Check-Endpoints
- 📚 Umfassende Dokumentation

**Verbessert:**
- ⚡ Datenbank-Performance (Indizes, Optimierungen)
- 🎨 UI/UX-Verbesserungen
- 🐛 Diverse Bugfixes
- 📖 Code-Dokumentation

---

*Entwickelt mit ❤️ für die psychiatrische Versorgung*
