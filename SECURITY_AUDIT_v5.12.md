# Security Audit — PUK Dashboard v5.12

## Methodik

Systematische Code-Analyse aller 60+ Dateien nach OWASP Top 10, mit Fokus auf:
Authentifizierung, Autorisierung, Injection, IDOR, File Upload, Session Management, klinische Datenintegrität.

---

## 🔴 Kritisch (sofort beheben)

### 1. Auth-Header-Spoofing — Kein echtes Identity Management

**Ort:** `backend/app/auth.py:83`
```python
user_id = (x_user_id or "demo").strip() or "demo"
```

**Problem:** Die gesamte Authentifizierung basiert auf dem Header `X-User-Id`, der clientseitig frei gesetzt wird. Jeder kann sich als beliebiger User ausgeben — Admin, Arzt, Manager.

**Risiko:** Vollständige Privilege Escalation. Ein Angreifer, der die API-URL kennt, kann:
- Admin-Aktionen ausführen (`X-User-Id: admin`)
- Patientendaten aller Stationen lesen
- Quittierungen für fremde Stationen vornehmen
- Regeln deaktivieren, Break-Glass aktivieren

**Fix für Produktion (zwingend):**
- SSO-Integration (SAML/OIDC) über Reverse Proxy
- JWT/Session-Token statt Header-Trust
- Header `X-User-Id` nur aus verifizierter SSO-Session ableiten
- Der DEMO_MODE-Guard existiert (`main.py:48`) — aber nur als Startup-Check, nicht als Runtime-Schutz

### 2. Debug-Endpoints in Produktion exponiert

**Ort:** `backend/main.py`
```python
app.include_router(debug_router, tags=["debug"])
```

**Endpoints:**
- `GET /api/debug/rules` — alle Regeldefinitionen
- `GET /api/debug/eval/{case_id}` — Fall-Evaluation mit vollen Alerts
- `GET /api/debug/ack-events` — alle ACK-Events

**Problem:** Kein `DEMO_MODE`-Guard. Diese Endpoints haben keine `require_permission()`-Checks und leaken interne Business-Logik + Patientendaten.

**Fix:**
```python
if DEMO_MODE:
    app.include_router(debug_router, tags=["debug"])
```

### 3. SQL-Injection in Schema-Migration

**Ort:** `backend/app/db.py:75`
```python
conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
```

**Problem:** `table`, `column`, `col_type` sind zwar hardcodiert (nicht user-input), aber das Pattern ist gefährlich wenn es kopiert/erweitert wird. Kein Escaping, kein Parameterized Query (DDL unterstützt keine Binds in SQLite).

**Fix:** Explizites Whitelist-Pattern:
```python
ALLOWED_TABLES = {"ack", "case", ...}
assert table in ALLOWED_TABLES, f"Invalid table: {table}"
```

---

## 🟡 Hoch (vor Go-Live beheben)

### 4. Kein File-Size-Limit bei CSV-Upload

**Ort:** `backend/routers/admin.py:761`

**Problem:** `file.file.read()` liest die gesamte Datei in den Speicher. Keine Größenbeschränkung definiert. Ein Upload von 1 GB+ kann den Server crashen (DoS).

**Fix:**
```python
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
raw = await file.read(MAX_UPLOAD_SIZE + 1)
if len(raw) > MAX_UPLOAD_SIZE:
    raise HTTPException(413, "Datei zu gross (max. 10 MB)")
```

### 5. Keine Input-Validierung auf `case_id` Path-Parameter

**Ort:** `backend/routers/cases.py` — 5 Endpoints

```python
@router.get("/api/cases/{case_id}")
def get_case(case_id: str, ...):
```

**Problem:** `case_id` wird nicht validiert (Länge, Zeichen, Format). Theoretisch kann ein extrem langer String oder Sonderzeichen-String Probleme verursachen (Log-Injection, DB-Query-Performance).

**Fix:**
```python
from pydantic import constr
CaseId = constr(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
```

