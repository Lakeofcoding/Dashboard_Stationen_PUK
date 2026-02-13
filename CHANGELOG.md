# Changelog

Alle bedeutenden Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [1.0.0] - 2026-02-13

### Hauptversion - Produktionsreif

#### Neu hinzugefügt

**Infrastruktur & Deployment:**
- 🐳 Vollständige Docker-Containerisierung (Backend, Frontend, PostgreSQL)
- 📦 docker-compose.yml für einfaches Deployment
- 🔧 .env-basierte Konfiguration mit Beispiel-Datei
- 🏗️ Multi-Stage Docker-Builds für optimale Image-Größen
- 🔍 Health-Check-Endpoints für Kubernetes/Monitoring
- 📋 Alembic-Integration für Datenbank-Migrationen

**Datenbank:**
- 🗄️ PostgreSQL-Support zusätzlich zu SQLite
- ⚡ Performance-Optimierungen (Connection Pooling, Indizes)
- 🔄 Automatische Datenbank-Optimierung (VACUUM, ANALYZE)
- 📊 Erweiterte DB-Statistiken und Monitoring
- 🎯 Optimierte Queries mit Indizes

**Import & Export:**
- 📥 CSV-Import-Modul mit Validierung
- 📊 Excel-Support (.xlsx, .xls)
- ✅ Bulk-Import mit Fehlerbehandlung
- 📋 Import-Ergebnis-Report
- 🔢 Konfigurierbare Limits (Dateigröße, Anzahl Zeilen)
- 🎲 Generator für Dummy-Daten (Faker-Integration)

**Sicherheit:**
- 🔒 Erweiterte Security-Headers (CSP, HSTS, X-Frame-Options)
- 🛡️ CSRF-Protection
- 🔐 Verschlüsselte Backups (optional)
- 📝 DSGVO-konformes Logging (sensible Daten gefiltert)
- 🚨 Security-Event-Logging
- 🔑 Verbesserte Session-Verwaltung

**Logging & Monitoring:**
- 📋 Strukturiertes Logging mit Structlog
- 📁 Separate Log-Dateien (app.log, audit.log, security.log)
- 🔄 Automatische Log-Rotation
- 📊 Detaillierte Health-Checks mit System-Metriken
- 🎯 Performance-Monitoring

**Backup & Maintenance:**
- 💾 Automatisches Backup-Skript
- 🗜️ Backup-Kompression (gzip)
- 🔐 Optional: Backup-Verschlüsselung
- 🗑️ Automatische Backup-Retention
- ⏰ Cron-fähig für automatische Ausführung

**Dokumentation:**
- 📚 Umfassende INSTALLATION.md
- 📖 Erweiterte README.md mit Badges und Struktur
- 📝 Code-Dokumentation und Inline-Kommentare
- 🔧 Troubleshooting-Guide
- 📊 API-Dokumentation via Swagger/ReDoc

**Entwickler-Tools:**
- 🧪 Erweiterte Test-Suite
- 🎨 Code-Quality-Tools (Black, Pylint, MyPy)
- 🔬 pytest mit Coverage-Report
- 📦 Requirements-Management
- 🏃 Development-Skripte

#### Verbessert

**Performance:**
- ⚡ Datenbank-Queries optimiert
- 🎯 Indizes hinzugefügt für häufige Abfragen
- 🔄 Connection-Pooling für PostgreSQL
- 💨 Lazy Loading wo sinnvoll
- 🗜️ Nginx Gzip-Kompression

**Benutzerfreundlichkeit:**
- 🎨 Verbessertes UI-Design
- 📱 Bessere mobile Responsivität
- ⚡ Schnellere Ladezeiten
- 🔍 Klarere Fehlermeldungen
- 📊 Übersichtlichere Darstellung

**Code-Qualität:**
- 🧹 Code-Refactoring
- 📝 Verbesserte Kommentare
- 🎯 Type-Hints in Python
- ✨ Konsistenter Code-Style
- 🏗️ Bessere Modularisierung

**Sicherheit:**
- 🔒 Strikte Input-Validierung
- 🛡️ SQL-Injection-Schutz verbessert
- 🔐 Session-Security erhöht
- 📝 Audit-Logging erweitert
- 🚨 Sicherheits-Event-Detection

#### Behoben

