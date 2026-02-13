# Sicherheitsrichtlinien - PUK Dashboard

## Übersicht

Dieses Dokument beschreibt die Sicherheitsmaßnahmen und Best Practices für das PUK Dashboard.

## 🔒 Sicherheitsarchitektur

### Mehrschichtige Sicherheit (Defense in Depth)

1. **Netzwerk-Ebene**: Firewall, Netzwerk-Segmentierung
2. **Transport-Ebene**: TLS/SSL, Certificate Pinning
3. **Anwendungs-Ebene**: RBAC, Input-Validation, CSRF-Protection
4. **Daten-Ebene**: Verschlüsselung, Zugriffskontrolle
5. **Audit-Ebene**: Logging, Monitoring, Alerting

## 🛡️ Implementierte Sicherheitsmaßnahmen

### Authentifizierung & Autorisierung

- ✅ **RBAC**: Role-Based Access Control mit granularen Permissions
- ✅ **Break-Glass Access**: Auditierter Notfallzugriff
- ✅ **Session-Management**: Timeout, sichere Cookies
- ✅ **SSO-Ready**: Vorbereitet für SAML2/OIDC-Integration

### Input-Validierung

- ✅ **Pydantic Models**: Automatische Validierung aller Eingaben
- ✅ **SQL-Injection-Schutz**: SQLAlchemy ORM
- ✅ **XSS-Prevention**: React auto-escaping
- ✅ **CSRF-Protection**: Token-basiert
- ✅ **File-Upload-Limits**: Größe, Typ, Anzahl

### Datenschutz

- ✅ **Offline-First**: Keine externe Kommunikation
- ✅ **Daten-Minimierung**: Nur Case-IDs, keine Patientennamen
- ✅ **Log-Filtering**: Sensible Daten automatisch gefiltert
- ✅ **Audit-Trail**: Append-only Logging
- ✅ **DSGVO-konform**: Privacy by Design

### Transport-Sicherheit

- ✅ **TLS 1.2+**: Verschlüsselte Verbindungen
- ✅ **HSTS**: Strict Transport Security
- ✅ **Security-Headers**: CSP, X-Frame-Options, etc.
- ✅ **Certificate-Validation**: Kein Self-Signed in Produktion

### Datenbank-Sicherheit

- ✅ **Prepared Statements**: ORM-basiert
- ✅ **Least-Privilege**: Minimale DB-Rechte
- ✅ **Connection-Pooling**: Ressourcen-Limits
- ✅ **Backup-Verschlüsselung**: Optional

## ⚠️ Sicherheits-Checkliste Produktion

### Vor Deployment

- [ ] `.env`-Datei konfiguriert und gesichert
- [ ] `ALLOW_DEMO_AUTH=0` gesetzt
- [ ] `DEBUG=0` gesetzt
- [ ] `SECRET_KEY` mit min. 32 Bytes Random
- [ ] Starke DB-Passwörter (min. 16 Zeichen)
- [ ] TLS-Zertifikate gültig und konfiguriert
- [ ] Firewall-Regeln aktiv
- [ ] Security-Headers im Reverse Proxy
- [ ] Backup-Strategie implementiert

### Nach Deployment

- [ ] Health-Checks funktionieren
- [ ] Logs werden geschrieben
- [ ] Monitoring läuft
- [ ] Backup-Tests durchgeführt
- [ ] Security-Scan durchgeführt
- [ ] Penetration-Test (optional)

### Laufend

- [ ] Regelmäßige Updates (monatlich)
- [ ] Log-Monitoring
- [ ] Backup-Überprüfung (wöchentlich)
- [ ] Security-Event-Review
- [ ] Vulnerability-Scans

## 🚨 Bekannte Einschränkungen

### Entwicklungs-Features (NICHT in Produktion!)

**Demo-Authentifizierung** (`ALLOW_DEMO_AUTH=1`):
- ⚠️ Umgeht alle Sicherheitsprüfungen
- ⚠️ Nur für lokale Entwicklung
- ⚠️ **MUSS** in Produktion deaktiviert sein

**Debug-Modus** (`DEBUG=1`):
- ⚠️ Zeigt detaillierte Fehlermeldungen
- ⚠️ Kann sensible Informationen leaken
- ⚠️ **MUSS** in Produktion deaktiviert sein

## 🔐 Passwort-Richtlinien

### Für System-Accounts

- Mindestens 16 Zeichen
- Groß-/Kleinbuchstaben, Zahlen, Sonderzeichen
- Keine Wörter aus Wörterbüchern
- Generierung: `openssl rand -base64 24`

### Für Benutzer (falls implementiert)