### 6. IDOR bei Case-Detail nur durch Station-Check geschützt

**Ort:** `backend/routers/cases.py`
```python
if c["station_id"] != ctx.station_id:
    raise HTTPException(status_code=404, detail="Case not found")
```

**Bewertung:** Der Station-Check ist vorhanden und korrekt — ein User kann nur Fälle seiner Station(en) sehen. **Aber:** Es gibt keinen Check, ob der User *überhaupt Zugriff auf diese Station hat*, weil die Browse-Endpunkte den Station-Context nicht immer korrekt setzen.

**Status:** In v5.11/5.12 durch Hierarchie-aware `enforce_station_scope` und `get_user_visible_stations` deutlich verbessert. Der Station-Match in der ACK-Logik ist korrekt.

### 7. CSRF-Token im Cookie ohne `__Host-` Prefix

**Ort:** `backend/middleware/csrf.py`

Das Double-Submit-Cookie-Pattern ist korrekt implementiert. Verbesserungspotential:
- `__Host-` Prefix für Cookie (verhindert Subdomain-Attacks)
- `SameSite=Strict` statt `Lax` wenn möglich

---

## 🟢 Gut gelöst

| Aspekt | Bewertung |
|---|---|
| RBAC-Modell | Solide: 6 Rollen, Permission-based, DB-gespeichert |
| ACK Station-Check | ✓ Case.station_id == ctx.station_id (IDOR geschützt) |
| ACK Condition-Hash | ✓ Verhindert ACK auf veraltete Alerts |
| ACK Day-Versioning | ✓ Reset invalidiert alle Tages-ACKs |
| CSRF Double-Submit | ✓ Korrekt implementiert |
| Rate-Limiting | ✓ 120/min + 3000/h |
| Security Headers (CSP) | ✓ Nonce-basiert |
| Audit-Trail (Admin) | ✓ Alle Admin-Aktionen geloggt |
| SQLAlchemy ORM | ✓ Parametrisierte Queries (kein SQL-Injection-Risiko bei ORM) |
| Break-Glass mit Ablauf | ✓ Zeitbegrenzt + revokeable |
| SECRET_KEY + DEMO_MODE mutual exclusion | ✓ Startup-Check |

---

## ACK-Integrität — Analyse & Empfehlungen

### Aktueller Zustand

Der ACK-Workflow hat **drei gute Schutzmechanismen**:

1. **Station-Binding:** `c["station_id"] != ctx.station_id` → nur eigene Station
2. **Condition-Hash:** Der Hash der Alertbedingung wird gespeichert. Ändern sich die Daten → Alert öffnet sich automatisch wieder (AUTO_REOPEN)
3. **Day-Versioning:** Tages-Reset invalidiert alle ACKs des Tages

### Fehlende Checks (Empfehlungen)

#### A. "Wer darf was quittieren?" — Personenbindung

**Aktuell:** Jeder User mit `ack:write` auf einer Station kann JEDEN Fall dieser Station quittieren.

**Problem:** Ein Pflegender könnte versehentlich ärztliche Alerts quittieren und umgekehrt.

**Empfehlung:**
```yaml
# In rules.yaml pro Regel:
- id: EKG_NOT_REPORTED_24H
  ack_roles: [clinician, system_admin]  # nur Ärzte dürfen quittieren

- id: HONOS_ENTRY_MISSING
  ack_roles: [clinician, shift_lead, manager]  # breiterer Kreis
```

Backend-Check:
```python
if rule.ack_roles and not ctx.roles.intersection(rule.ack_roles):
    raise HTTPException(403, "Keine Berechtigung, diese Meldung zu quittieren")
```

#### B. "Bulk-ACK-Schutz"

**Aktuell:** Ein User kann `case`-Scope ACK verwenden, um ALLE Alerts eines Falls auf einmal zu quittieren.

**Risiko:** Könnte dazu verleiten, Alerts ungelesen zu bestätigen.