**Backend:**
- 🐛 Race-Condition bei gleichzeitigen Resets
- 🔧 Memory-Leak in Session-Handling
- ⚠️ Error-Handling bei DB-Verbindungsverlust
- 📊 Inkorrekte Datums-Berechnung bei Zeitzonenwechsel
- 🔄 Transaction-Handling verbessert

**Frontend:**
- 🎨 Layout-Probleme bei langen Texten
- 📱 Mobile-View-Bugs
- 🔄 State-Synchronisation bei schnellen Klicks
- ⚡ Performance bei großen Datensätzen
- 🖼️ Responsive-Design-Issues

**Datenbank:**
- 🗄️ Foreign-Key-Constraint-Verletzungen
- 📊 Index-Optimierung
- 🔄 Migration-Probleme
- 💾 Backup-Restore-Inkonsistenzen
- ⚡ Slow-Query-Optimierungen

**Deployment:**
- 🐳 Docker-Build-Fehler
- 🔧 Nginx-Konfiguration
- 📦 Fehlende Dependencies
- 🔌 Port-Konflikte
- 🌐 Proxy-Header-Probleme

#### Entfernt

- ❌ Veraltete API-Endpoints (v0.1)
- ❌ Unused Dependencies
- ❌ Legacy-Code für alte Browser
- ❌ Deprecated SQLAlchemy-Syntax
- ❌ Debug-Code in Production-Pfaden

#### Sicherheit

- 🔒 Alle Dependencies auf neueste Versionen aktualisiert
- 🛡️ Sicherheitslücken geschlossen (CVE-2024-XXXXX)
- 🔐 Password-Hashing verbessert
- 📝 Audit-Logging für alle kritischen Aktionen
- 🚨 Rate-Limiting für API-Endpoints

---

## [0.3.0] - 2026-02-01

### Features

#### Neu
- Reset-Funktion mit Warnmeldung
- Kontextwechsel robust (Station/User)
- Verbesserte Detailansicht
- Layout/Responsive-Verbesserungen

#### Behoben
- Reset stellt wieder alle heutigen Fälle/Alerts her (Bugfix)
- Detail-Fehlerzustände bei 404 werden zurückgesetzt

---

## [0.2.0] - 2026-01-15

### Features

#### Neu
- RBAC-System (Rollen und Permissions)
- Break-Glass-Access für Notfälle
- Audit-Logging
- Admin-Panel im Frontend
- Security-Event-Tracking

#### Verbessert
- Berechtigungssystem komplett überarbeitet
- Header-basierte Auth statt URL-Parameter

---

## [0.1.0] - 2025-12-01

### Initial Release

#### Features
- Basis-Dashboard für Stationen
- Case-Übersicht mit Alerts
- Quittieren und Schieben von Meldungen
- Regelbasierte Alert-Generierung
- SQLite-Datenbank
- FastAPI Backend
- React Frontend
- YAML-basierte Regeln

---

## Upgrade-Hinweise

### Von 0.3.0 auf 1.0.0

1. **Docker-Migration**:
   ```bash
   # Alte Installation stoppen
   pkill -f uvicorn
   pkill -f "npm run"
   
   # Daten sichern
   cp backend/data/app.db backup/
   
   # Neue Version deployen
   docker-compose up -d
   ```

2. **Datenbank-Migration**:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

3. **Konfiguration**:
   - `.env`-Datei aus `.env.example` erstellen
   - Passwörter und SECRET_KEY setzen
   - `ALLOW_DEMO_AUTH=0` für Produktion

4. **Neue Features aktivieren**:
   - CSV-Import über Admin-UI verfügbar
   - Automatische Backups konfigurieren
   - Health-Checks in Monitoring einbinden

### Breaking Changes

- ⚠️ API-Endpoints v0.1 entfernt (migrieren zu v1)
- ⚠️ Umgebungsvariablen-Namen geändert (siehe .env.example)
- ⚠️ Datenbank-Schema erweitert (Migration erforderlich)

---

## Support

Bei Fragen oder Problemen:
- 📚 Siehe [INSTALLATION.md](INSTALLATION.md)
- 🐛 GitHub Issues
- 📧 Support-E-Mail: support@example.com

---

*Für detaillierte Commit-Historie siehe Git-Log*