- Mindestens 12 Zeichen
- Komplexität: 3 von 4 (Groß/Klein/Zahl/Sonderzeichen)
- Passwort-History: 5
- Max-Alter: 90 Tage

## 🎯 Security-Headers

Folgende Headers werden im Reverse Proxy gesetzt:

```nginx
# Strenge Transport-Sicherheit
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

# Frame-Schutz
X-Frame-Options: SAMEORIGIN

# Content-Type-Sniffing verhindern
X-Content-Type-Options: nosniff

# XSS-Filter aktivieren
X-XSS-Protection: 1; mode=block

# Referrer-Policy
Referrer-Policy: strict-origin-when-cross-origin

# Content-Security-Policy
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self';

# Permissions-Policy
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

## 📊 Audit-Logging

### Was wird geloggt?

**Security-Events**:
- Login-Versuche (erfolgreich/fehlgeschlagen)
- Berechtigungs-Ablehnungen
- Break-Glass-Aktivierungen
- Admin-Aktionen
- Konfigurationsänderungen

**Audit-Events**:
- Case-Zugriffe
- ACK/SHIFT-Aktionen
- Reset-Operationen
- Daten-Importe
- User-/Rollen-Änderungen

### Was wird NICHT geloggt?

- Patientennamen
- Gesundheitsdaten im Klartext
- Passwörter
- API-Keys
- Session-Tokens

## 🔍 Monitoring & Alerting

### Kritische Events (sofort alertieren)

- Mehrfache fehlgeschlagene Logins
- Nicht-autorisierte Zugriffe
- Break-Glass-Aktivierungen
- Datenbank-Verbindungsfehler
- Disk-Space < 5%

### Warnungen (täglich reviewen)

- Ungewöhnliche Zugriffsmuster
- Große Datenmengen-Exporte
- Häufige Reset-Operationen
- Performance-Degradation

## 🚨 Incident-Response

### Bei Sicherheitsvorfall

1. **Eindämmen**: Betroffene Systeme isolieren
2. **Analysieren**: Logs prüfen, Scope bestimmen
3. **Beheben**: Schwachstelle schließen
4. **Wiederherstellen**: System aus Backup
5. **Dokumentieren**: Incident-Report
6. **Lernen**: Post-Mortem durchführen

### Kontakt

- **Security-Team**: security@example.com
- **Notfall (24/7)**: +41 XX XXX XX XX

## 🔄 Update-Prozess

### Security-Updates (sofort)

1. Vulnerability-Report prüfen
2. Patch-Verfügbarkeit prüfen
3. In Test-Umgebung testen
4. Backup erstellen
5. Update in Produktion
6. Funktions-Tests
7. Monitoring intensivieren

### Regular Updates (monatlich)

1. Release-Notes prüfen
2. Test-Deployment
3. Produktions-Deployment im Wartungsfenster

## 📋 Compliance

### DSGVO-Anforderungen

- ✅ **Privacy by Design**: Daten-Minimierung
- ✅ **Zweckbindung**: Nur Qualitätssicherung
- ✅ **Transparenz**: Audit-Logs
- ✅ **Datensicherheit**: Verschlüsselung, Zugriffskontrolle
- ✅ **Auskunftsrecht**: Audit-Log-Export möglich
- ✅ **Löschrecht**: Manuelle Löschung möglich
- ✅ **Datenportabilität**: CSV-Export

### Klinische Standards

- ✅ **IHE-konform**: Integration Healthcare Enterprise
- ✅ **FHIR-ready**: Vorbereitet für FHIR-Integration
- ✅ **HL7-kompatibel**: Datenstrukturen aligned

## 🛠️ Security-Tools

### Entwicklung

```bash
# Dependency-Check
pip-audit  # Python
npm audit  # Node.js

# Code-Scanning
bandit app/  # Python Security Linter
semgrep --config=auto app/  # Multi-Language Scanner

# Secret-Scanning
gitleaks detect  # Git History Scanner
```

### Produktion

```bash
# Vulnerability-Scanning
trivy image puk-dashboard-backend:latest
trivy image puk-dashboard-frontend:latest

# Container-Scanning
docker scan puk-dashboard-backend:latest

# Network-Scanning
nmap -sV <host>
```

## 📝 Weitere Ressourcen

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [BSI IT-Grundschutz](https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/IT-Grundschutz/it-grundschutz_node.html)

---

## Verantwortliche Disclosure

Wenn Sie eine Sicherheitslücke finden:

1. **NICHT** öffentlich posten
2. E-Mail an security@example.com
3. Details beschreiben (PoC wenn möglich)
4. Angemessene Zeit für Fix gewähren (90 Tage)

Wir danken allen Sicherheitsforschern für verantwortungsvolle Disclosure!

---

*Letzte Aktualisierung: 2026-02-13*