**Empfehlungen:**
- Audit-Log analysierbar machen (Bulk-ACKs pro User/Tag flaggen)
- Optional: Case-ACK nur für Shift-Leads erlauben, Kliniker müssen Regel-für-Regel quittieren
- UI-seitig: Bestätigungsdialog bei Case-ACK mit Übersicht aller betroffenen Alerts

#### C. "Verantwortlichkeitsprinzip"

**Empfehlung:** `responsible_person`-Feld im Fall nutzen:
```python
# Optional: Nur fallführende Person oder übergeordnete Rolle
if rule.restrict_to_responsible and c.get("responsible_person") != ctx.user_id:
    if "manager" not in ctx.roles and "shift_lead" not in ctx.roles:
        raise HTTPException(403, "Nur fallführende Person oder Leitung darf quittieren")
```

---

## Testabdeckung — Empfehlungen

### Vorhandene Tests (8 Dateien)

| Test | Abdeckung |
|---|---|
| test_smoke.py | Startup + Basic Endpoints |
| test_rule_engine.py | Regelauswertung |
| test_admin_crud.py | Admin CRUD |
| test_export_csv.py | CSV Export |
| test_rbac.py | Rollen/Permissions |
| test_rbac_enforcement.py | Permission-Checks |
| test_security.py | CSRF, Headers |
| test_ack_lifecycle.py | ACK/Shift/Reset |

### Fehlende Tests (priorisiert)

#### Prio 1 — Sicherheitskritisch

1. **Cross-Station-ACK-Test:** User A (Station X) versucht Fall auf Station Y zu ACKen → muss 404 sein
2. **Hierarchie-Scope-Test:** Manager EPP kann Station A1 sehen, aber nicht Station G0
3. **Browse-Endpoint-Scope:** Clinician sieht nur eigene Station in Browse-Results
4. **File-Upload-Abuse:** Überlange Datei, Binärdatei statt CSV, Sonderzeichen in Feldern
5. **Concurrent ACK+Reset:** ACK und Reset gleichzeitig → Version-Konsistenz prüfen

#### Prio 2 — Business-Logik

6. **Donut-Berechnung:** N Fälle mit bekanntem Alert-Status → erwartete severity_dist
7. **Day-Version-Isolation:** ACK mit Version N, dann Reset (N+1) → ACK nicht mehr gültig
8. **Condition-Hash AUTO_REOPEN:** ACK, dann Daten ändern → Alert wieder offen
9. **Seed-Completeness:** Überprüfen, dass vervollständigte Fälle tatsächlich 0 Alerts haben

#### Prio 3 — Regression

10. **Excel-Import-Konsistenz:** Upload → Klinik/Zentrum-Zuordnung korrekt
11. **Filter-Kaskade:** Klinik-Filter → Zentrum-Optionen korrekt eingeschränkt
12. **Langlieger-Berechnung:** Fall mit 50+ Tagen → korrekt gezählt

---

## Zusammenfassung

| Kategorie | Anzahl | Einschätzung |
|---|---|---|
| 🔴 Kritisch | 3 | Auth-Spoofing ist das Hauptrisiko. Für internen Demo-Betrieb akzeptabel, für Produktion zwingend zu beheben |
| 🟡 Hoch | 4 | Vor Go-Live beheben (File-Size, Input-Validierung, IDOR-Hardening) |
| 🟢 Gut | 11+ | RBAC-Modell, ACK-Lifecycle, CSRF, Rate-Limiting, Audit — alles solide |

**Gesamteinschätzung:** Die Architektur ist für ein internes Monitoring-Dashboard gut aufgebaut. Die Security-Schichten (RBAC, CSRF, CSP, Rate-Limiting) sind vorhanden und korrekt implementiert. Das Hauptrisiko ist die Header-basierte Auth, die für die Demo-Phase bewusst so gewählt wurde und vor einer Produktivsetzung durch SSO/JWT ersetzt werden muss.
