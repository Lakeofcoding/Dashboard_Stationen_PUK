# Dashboard Stationen (PUK) – Intranet-MVP

## Idee / Anliegen

Dieses Projekt ist ein Intranet-orientiertes MVP für ein Stations-Dashboard, das Fälle und regelbasierte Hinweise (Alerts) sichtbar macht und eine **tagesbezogene Arbeitsliste** unterstützt.

Kernziele:

- **Schnelle Übersicht pro Station** (inkl. Priorisierung über Severity).
- **Tagesbezogene Bearbeitung** über *Quittieren* und *Schieben* (a/b/c).
- **Reset-Funktion** für den Geschäftstag, um „heutige Entscheidungen“ vollständig zurückzusetzen.
- **Intranet-/Privacy-Orientierung**: Kein öffentliches Internet als Abhängigkeit; Betrieb über Reverse Proxy/SSO vorgesehen.

## Umsetzung (Überblick)

### Architektur

- **Frontend**: React + TypeScript + Vite (Single Page App)
- **Backend**: FastAPI (Python)
- **Regelwerk**: YAML (`rules/`), vom Backend ausgewertet
- **Persistenz**: SQLite (Audit/Events, Tageszustand/Versionierung)

### Zentrale Domain-Konzepte

- **Case**: Fall mit Basisdaten (Eintritt/Austritt, Scores, BFS etc.)
- **Alert**: Regelverletzung/Statushinweis mit `rule_id`, `severity`, `category`, `message`, `explanation`
- **Ack/Shift**:
  - `ACK`: blendet eine Meldung für *heute* aus
  - `SHIFT` (+ `shift_code` a/b/c): blendet eine Meldung für *heute* aus, aber markiert sie als „geschoben“
- **Business Date**: Geschäftstag in `Europe/Zurich` (nicht UTC).

## Wichtige Änderungen (Feb 2026)

### 1) Reset stellt wieder alle heutigen Fälle/Alerts her (Bugfix)

**Problem:** Nach Reset blieben bereits quittierte/geschobene Meldungen u.U. weiterhin „gültig“, weil die Validitätsprüfung einen zu breiten Fallback auf `acked_at` genutzt hat.

**Fix:** Die Funktion `_ack_is_valid_today(...)` prüft jetzt **strikt**:

- Wenn `business_date` **und** `version` vorhanden sind:
  - gültig nur, wenn `business_date == heute` **und** `version == current_version`
- Fallback auf `acked_at` **nur** für Legacy-Daten (wenn `business_date` oder `version` fehlen)

Damit invalidiert ein Reset (Versionsinkrement) tatsächlich alle heutigen ACK/SHIFT-Entscheidungen.

### 2) Reset mit Warnmeldung (OK/Abbrechen)

Der Reset-Button zeigt jetzt eine klare Warnung und führt den Reset nur nach Bestätigung aus.

### 3) Kontextwechsel robust (Station/User)

Wenn in der Detailansicht auf eine andere Station oder einen anderen User gewechselt wird:

- Detail/Selektion/Fehlerzustand wird zurückgesetzt
- UI bleibt bedienbar („von überall alles machen“)

Zusätzlich wird bei Detail-Fehlern, die auf „nicht gefunden“ hindeuten (404), die Selektion automatisch aufgehoben.

### 4) Layout/Responsive

- Grid nutzt `minmax(0, …)` und `min-width: 0` zur Vermeidung von Overflow.
- Zusätzlich: `overflow-wrap:anywhere` für lange Tokens/IDs.

### 5) Detailansicht übersichtlicher

Die Detailinformationen (Fall/Scores/Vollständigkeit) sind als innere Kacheln dargestellt (statt als reine Liste), ohne bestehende Funktionen zu entfernen.

## Anleitung (lokale Entwicklung)

### Backend starten

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

# Demo-Auth explizit erlauben (nur lokal!)
export DASHBOARD_ALLOW_DEMO_AUTH=1
export DASHBOARD_DEBUG=1

python main.py
```

### Frontend starten

```bash
cd frontend
npm install

# Demo-Auth im Frontend aktivieren (nur lokal!)
# Lege dazu eine Datei "frontend/.env.local" an mit:
# VITE_DEMO_AUTH=1

npm run dev
```

Vite proxy't `/api` automatisch auf `http://127.0.0.1:8000`.

## Betrieb (Intranet, empfohlen)

- Reverse Proxy vor dem Backend (TLS, Auth/SSO, Header/JWT Claims)
- **DEMO ausschalten**:
  - kein `VITE_DEMO_AUTH=1`
  - kein `DASHBOARD_ALLOW_DEMO_AUTH=1`
- Egress blockieren (Server/Pod ohne Internet-Outbound)
- Security Header (CSP, Cache-Control `no-store` etc.)

## Eingesetzte Mittel

- FastAPI, Pydantic
- React Hooks
- SQLite (inkl. Audit-Events)
- YAML-Regeldefinitionen
- Versionsbasierte Reset-Semantik (Business-Date + Version)

## Berechtigungen (Vorbereitung Berechtigungsmatrix)

Aktuell (Prototyp):

- Auth über Header (`X-User-Id`, `X-Station-Id`, `X-Roles`)
- Backend prüft Rollen über `require_role(...)`

Empfohlene nächste Stufe:

- Serverseitige Rollenauflösung (DB/IdP), Frontend nur Anzeige
- Admin-Layer (UI + API), um User->Role->StationScope zu pflegen

---

### Projektstruktur

- `backend/` FastAPI Backend
- `frontend/` React/Vite SPA
- `rules/` YAML Regelwerk



## Security / RBAC (MVE-RBAC)

Dieses Repo enthält nun ein **Minimum Viable Enterprise RBAC** (ohne SSO), das Identität und Autorisierung trennt:

- **Identität**: aktuell via Header `X-User-Id` (SSO/Entra später)
- **Station-Scope**: `X-Station-Id` ist Teil des Request-Kontexts; Rollen können stationsgebunden oder global (`*`) vergeben werden
- **Autorisierung**: Rollen/Permissions sind **DB-basiert**, nicht mehr über `X-Roles`
- **Audit**: sicherheitsrelevante Aktionen und Admin-Aktionen werden in `security_event` append-only protokolliert
- **Break-glass**: Notfallzugang `/api/break_glass/activate` (zeitlich begrenzt, mit Audit); Review/Revoke über `/api/admin/break_glass`

### Systemrollen (Seed)

- `viewer` (read)
- `clinician` (read + ack/shift)
- `shift_lead` (clinician + reset)
- `manager` (read + break-glass self)
- `admin` (voller Admin + Audit)
- `break_glass_admin` (temporär über Break-glass)

### Admin UI

Im Frontend gibt es eine **Admin-Ansicht** (Dropdown „Admin“), sichtbar sobald die Permissions `admin:*` bzw. `audit:read` vorhanden sind.

### Lokales Testen

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Tests:

```bash
pytest -q
```

