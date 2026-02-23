# PUK Dashboard — Technische Referenzdokumentation

**Version:** 1.0 · Februar 2026
**Umfang:** ca. 10'000 Zeilen Quellcode über 60 Dateien
**Tech-Stack:** FastAPI (Python 3.13) · React 18 / TypeScript · SQLAlchemy · SQLite / PostgreSQL

---

## Inhaltsverzeichnis

1. [Einleitung und Zweck der Anwendung](#1-einleitung-und-zweck-der-anwendung)
2. [Architektur im Überblick](#2-architektur-im-überblick)
3. [Empfohlene Lesereihenfolge](#3-empfohlene-lesereihenfolge)
4. [Verzeichnisstruktur](#4-verzeichnisstruktur)
5. [Der Startvorgang: Wie die Anwendung hochfährt](#5-der-startvorgang-wie-die-anwendung-hochfährt)
   - 5.1 Backend-Einstiegspunkt: `main.py`
   - 5.2 Frontend-Einstiegspunkt: `main.tsx`
   - 5.3 Start-Skripte für Entwicklung und Demo
6. [Konfiguration und Umgebungsvariablen](#6-konfiguration-und-umgebungsvariablen)
   - 6.1 Die zentrale Konfigurationsdatei: `config.py`
   - 6.2 Der Lazy-Proxy: Ein Muster für verzögerte Initialisierung
   - 6.3 Vite-Konfiguration und der Entwicklungs-Proxy
   - 6.4 Vollständige Referenz aller Umgebungsvariablen
7. [Die Datenbank-Schicht](#7-die-datenbank-schicht)
   - 7.1 Engine und Sessions: `db.py`
   - 7.2 Das Datenmodell: `models.py` — 15 ORM-Tabellen im Detail
   - 7.3 Robuste Fehlerbehandlung: `db_safety.py`
   - 7.4 Schema-Migrationen: Der pragmatische Ansatz
8. [Authentifizierung und rollenbasierte Zugriffskontrolle (RBAC)](#8-authentifizierung-und-rollenbasierte-zugriffskontrolle)
   - 8.1 Das AuthContext-Objekt: `auth.py`
   - 8.2 Das RBAC-System: `rbac.py`
   - 8.3 Der Permission-Katalog
   - 8.4 Berechtigungsmatrix
9. [Der Middleware-Stack](#9-der-middleware-stack)
   - 9.1 Warum Pure ASGI statt BaseHTTPMiddleware
   - 9.2 CSRF-Schutz: Das Double-Submit-Cookie-Muster
   - 9.3 Rate-Limiting: Sliding-Window in Memory
   - 9.4 Security-Headers und Content Security Policy
10. [Die Daten-Pipeline: Vom Excel-Sheet zur API-Response](#10-die-daten-pipeline-vom-excel-sheet-zur-api-response)
    - 10.1 Excel-Import: `excel_loader.py`
    - 10.2 Datenanreicherung: `case_logic.py`
    - 10.3 Regelauswertung: `rule_engine.py`
    - 10.4 Klinische Regeldefinitionen: `rules.yaml`
    - 10.5 Der vollständige Datenfluss als Zusammenfassung
11. [Die API-Schicht: Alle Endpunkte im Detail](#11-die-api-schicht-alle-endpunkte-im-detail)
    - 11.1 Fallverwaltung: `cases.py`
    - 11.2 Hierarchische Stationsübersicht: `overview.py`
    - 11.3 Administration: `admin.py`
    - 11.4 Exporte und Reports: `export.py`
    - 11.5 Metadaten: `meta.py`
    - 11.6 Benachrichtigungen, Debug und Health
12. [Der ACK/Shift-Lifecycle: Quittieren und Schieben von Alerts](#12-der-ackshift-lifecycle)
    - 12.1 Der Quittierungs-Speicher: `ack_store.py`
    - 12.2 Tagesversion und Geschäftstag: `day_state.py`
    - 12.3 Drei Wege zur Invalidierung
    - 12.4 Datenfluss einer Quittierung — Schritt für Schritt
13. [Audit-Trail und Sicherheitsmechanismen](#13-audit-trail-und-sicherheitsmechanismen)
    - 13.1 Das Audit-System: `audit.py`
    - 13.2 Der Break-Glass-Mechanismus
14. [Pydantic-Schemas: Validierung an der API-Grenze](#14-pydantic-schemas)
15. [Das Frontend im Detail](#15-das-frontend-im-detail)
    - 15.1 Typdefinitionen: `types.ts`
    - 15.2 Die Hauptkomponente: `App.tsx`
    - 15.3 Polling, Caching und Flicker-Vermeidung
    - 15.4 Die hierarchische Navigation: Klinik → Zentrum → Station
    - 15.5 CaseTable: Die sortierbare Falltabelle
    - 15.6 ParameterBar: Kompakte Statusübersicht
    - 15.7 MonitoringPanel: SVG-Verlaufs-Charts
    - 15.8 MatrixReport: Der Tagesbericht als Heatmap
    - 15.9 AdminPanel: Die Verwaltungsoberfläche
    - 15.10 ReportPanel: Export-Funktionalität
16. [Die Test-Suite](#16-die-test-suite)
    - 16.1 Architektur der Testinfrastruktur: `conftest.py`
    - 16.2 Die acht Test-Module im Überblick
17. [DevOps, Deployment und Betrieb](#17-devops-deployment-und-betrieb)
    - 17.1 Docker-Compose-Architektur
    - 17.2 Qualitäts-Gates: Pre-Commit und Pre-Deploy
18. [Datenfluss-Diagramme: Zwei Szenarien Ende-zu-Ende](#18-datenfluss-diagramme)
19. [Glossar](#19-glossar)

---

## 1. Einleitung und Zweck der Anwendung

Das PUK Dashboard ist ein klinisches Überwachungssystem, das für die Psychiatrische Universitätsklinik Zürich (PUK) entwickelt wurde. Die Anwendung verfolgt ein klares Ziel: Sie überwacht psychiatrische Behandlungsfälle über alle Stationen des Spitalsystems hinweg und erzeugt klinische Warnungen (Alerts), sobald bestimmte Qualitäts- oder Sicherheitskriterien nicht erfüllt sind.

Im klinischen Alltag einer psychiatrischen Klinik entstehen täglich hunderte dokumentationspflichtige Situationen. Ein Patient wird aufgenommen, und innerhalb von drei Tagen muss ein HoNOS-Score erfasst werden. Wird ein Patient mit Clozapin behandelt, müssen regelmässig Neutrophilen-Werte kontrolliert werden. Bei unfreiwilligen Aufenthalten muss innerhalb von 72 Stunden ein Behandlungsplan erstellt werden. All diese Regeln existieren auf Papier, in Richtlinien und in den Köpfen erfahrener Kliniker — das PUK Dashboard macht sie maschinenlesbar und prüft sie automatisch gegen die aktuellen Falldaten.

Die Architektur der Anwendung folgt dem Muster einer klassischen Single-Page-Application mit REST-API: Ein React-Frontend kommuniziert über HTTP mit einem FastAPI-Backend, das die Geschäftslogik kapselt und eine relationale Datenbank als Persistenzschicht nutzt. Obwohl diese Grundarchitektur verbreitet ist, weist das PUK Dashboard einige Besonderheiten auf, die aus dem klinischen Kontext herrühren: ein ausgefeiltes Quittierungs- und Schiebungssystem für Alerts, ein rollenbasiertes Berechtigungssystem mit Notfallzugang (Break-Glass), und eine resiliente Audit-Schicht, die unter keinen Umständen klinische Workflows blockieren darf.

---

## 2. Architektur im Überblick

Das System besteht aus drei Hauptschichten, die strikt voneinander getrennt sind: dem Browser-Frontend, dem HTTP-API-Backend und der Datenbankschicht. Zwischen Frontend und Backend liegt ein Middleware-Stack, der Sicherheitsfunktionen wie CSRF-Schutz, Rate-Limiting und Content-Security-Policy durchsetzt.

```
┌──────────────────────────────────────────────────────────┐
│  Browser (React SPA)                                      │
│  App.tsx → CaseTable / MonitoringPanel / AdminPanel        │
│                          │                                 │
│  HTTP: GET/POST /api/*   │  CSRF-Token im Cookie + Header  │
└──────────────────────────┬────────────────────────────────┘
                           │
┌──────────────────────────┴────────────────────────────────┐
│  Middleware-Stack (ASGI, von aussen nach innen):           │
│  1. SecurityHeaders → CSP-Nonce, HSTS, X-Frame            │
│  2. RateLimit → 120/min, 3000/h pro Client                 │
│  3. CSRF → Double-Submit-Cookie bei POST/PUT/DELETE        │
│                          │                                 │
│  FastAPI Application     │                                 │
│  ├─ routers/cases.py     ← Fallliste, Detail, ACK/Shift   │
│  ├─ routers/overview.py  ← Hierarchie-Übersicht           │
│  ├─ routers/admin.py     ← CRUD User/Rollen/Regeln        │
│  ├─ routers/export.py    ← Reports, CSV-Import/Export      │
│  ├─ routers/meta.py      ← Stationsliste, Shift-Gründe    │
│  ├─ routers/debug.py     ← Rule-Debug (nur mit Permission) │
│  └─ routers/health.py    ← Liveness-Probe                 │
│                          │                                 │
│  Business Logic          │                                 │
│  ├─ app/case_logic.py    ← enrich_case(), Metriken        │
│  ├─ app/rule_engine.py   ← evaluate_alerts()              │
│  ├─ app/ack_store.py     ← Quittierungs-Speicher          │
│  ├─ app/rbac.py          ← Rollen, Permissions, BG        │
│  └─ app/excel_loader.py  ← Daten aus Excel                │
│                          │                                 │
│  Data Layer              │                                 │
│  ├─ app/db.py            ← SQLAlchemy Engine/Session       │
│  ├─ app/models.py        ← ORM-Modelle (15 Tabellen)      │
│  └─ data/app.db          ← SQLite (Dev) / PostgreSQL      │
└──────────────────────────────────────────────────────────┘
```

Das Kernkonzept lässt sich in einem Satz zusammenfassen: Klinische Falldaten fliessen aus einer Datenquelle (derzeit Excel, später KISim) in die Datenbank, werden dort angereichert und gegen klinische Regeln evaluiert. Die daraus resultierenden Alerts werden dem klinischen Personal angezeigt, das sie quittieren oder schieben kann. Ein täglicher Reset-Mechanismus stellt sicher, dass quittierte Alerts am nächsten Tag erneut geprüft werden.

---

## 3. Empfohlene Lesereihenfolge

Wer das Projekt systematisch durcharbeiten möchte, profitiert von einer bestimmten Reihenfolge. Die Anwendung ist so aufgebaut, dass jede Schicht auf der darunterliegenden aufbaut. Es empfiehlt sich daher, von der Infrastruktur (Konfiguration, Datenbank) über die Geschäftslogik (Datenanreicherung, Regeln) bis hin zur Präsentationsschicht (API, Frontend) vorzugehen.

Die folgende Reihenfolge hat sich als besonders effektiv erwiesen:

Als erstes sollte `backend/main.py` gelesen werden — diese Datei zeigt, welche Teile existieren und wie sie beim Start zusammengefügt werden. Sie ist das Inhaltsverzeichnis des Backends. Danach folgt `backend/app/config.py`, um zu verstehen, welche Umgebungsvariablen das Verhalten steuern. Im dritten Schritt sind `backend/app/db.py` und `backend/app/models.py` an der Reihe, denn sie definieren die Datenbankstruktur und damit das Fundament aller Geschäftslogik. Schritt vier umfasst `backend/app/auth.py` und `backend/app/rbac.py` — das Berechtigungssystem, ohne dessen Verständnis kein Endpunkt nachvollziehbar ist.

Ab dem fünften Schritt beginnt die fachliche Logik: `backend/app/excel_loader.py` zeigt, woher die Daten kommen. `backend/app/case_logic.py` erklärt, wie Rohdaten zu klinischen Metriken werden. `backend/app/rule_engine.py` zusammen mit `rules/rules.yaml` zeigt, wie aus Metriken Alerts entstehen. Schritt acht betrifft `backend/routers/cases.py`, die wichtigste API-Datei. Schritt neun umfasst `backend/app/ack_store.py` und `backend/app/day_state.py` für den Quittierungs-Workflow. Im zehnten Schritt folgen die Middleware-Dateien unter `backend/middleware/`. Schritt elf wechselt zum Frontend: `frontend/src/types.ts` und dann `frontend/src/App.tsx`. Zuletzt lohnt sich ein Blick in `backend/tests/conftest.py` und die Test-Module, um zu verstehen, wie das System verifiziert wird.

---

## 4. Verzeichnisstruktur

```
Dashboard_Stationen_PUK/
├── backend/
│   ├── main.py                 ← FastAPI-App, Startup, Router-Registration
│   ├── app/                    ← Kern-Logik (kein HTTP-spezifischer Code)
│   │   ├── config.py           ← Umgebungsvariablen, Konstanten
│   │   ├── db.py               ← SQLAlchemy Engine und Session-Factory
│   │   ├── db_safety.py        ← Globale DB-Fehlerbehandlung
│   │   ├── models.py           ← 15 ORM-Tabellen
│   │   ├── schemas.py          ← Pydantic Request/Response-Modelle
│   │   ├── auth.py             ← AuthContext-Erzeugung
│   │   ├── rbac.py             ← Rollen, Permissions, Break-Glass
│   │   ├── audit.py            ← Security-Event-Logging
│   │   ├── excel_loader.py     ← Excel-Import nach Python-Dicts
│   │   ├── case_logic.py       ← Datenanreicherung und Metrikberechnung
│   │   ├── rule_engine.py      ← Regelauswertung und Alert-Erzeugung
│   │   ├── ack_store.py        ← Quittierungs-Persistenz
│   │   ├── day_state.py        ← Geschäftstag und Tagesversion
│   │   └── frontend_serving.py ← Auslieferung des gebauten Frontends
│   ├── middleware/
│   │   ├── csrf.py             ← CSRF Double-Submit-Cookie
│   │   ├── rate_limit.py       ← In-Memory Rate-Limiter
│   │   └── security_headers.py ← CSP, HSTS, X-Frame-Options
│   ├── routers/                ← HTTP-Endpunkte, thematisch gruppiert
│   │   ├── cases.py            ← /api/cases, /api/ack, Lab/EKG-History
│   │   ├── overview.py         ← /api/overview
│   │   ├── admin.py            ← /api/admin/* (CRUD)
│   │   ├── export.py           ← /api/export/*, CSV-Upload
│   │   ├── meta.py             ← /api/meta/*
│   │   ├── notifications.py    ← /api/notifications/*
│   │   ├── debug.py            ← /api/debug/*
│   │   └── health.py           ← /health
│   ├── tests/                  ← 150 pytest-Tests in 8 Modulen
│   ├── data/                   ← demo_cases.xlsx und SQLite-DB
│   └── alembic/                ← Vorbereitete DB-Migrationen
├── frontend/
│   ├── src/
│   │   ├── main.tsx            ← React-Einstiegspunkt
│   │   ├── App.tsx             ← Hauptkomponente mit State und Routing
│   │   ├── types.ts            ← Gemeinsame TypeScript-Typdefinitionen
│   │   ├── CaseTable.tsx       ← Sortierbare Falltabelle
│   │   ├── ParameterBar.tsx    ← Kompakte Parameter-Statusleiste
│   │   ├── MonitoringPanel.tsx ← SVG-Verlaufs-Charts
│   │   ├── MatrixReport.tsx    ← Tagesbericht als Heatmap-Matrix
│   │   ├── AdminPanel.tsx      ← Admin-Oberfläche
│   │   └── ReportPanel.tsx     ← Export-Panel
│   └── vite.config.ts          ← Build-Konfiguration und API-Proxy
├── rules/
│   └── rules.yaml              ← Klinische Regeldefinitionen
├── scripts/                    ← Pre-Commit-Hooks, Deployment-Checks
├── docker-compose.yml          ← Container-Orchestrierung
└── Makefile                    ← Convenience-Targets
```

---

## 5. Der Startvorgang: Wie die Anwendung hochfährt

### 5.1 Backend-Einstiegspunkt: `main.py`

Die Datei `backend/main.py` ist mit 157 Zeilen vergleichsweise kurz, erfüllt aber eine zentrale Rolle: Sie erstellt die FastAPI-Anwendung, konfiguriert den Middleware-Stack, registriert alle Router und orchestriert den Startup-Vorgang. Sie ist damit das Bindeglied, das alle anderen Module zu einer lauffähigen Anwendung zusammenfügt.

Der Ablauf beim Import und Start lässt sich in fünf Phasen unterteilen.

**Phase 1: Importe und Logging.** Die ersten 43 Zeilen importieren die benötigten Module und konfigurieren das Python-Logging-System. Wenn die Umgebungsvariable `DASHBOARD_DEBUG` auf `"1"` steht, wird das Log-Level auf `DEBUG` gesetzt, was deutlich ausführlichere Ausgaben erzeugt. Im Normalbetrieb (Level `INFO`) werden nur relevante Statusmeldungen ausgegeben.

**Phase 2: Hard Fuse.** Die Zeilen 48–54 enthalten eine Sicherheitsschaltung, die verhindert, dass die Anwendung mit einer gefährlichen Konfiguration startet. Wenn gleichzeitig ein SECRET_KEY gesetzt ist (was auf eine Produktionsumgebung hindeutet) und der Demo-Modus aktiv ist (der keine echte Authentifizierung erzwingt), bricht die Anwendung sofort mit einer Fehlermeldung ab. Diese Kombination wäre gefährlich, weil der Demo-Modus jeden beliebigen User-Header akzeptiert — in einer Produktionsumgebung darf das nicht passieren.

**Phase 3: Middleware-Registration.** In den Zeilen 73–86 werden drei Middleware-Schichten hinzugefügt. Ein wichtiges Detail: Starlettes `add_middleware()` fügt jede neue Middleware als äusserste Schicht hinzu. Die Registrierungsreihenfolge im Code ist also:

```python
app.add_middleware(SecurityHeadersMiddleware)     # Registriert als 3. → wird 1. durchlaufen
app.add_middleware(RateLimitMiddleware, ...)       # Registriert als 2. → wird 2. durchlaufen
app.add_middleware(CSRFMiddleware)                 # Registriert als 1. → wird 3. durchlaufen
```

Das bedeutet: Ein eingehender Request durchläuft zuerst die Security-Headers-Middleware (die einen CSP-Nonce generiert), dann das Rate-Limiting (das prüft, ob der Client sein Kontingent überschritten hat), und zuletzt den CSRF-Schutz (der bei schreibenden Requests das Token validiert). Erst danach erreicht der Request die eigentliche FastAPI-Anwendung mit ihren Routern.

**Phase 4: Router-Registration.** Die Zeilen 92–108 registrieren acht Router-Module. Jeder Router ist eine eigene Python-Datei, die thematisch zusammengehörige Endpunkte bündelt. Die `tags`-Parameter dienen lediglich der Gruppierung in der Swagger-Dokumentation (die nur im Debug-Modus verfügbar ist).

**Phase 5: Startup-Event.** Der mit `@app.on_event("startup")` dekorierte Handler in Zeilen 125–157 wird genau einmal ausgeführt, wenn der ASGI-Server (Uvicorn) die Anwendung hochfährt. Die Reihenfolge der Operationen ist kritisch und darf nicht verändert werden:

1. `init_db()` erstellt alle Datenbanktabellen, die noch nicht existieren, und ergänzt fehlende Spalten in bestehenden Tabellen.
2. `seed_rbac(db)` befüllt den Rollen- und Berechtigungs-Katalog: Rollen wie „viewer", „clinician", „admin" werden in der Datenbank angelegt, ebenso alle definierten Permissions.
3. `seed_rule_definitions(db)` lädt die klinischen Regeln aus `rules/rules.yaml` in die Datenbank, sofern noch keine vorhanden sind.
4. Der Demo-User „demo" wird mit der Admin-Rolle angelegt, falls er noch nicht existiert.
5. `seed_shift_reasons()` erstellt die Standard-Schiebe-Gründe (a: „Noch in Bearbeitung", b: „Warte auf Rückmeldung", c: „Nicht relevant / Ausnahme").
6. `seed_dummy_cases_to_db()` importiert die Demo-Falldaten aus der Excel-Datei in die Datenbank.

### 5.2 Frontend-Einstiegspunkt: `main.tsx`

Die Datei `frontend/src/main.tsx` umfasst nur 21 Zeilen und ist der Standard-Einstiegspunkt einer React-18-Anwendung. Sie tut genau drei Dinge: Sie importiert React und ReactDOM, findet das HTML-Element mit der ID `root` (definiert in `index.html`), und rendert die `App`-Komponente darin. Der `StrictMode`-Wrapper aktiviert in der Entwicklung doppeltes Rendering, was hilft, subtile Bugs wie fehlende Cleanup-Funktionen in `useEffect`-Hooks zu finden.

Bemerkenswert ist, was diese Datei *nicht* enthält: keinen Router (wie React Router), keinen State-Manager (wie Redux), keine Provider-Hierarchie. Die gesamte Navigation und das State-Management sind direkt in `App.tsx` implementiert — eine bewusste Architekturentscheidung für ein Dashboard dieser Grösse, bei dem die Komplexität eines Routing-Frameworks keinen Mehrwert bieten würde.

### 5.3 Start-Skripte für Entwicklung und Demo

Die Datei `_start_backend.bat` (Windows) enthält den Befehl `uvicorn main:app --reload --host 0.0.0.0 --port 8000`. Uvicorn ist ein ASGI-Server, der asynchrone Python-Webanwendungen ausführt. Der Parameter `--reload` sorgt dafür, dass bei jeder Dateiänderung der Server automatisch neu startet — ein Feature, das ausschliesslich in der Entwicklung nützlich ist. Die Notation `main:app` sagt Uvicorn, dass es im Modul `main` die Variable `app` als ASGI-Anwendung verwenden soll.

Die Datei `_start_frontend.bat` führt `npm run dev` aus, was den Vite-Entwicklungsserver auf Port 5173 startet. Vite bietet Hot Module Replacement (HMR): Bei Änderungen an einer React-Komponente wird nur diese Komponente im Browser aktualisiert, ohne die gesamte Seite neu zu laden. Das beschleunigt den Entwicklungszyklus erheblich.

Für den kombinierten Start beider Teile existiert `demo-start.sh` (Linux/Mac) bzw. `demo-start.bat` (Windows). Diese Skripte prüfen Voraussetzungen (Python-Version, Node.js), installieren Abhängigkeiten, starten Backend und Frontend parallel und öffnen den Browser.

---

## 6. Konfiguration und Umgebungsvariablen

### 6.1 Die zentrale Konfigurationsdatei: `config.py`

Die Datei `backend/app/config.py` (62 Zeilen) ist der einzige Ort, an dem Umgebungsvariablen gelesen werden. Alle anderen Module importieren die daraus abgeleiteten Python-Konstanten. Dieses Muster hat den Vorteil, dass Umgebungsvariablen nicht über die gesamte Codebasis verstreut sind und sich leicht testen lassen (durch Überschreiben der Konstanten statt der Umgebungsvariablen).

Die vier wichtigsten Konfigurationswerte sind:

`DEBUG` wird aus `DASHBOARD_DEBUG` abgeleitet und steuert, ob die Swagger-UI zugänglich ist, ob ausführlichere Fehlermeldungen zurückgegeben werden und ob das Log-Level auf `DEBUG` steht. Im Produktionsbetrieb muss dieser Wert `False` sein.

`SECRET_KEY` dient als kryptographisches Geheimnis für den CSRF-Schutz. In der Produktion muss dies ein zufälliger String von mindestens 32 Zeichen sein. Im Demo-Modus (ohne SECRET_KEY) gibt die Anwendung beim Start eine Warnung aus, funktioniert aber trotzdem.

`DEMO_MODE` steuert das Authentifizierungsverhalten. Wenn aktiv, wird jeder im Header genannte Benutzername akzeptiert und automatisch in der Datenbank angelegt. Das ist für Entwicklung und Demo unverzichtbar, in der Produktion aber ein Sicherheitsrisiko — daher die Hard Fuse in `main.py`.

`SECURE_COOKIES` bestimmt, ob Cookies mit dem `Secure`-Flag ausgeliefert werden. Dieses Flag bewirkt, dass der Browser das Cookie nur über HTTPS sendet. In der Entwicklung (HTTP auf localhost) muss dieser Wert `False` sein, in der Produktion (hinter einem HTTPS-Reverse-Proxy) `True`.

### 6.2 Der Lazy-Proxy: Ein Muster für verzögerte Initialisierung

Ein interessantes Implementierungsdetail in `config.py` ist die Klasse `_StationCenterProxy`. Sie löst ein konkretes Problem: Die Zuordnung von Stationen zu Zentren (`STATION_CENTER`) wird aus der Excel-Datei geladen. Beim Import von `config.py` — der sehr früh im Startup passiert — ist der Excel-Loader aber möglicherweise noch nicht bereit (etwa weil die Excel-Datei noch nicht existiert oder Pandas noch nicht importiert ist).

Die Lösung ist ein Dict-Subclass, der sich beim ersten Zugriff selbst befüllt:

```python
class _StationCenterProxy(dict):
    _loaded = False
    def _ensure(self):
        if not self._loaded:
            self.update(_load_station_center())
            self._loaded = True
    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)
```

Von aussen ist `STATION_CENTER` ein ganz normales Dictionary. Der Aufruf `STATION_CENTER["59A1 For-SI"]` liefert `"ZSFT"` — aber erst bei diesem ersten Zugriff werden die Daten tatsächlich aus der Excel-Datei geladen. Alle folgenden Zugriffe lesen direkt aus dem Cache. Dieses Muster wird manchmal als „Lazy Dictionary" oder „Self-Initializing Proxy" bezeichnet.

### 6.3 Vite-Konfiguration und der Entwicklungs-Proxy

Die Datei `frontend/vite.config.ts` (25 Zeilen) konfiguriert den Build-Prozess und den Entwicklungsserver. Ihre wichtigste Funktion ist der Proxy:

```typescript
server: {
    proxy: {
        "/api": "http://localhost:8000",
        "/health": "http://localhost:8000",
    },
},
```

In der Entwicklung laufen Frontend (Port 5173) und Backend (Port 8000) als getrennte Prozesse. Ohne den Proxy würde der Browser bei einem `fetch("/api/cases")` den Vite-Server auf Port 5173 ansprechen, der von `/api/cases` nichts weiss. Der Proxy leitet alle Requests, deren Pfad mit `/api` oder `/health` beginnt, transparent an das Backend weiter. Für den Frontend-Code sieht es so aus, als kämen API-Responses vom selben Ursprung — Cross-Origin-Probleme entstehen gar nicht erst.

In der Produktion existiert dieser Proxy nicht. Stattdessen liefert das Backend selbst das gebaute Frontend aus (via `frontend_serving.py`), sodass API und Frontend unter derselben Domain laufen.

### 6.4 Vollständige Referenz aller Umgebungsvariablen

| Variable | Gelesen in | Standard | Produktionswert |
|----------|-----------|----------|-----------------|
| `SECRET_KEY` | config.py | `""` | **Pflicht:** 64 zufällige Hex-Zeichen |
| `DASHBOARD_ALLOW_DEMO_AUTH` | config.py | `"1"` | `"0"` — Demo-Auth deaktivieren |
| `DASHBOARD_DEBUG` | config.py | `"0"` | `"0"` |
| `DASHBOARD_SECURE_COOKIES` | config.py | `"0"` | `"1"` (HTTPS-Umgebung) |
| `DATABASE_URL` | db.py | `""` → SQLite | `postgresql://user:pass@host/db` |
| `DB_POOL_SIZE` | db.py | `5` | Nach Lastprofil anpassen |
| `DB_MAX_OVERFLOW` | db.py | `10` | Nach Lastprofil anpassen |
| `DASHBOARD_SERVE_FRONTEND` | frontend_serving.py | `"0"` | `"1"` |

---

## 7. Die Datenbank-Schicht

### 7.1 Engine und Sessions: `db.py`

Die Datei `backend/app/db.py` (103 Zeilen) ist die Brücke zwischen der Anwendung und dem Datenbanksystem. Sie verwendet SQLAlchemy, ein Python-ORM (Object-Relational Mapper), das es erlaubt, mit Python-Klassen und -Methoden zu arbeiten statt mit rohem SQL.

Am Anfang der Datei steht die Entscheidung, welche Datenbank verwendet wird. Wenn die Umgebungsvariable `DATABASE_URL` gesetzt ist, wird sie direkt als Verbindungsstring verwendet — typischerweise für PostgreSQL in der Produktion. Ist sie nicht gesetzt, fällt die Anwendung auf SQLite zurück und erstellt eine Datenbankdatei unter `backend/data/app.db`.

Diese Fallback-Logik hat einen wichtigen Grund: Für Entwicklung und Demo soll die Anwendung ohne externe Abhängigkeiten starten können. SQLite ist in Python eingebaut und braucht keinen separaten Datenbankserver. Der Preis dafür sind einige Einschränkungen, die in `_engine_kwargs` adressiert werden:

```python
if _IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
```

SQLite erlaubt standardmässig nur Zugriffe vom Thread, der die Verbindung erstellt hat. Da FastAPI Requests asynchron verarbeitet und möglicherweise zwischen Threads wechselt, muss diese Einschränkung aufgehoben werden. Für PostgreSQL werden stattdessen Pool-Parameter konfiguriert: `pool_size` (wie viele Verbindungen dauerhaft offen gehalten werden) und `max_overflow` (wie viele zusätzliche Verbindungen bei Last erstellt werden dürfen).

Die Funktion `init_db()` wird beim Startup aufgerufen und führt zwei Schritte aus. Zuerst ruft sie `Base.metadata.create_all(bind=engine)` auf, was SQLAlchemy veranlasst, alle in `models.py` definierten Tabellen in der Datenbank zu erstellen — aber nur solche, die noch nicht existieren. Dann folgt `_ensure_schema()`, eine anwendungsspezifische Funktion, die fehlende Spalten zu bestehenden Tabellen hinzufügt:

```python
def safe_add(conn, table, column, col_type="TEXT"):
    if column not in cols(table):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
```

Dieser Ansatz ist ein pragmatischer Kompromiss: Statt eines vollwertigen Migrationssystems (wie Alembic) werden Schema-Erweiterungen inkrementell per `ALTER TABLE ADD COLUMN` durchgeführt. Das reicht für das aktuelle MVP-Stadium, in dem Spalten nur hinzugefügt, aber nie umbenannt oder entfernt werden.

### 7.2 Das Datenmodell: `models.py` — 15 ORM-Tabellen im Detail

Die Datei `backend/app/models.py` (435 Zeilen) definiert alle Datenbanktabellen als SQLAlchemy-ORM-Klassen. Jede Klasse entspricht einer Tabelle, jedes Attribut einer Spalte. Die folgende Beschreibung erläutert jede Tabelle, ihre Rolle im System und ihre Beziehungen zu anderen Tabellen.

**`Case` (Tabellenname: `case_data`)** ist die Kernentität der Anwendung. Ein Case repräsentiert einen psychiatrischen Behandlungsfall — die Aufnahme eines Patienten auf einer bestimmten Station. Die Tabelle hat über 35 Spalten, die sich in mehrere Gruppen einteilen lassen.

Die Identifikationsspalten umfassen `case_id` (der Primärschlüssel, typischerweise eine achtstellige Nummer), `station_id` (die Station, z.B. „59A1 For-SI"), `patient_id` (eine Pseudo-ID ohne direkten Bezug zum realen Patienten), `clinic` (die übergeordnete Klinik: EPP, FPP, APP oder KJPP) und `center` (das Zentrum innerhalb der Klinik, z.B. ZAPE oder ZSFT).

Die zeitlichen Spalten sind `admission_date` (Aufnahmedatum), `discharge_date` (Entlassungsdatum; `None` bei offenen Fällen) und diverse weitere Datumsspalten wie `treatment_plan_date`, `ekg_last_date` oder `clozapin_start_date`. Diese werden als ISO-Strings in der Datenbank gespeichert (z.B. „2026-01-15") und bei der Datenanreicherung in Python-`date`-Objekte umgewandelt.

Die klinischen Score-Spalten umfassen HoNOS (Health of the Nation Outcome Scales, ein psychiatrischer Standardscore von 0 bis 48, jeweils bei Eintritt und Austritt), BSCL (Brief Symptom Checklist, ein Durchschnittswert von 0.0 bis 4.0, ebenfalls bei Eintritt und Austritt) und BFS (drei Datenpunkte zur Basisdokumentation).

Die Monitoring-Spalten betreffen Felder, die für laufende medizinische Überwachungen relevant sind: `clozapin_active` (ob der Patient Clozapin erhält, das eine regelmässige Blutbildkontrolle erfordert), `neutrophils_last_value` (der letzte Neutrophilen-Wert), `ekg_last_reported` (ob das letzte EKG befundet wurde) und ähnliche.

**`Ack` (Tabellenname: `ack`)** speichert Quittierungen und Schiebungen. Jeder Eintrag dokumentiert, dass ein bestimmter Benutzer einen bestimmten Alert zu einem bestimmten Zeitpunkt als gesehen markiert hat. Die Spalten `case_id` und `scope_id` identifizieren den betroffenen Fall und die betroffene Regel. `condition_hash` enthält einen SHA-256-Hash, der die exakte Bedingung zum Zeitpunkt der Quittierung kodiert — ändert sich der zugrundeliegende Wert, wird die Quittierung automatisch invalidiert. `business_date` und `version` ermöglichen die Invalidierung durch Tageswechsel und Reset.

**`User`, `Role`, `Permission`, `UserRole` und `RolePermission`** bilden gemeinsam das RBAC-System (Role-Based Access Control). Die Beziehungen verlaufen über zwei Many-to-Many-Verbindungstabellen: Ein User kann mehrere Rollen haben (via `UserRole`), und jede Rolle kann mehrere Permissions haben (via `RolePermission`). `UserRole` enthält zusätzlich ein `station_id`-Feld, was bedeutet, dass Rollen stationsgebunden zugewiesen werden können. Ein Wert von `"*"` bedeutet „global gültig, über alle Stationen hinweg".

**`BreakGlassSession`** dokumentiert Notfallzugänge. Wenn ein Manager temporär erhöhte Rechte benötigt (etwa um in einer Notfallsituation auf Daten einer fremden Station zuzugreifen), kann eine Break-Glass-Session aktiviert werden. Die Session hat ein Ablaufdatum (standardmässig 4 Stunden), kann aber auch vorzeitig von einem Administrator revoked werden.

**`DayState`** hat einen zusammengesetzten Primärschlüssel aus `station_id` und `business_date`. Sie speichert die aktuelle Tagesversion pro Station. Die Version startet bei 1 und wird bei jedem manuellen Reset inkrementiert. Quittierungen sind nur gültig, wenn ihre Version mit der aktuellen übereinstimmt — ein Reset invalidiert somit alle Quittierungen des laufenden Tages.

**`SecurityEvent`** ist die Audit-Tabelle. Jeder sicherheitsrelevante Vorgang — Quittierungen, Rollenzuweisungen, Break-Glass-Aktivierungen, CSV-Uploads — wird hier mit Zeitstempel, Akteur, IP-Adresse und Details festgehalten.

**`RuleDefinition`** speichert die klinischen Regeln, die beim Startup aus `rules/rules.yaml` geladen werden. Jede Regel hat eine `rule_id`, eine `severity` (CRITICAL oder WARN), ein `metric` (das zu prüfende Feld), einen `operator` (is_true, is_false, >, >=, is_null) und einen erwarteten Wert. Regeln können über das Admin-Interface aktiviert und deaktiviert werden.

**`ShiftReason`** definiert die verfügbaren Gründe, die beim Schieben eines Alerts angegeben werden können. Die Standard-Gründe sind: „Noch in Bearbeitung", „Warte auf Rückmeldung" und „Nicht relevant / Ausnahme".

**`NotificationRule`** ist eine vorbereitete Tabelle für zukünftige E-Mail-Benachrichtigungen. Sie definiert, unter welchen Bedingungen (Station, Severity, Kategorie) eine Benachrichtigung per E-Mail versendet werden soll.

### 7.3 Robuste Fehlerbehandlung: `db_safety.py`

Die Datei `backend/app/db_safety.py` (135 Zeilen) implementiert drei Mechanismen, die das System gegen Datenbankfehler absichern.

Der erste Mechanismus sind globale Exception-Handler, die über `register_db_error_handlers(app)` registriert werden. Ohne diese Handler würde ein `IntegrityError` (z.B. bei einem Duplikat-Eintrag) als generischer HTTP-500-Fehler beim Client ankommen — ohne jede brauchbare Information. Die Handler wandeln spezifische Datenbankfehler in sinnvolle HTTP-Responses um: Ein UNIQUE-Constraint-Fehler wird zu HTTP 409 (Conflict) mit der Nachricht „Datensatz existiert bereits", ein NOT-NULL-Fehler zu „Pflichtfeld fehlt", und ein OperationalError (Datenbank nicht erreichbar) zu HTTP 503 mit einer benutzerfreundlichen Meldung.

Der zweite Mechanismus ist die Funktion `safe_audit()`. Im klinischen Kontext ist es inakzeptabel, dass ein fehlgeschlagener Audit-Eintrag dazu führt, dass eine Quittierung nicht durchgeführt werden kann. Wenn ein Arzt einen kritischen Alert quittiert, muss diese Operation Erfolg haben, auch wenn das Audit-Logging in diesem Moment einen Datenbankfehler hat. `safe_audit()` fängt daher alle Exceptions ab, loggt sie (für spätere Analyse), und lässt die übergeordnete Operation weiterlaufen.

Der dritte Mechanismus ist der Context-Manager `db_context()`, der eine Datenbank-Session bereitstellt und garantiert, dass bei einem Fehler ein Rollback durchgeführt und die Session in jedem Fall geschlossen wird. Ohne diesen Schutz könnte eine nicht geschlossene Session den Connection Pool erschöpfen.

### 7.4 Schema-Migrationen: Der pragmatische Ansatz

Das Projekt enthält einen vollständigen `alembic/`-Ordner mit einer initialen Migration (`20260215_001_initial.py`, 225 Zeilen), die alle Tabellen in einem Schritt erstellt. Alembic ist ein weit verbreitetes Migrationswerkzeug für SQLAlchemy, das Schema-Änderungen versioniert und in beide Richtungen (Upgrade/Downgrade) anwendbar macht.

Im aktuellen MVP-Stadium wird Alembic allerdings nicht aktiv verwendet. Stattdessen erledigt `_ensure_schema()` in `db.py` die inkrementelle Schema-Erweiterung per `ALTER TABLE ADD COLUMN`. Dieser Ansatz funktioniert, solange nur Spalten hinzugefügt werden — für Umbenennungen, Löschungen oder Typ-Änderungen ist er nicht geeignet. Sobald die Anwendung in die Produktion geht und regelmässige Schema-Änderungen anfallen, sollte auf Alembic-Migrationen umgestellt werden.

---

## 8. Authentifizierung und rollenbasierte Zugriffskontrolle

### 8.1 Das AuthContext-Objekt: `auth.py`

Das Authentifizierungs- und Autorisierungssystem des PUK Dashboards ist um ein zentrales Objekt herum aufgebaut: den `AuthContext`. Dieses Objekt wird bei jedem eingehenden Request erstellt und enthält alle Informationen darüber, wer den Request stellt und was diese Person tun darf.

```python
@dataclass(frozen=True)
class AuthContext:
    user_id: str              # z.B. "pflege1"
    station_id: str           # z.B. "59A1 For-SI" oder "*" (global)
    roles: Set[str]           # z.B. {"clinician"}
    permissions: Set[str]     # z.B. {"dashboard:view", "ack:write"}
    is_break_glass: bool      # Notfallzugang aktiv?
```

Die Erzeugung des AuthContext erfolgt in der Funktion `get_auth_context()`, die als FastAPI-Dependency deklariert ist. Das bedeutet: Jeder Endpunkt, der einen `AuthContext` als Parameter deklariert, bekommt automatisch einen frisch erzeugten Kontext injiziert. Der Ablauf der Erzeugung hat fünf Schritte.

Zuerst wird die Identität des Benutzers aus dem HTTP-Header `X-User-Id` gelesen. Im Demo-Modus genügt das — der Header-Wert wird direkt als User-ID verwendet. In einer Produktionsumgebung würde diese Information von einem vorgelagerten SSO-System (Single Sign-On) oder Reverse-Proxy injiziert.

Zweitens wird der Stations-Kontext bestimmt. Dafür gibt es drei Quellen mit absteigender Priorität: der Query-Parameter `?ctx=...`, der Header `X-Scope-Ctx`, und der Legacy-Header `X-Station-Id`. Der Wert `"global"` oder ein fehlender Kontext wird zu `"*"` normalisiert, was „alle Stationen" bedeutet.

Drittens wird `ensure_user_exists()` aufgerufen, das den Benutzer in der Datenbank anlegt, falls er noch nicht existiert (nur im Demo-Modus relevant). Viertens prüft `enforce_station_scope()`, ob der Benutzer mindestens eine Rolle hat, die für die angeforderte Station gilt. Fünftens sammelt `resolve_permissions()` alle Permissions zusammen, die sich aus den Rollen des Benutzers ergeben, unter Berücksichtigung eventuell aktiver Break-Glass-Sessions.

### 8.2 Das RBAC-System: `rbac.py`

Die Datei `backend/app/rbac.py` (328 Zeilen) implementiert das vollständige RBAC-System. Es folgt dem klassischen Muster: Benutzer werden Rollen zugewiesen, Rollen haben Permissions, und Endpunkte erfordern bestimmte Permissions.

Der Permission-Katalog definiert zehn atomare Berechtigungen. `dashboard:view` erlaubt das Lesen von Falldaten und ist die grundlegendste Berechtigung. `ack:write` erlaubt das Quittieren und Schieben von Alerts — eine Berechtigung, die nur klinisches Personal haben sollte. `reset:today` erlaubt das Zurücksetzen der Tagesversion, was alle Quittierungen invalidiert. `admin:read` und `admin:write` kontrollieren den Zugriff auf die Administrationsfunktionen. `audit:read` erlaubt das Lesen des Audit-Logs. `breakglass:activate` erlaubt die Selbst-Aktivierung eines Notfallzugangs, und `breakglass:review` erlaubt es, fremde Break-Glass-Sessions einzusehen und zu widerrufen.

Der Rollen-Katalog definiert sechs vordefinierte Rollen, die beim Startup in die Datenbank geschrieben werden. Die Rolle `viewer` hat nur `dashboard:view` und `meta:read` — genug, um Daten anzusehen, aber nicht um etwas zu verändern. Die Rolle `clinician` fügt `ack:write` hinzu, was klinischem Personal erlaubt, Alerts zu quittieren. Die Rolle `shift_lead` (Schichtleitung) hat zusätzlich `reset:today`. Die Rolle `manager` hat `breakglass:activate`, was einen temporären Notfallzugang ermöglicht. Die Rolle `admin` hat alle Permissions.

Die Funktion `resolve_permissions()` ist das Herzstück der RBAC-Auflösung. Ihr Ablauf lässt sich so zusammenfassen: Sie lädt alle `UserRole`-Einträge des Benutzers, filtert auf Rollen, die entweder global (`station_id="*"`) oder für die angeforderte Station gelten, sammelt die Permissions jeder gültigen Rolle über die `RolePermission`-Tabelle, und bildet die Vereinigung aller Permissions. Zusätzlich prüft sie, ob eine aktive Break-Glass-Session existiert, und fügt in diesem Fall temporäre Admin-Permissions hinzu.

### 8.3 Der Permission-Katalog

| Permission | Bedeutung |
|------------|-----------|
| `dashboard:view` | Fälle und Detaildaten anzeigen |
| `debug:view` | Debug-Endpunkte (Rules/Eval) lesen |
| `meta:read` | Meta-Informationen (Stationsliste) lesen |
| `ack:write` | Quittieren und Schieben |
| `reset:today` | Tages-Reset (Version inkrementieren) |
| `admin:read` | Admin-Lesezugriff (User/Rollen/Audit) |
| `admin:write` | Admin-Schreibzugriff (User/Rollen-Zuweisung) |
| `audit:read` | Security-Audit-Log lesen |
| `breakglass:activate` | Eigenen Notfallzugang aktivieren |
| `breakglass:review` | Notfallzugänge einsehen und widerrufen |

### 8.4 Berechtigungsmatrix

```
Endpunkt                     Permission          viewer  clinician  manager  admin
─────────────────────────────────────────────────────────────────────────────────
GET  /api/cases              dashboard:view        ✓        ✓          ✓       ✓
GET  /api/cases/{id}         dashboard:view        ✓        ✓          ✓       ✓
POST /api/ack                ack:write             ✗        ✓          ✗*      ✓
POST /api/reset_today        reset:today           ✗        ✗          ✗       ✓
GET  /api/admin/users        admin:read            ✗        ✗          ✗       ✓
POST /api/admin/users        admin:write           ✗        ✗          ✗       ✓
GET  /api/admin/audit        audit:read            ✗        ✗          ✗       ✓
POST /api/break_glass        breakglass:activate   ✗        ✗          ✓       ✓

* Manager können via Break-Glass temporär erhöhte Rechte erhalten
```

---

## 9. Der Middleware-Stack

### 9.1 Warum Pure ASGI statt BaseHTTPMiddleware

Alle drei Middleware-Schichten sind als sogenannte „Pure ASGI Middleware" implementiert — sie erben nicht von Starlettes `BaseHTTPMiddleware`, sondern implementieren direkt das ASGI-Interface mit einer `__call__(self, scope, receive, send)`-Methode.

Der Grund für diese Entscheidung ist ein konkreter Bug: Starlettes `BaseHTTPMiddleware` verwendet intern TaskGroups (seit Python 3.11). Wenn ein Request-Handler eine `HTTPException` wirft (z.B. 403 Forbidden), wrappen TaskGroups diese Exception in eine `ExceptionGroup`. FastAPIs Exception-Handler können `ExceptionGroup`-Objekte nicht verarbeiten und wandeln sie in generische HTTP-500-Fehler um. Das Resultat: Statt einer sauberen 403-Response mit Fehlernachricht kommt beim Client ein kryptischer 500-Fehler an.

Die Pure-ASGI-Alternative vermeidet dieses Problem, weil sie keine TaskGroups verwendet und Fehler-Responses direkt als `JSONResponse`-Objekte konstruiert:

```python
async def __call__(self, scope, receive, send):
    if error_condition:
        response = JSONResponse(status_code=403, content={"detail": "Forbidden"})
        await response(scope, receive, send)
        return
    await self.app(scope, receive, send)
```

### 9.2 CSRF-Schutz: Das Double-Submit-Cookie-Muster

Die Datei `middleware/csrf.py` (123 Zeilen) implementiert den CSRF-Schutz (Cross-Site Request Forgery) nach dem Double-Submit-Cookie-Muster. Dieses Muster schützt vor Angriffen, bei denen eine bösartige Website den Browser eines authentifizierten Benutzers dazu bringt, unbeabsichtigte Aktionen auf der Ziel-Anwendung auszuführen.

Das Muster funktioniert in zwei Phasen. In der ersten Phase setzt der Server bei einem GET-Request ein Cookie namens `csrf_token` mit einem kryptographisch zufälligen Wert. Das Frontend liest dieses Cookie und sendet es bei allen nachfolgenden schreibenden Requests (POST, PUT, DELETE) zusätzlich als HTTP-Header `X-CSRF-Token`.

In der zweiten Phase vergleicht die Middleware bei jedem schreibenden Request den Cookie-Wert mit dem Header-Wert. Stimmen sie überein, ist der Request legitim. Fehlt eines der beiden, oder stimmen die Werte nicht überein, wird der Request mit HTTP 403 abgewiesen.

Die Sicherheit dieses Musters basiert auf der Same-Origin-Policy des Browsers: Eine bösartige Website kann zwar bewirken, dass der Browser das CSRF-Cookie automatisch mitsendet, aber sie kann den Wert des Cookies nicht lesen (und ihn daher nicht als Header mitsenden). Nur Code, der auf der gleichen Domain läuft wie die Anwendung, kann das Cookie lesen und den Header setzen.

Ein wichtiges Detail der Implementierung ist die Verwendung von `secrets.compare_digest()` statt des normalen `==`-Operators für den Token-Vergleich. Der Grund: Ein normaler String-Vergleich bricht ab, sobald das erste abweichende Zeichen gefunden wird. Ein Angreifer könnte die Dauer des Vergleichs messen und daraus Rückschlüsse auf die korrekten Zeichen ziehen (Timing-Attacke). `compare_digest()` vergleicht in konstanter Zeit, unabhängig davon, an welcher Stelle die Strings abweichen.

### 9.3 Rate-Limiting: Sliding-Window in Memory

Die Datei `middleware/rate_limit.py` (121 Zeilen) begrenzt die Anzahl der Requests, die ein einzelner Client pro Zeiteinheit senden darf. Die Standard-Limits sind 120 Requests pro Minute und 3000 pro Stunde.

Die Implementierung verwendet einen Sliding-Window-Algorithmus. Für jeden Client werden die Zeitstempel aller Requests gespeichert. Bei einem neuen Request werden zuerst alle Zeitstempel entfernt, die älter als das Fenster sind (60 Sekunden für das Minutenlimit, 3600 Sekunden für das Stundenlimit). Dann wird geprüft, ob die Anzahl der verbleibenden Zeitstempel das Limit überschreitet. Falls ja, wird HTTP 429 (Too Many Requests) mit einem `Retry-After`-Header zurückgegeben.

Die Identifikation des Clients erfolgt zweistufig: Wenn ein `X-User-Id`-Header vorhanden ist, wird der Benutzername als Schlüssel verwendet. Andernfalls wird die IP-Adresse des Clients herangezogen. Diese Unterscheidung ist wichtig, weil in einem Spitalsnetzwerk häufig viele Benutzer hinter derselben IP-Adresse sitzen (NAT). Ohne die User-basierte Identifikation würden sich alle Mitarbeiter einer Abteilung ein gemeinsames Kontingent teilen.

### 9.4 Security-Headers und Content Security Policy

Die Datei `middleware/security_headers.py` (117 Zeilen) setzt auf jede HTTP-Response eine Reihe von Sicherheits-Headern, die den Browser anweisen, bestimmte Schutzmechanismen zu aktivieren.

Der wichtigste dieser Header ist `Content-Security-Policy` (CSP). CSP definiert, welche Ressourcen (Scripts, Styles, Bilder) der Browser laden und ausführen darf. Die Middleware generiert bei jedem Request einen zufälligen Nonce (eine einmalige Zeichenkette), speichert ihn im ASGI-Scope und setzt den CSP-Header auf `script-src 'nonce-...'`. Das bedeutet: Der Browser darf nur Scripts ausführen, die ein `nonce`-Attribut mit exakt diesem Wert haben. Wenn das Frontend in der Produktion ausgeliefert wird, liest `frontend_serving.py` den Nonce aus dem Scope und injiziert ihn in alle `<script>`-Tags des HTML-Dokuments. Ein eingeschleuster Script-Tag (XSS-Angriff) hätte den Nonce nicht und würde vom Browser blockiert.

Weitere gesetzte Header sind `X-Content-Type-Options: nosniff` (verhindert, dass der Browser den MIME-Type einer Response errät statt dem deklarierten zu vertrauen), `X-Frame-Options: DENY` (verhindert, dass die Seite in einem iframe eingebettet wird, was Clickjacking verhindert), und `Strict-Transport-Security` (weist den Browser an, die Seite zukünftig nur über HTTPS aufzurufen).

---

## 10. Die Daten-Pipeline: Vom Excel-Sheet zur API-Response

### 10.1 Excel-Import: `excel_loader.py`

Die Datei `backend/app/excel_loader.py` (437 Zeilen) ist die Datenquelle des aktuellen Systems. In der endgültigen Produktionsversion wird die Datenquelle das klinische Informationssystem KISim sein; bis dahin dient eine Excel-Datei (`data/demo_cases.xlsx`) mit 100 realistischen Testfällen als Grundlage.

Ein bemerkenswertes Designmerkmal ist die graceful degradation: Die gesamte Datei ist so geschrieben, dass sie auch ohne installiertes `pandas` und `openpyxl` funktioniert. Beim Import wird versucht, `pandas` zu laden. Schlägt dies fehl, wird eine globale Variable `_HAS_PANDAS` auf `False` gesetzt, und alle Funktionen geben leere Listen zurück. Das System läuft dann auf Hardcoded-Minidaten weiter — weniger nützlich, aber immerhin lauffähig.

Die Hauptfunktion `get_demo_cases()` liest die Excel-Datei Zeile für Zeile und wandelt jede Zeile in ein Python-Dictionary um. Die grösste Herausforderung dabei ist die Datumskonvertierung: Pandas liest Datumswerte je nach Spaltenformat als `datetime.datetime`, `pandas.Timestamp`, `NaT` (Not a Time, das Pendant zu `NaN` für Datumswerte), oder als Strings. Die Hilfsfunktion `_to_date()` normalisiert all diese Varianten zu einem Python-`date`-Objekt oder `None`:

```python
def _to_date(v):
    if v is None or _is_na(v): return None
    if isinstance(v, date): return v
    if isinstance(v, datetime): return v.date()
    return date.fromisoformat(str(v)[:10])
```

Die Funktion `_is_na()` verdient besondere Beachtung, weil sie Pandas-agnostisch ist: Sie prüft erst auf `None`, dann auf `pd.isna()` (nur wenn Pandas verfügbar ist), und zuletzt auf `math.isnan()` (für nackte float-NaN-Werte).

Neben den Falldaten liefert der Excel-Loader auch Metadaten wie die Zuordnung von Stationen zu Zentren (`get_station_center_map()`) und die Zuordnung von Stationen zu Kliniken.

### 10.2 Datenanreicherung: `case_logic.py`

Die Datei `backend/app/case_logic.py` (573 Zeilen) ist die umfangreichste Business-Logic-Datei und enthält die Transformation von Rohdaten in klinisch auswertbare Fälle. Sie lässt sich in drei funktionale Blöcke unterteilen: Daten laden, Daten anreichern, Daten in die Datenbank schreiben.

Der Lade-Block wird von `_load_raw_cases_from_db(station_id)` angeführt, das alle Fälle einer Station aus der Datenbank liest. Ein wichtiges Detail ist die Datums-Rückkonvertierung: In der Datenbank sind alle Datumswerte als ISO-Strings gespeichert (z.B. „2026-01-15"). Für die Geschäftslogik werden sie in Python-`date`-Objekte umgewandelt, damit Berechnungen wie „Tage seit Aufnahme" möglich sind:

```python
c["admission_date"] = date.fromisoformat(c["admission_date"]) if c["admission_date"] else None
```

Der Anreicherungs-Block wird von `enrich_case(c: dict)` angeführt, der zentralen Funktion der gesamten Datenpipeline. Sie nimmt einen Roh-Fall (ein Dictionary mit ~35 Feldern) und fügt ein `_derived`-Dictionary mit ~20 berechneten booleschen Werten hinzu. Diese berechneten Werte sind die eigentlichen Metriken, gegen die die Regeln evaluiert werden.

Einige Beispiele verdeutlichen die Art der Berechnungen: `honos_entry_missing_over_3d` ist `True`, wenn der HoNOS-Eintrittsscore fehlt und die Aufnahme mehr als 3 Tage zurückliegt. `treatment_plan_missing_involuntary_72h` ist `True`, wenn kein Behandlungsplan existiert, der Aufenthalt unfreiwillig ist und mehr als 3 Tage vergangen sind. `clozapin_neutrophils_low` ist `True`, wenn der Patient Clozapin erhält und der letzte Neutrophilen-Wert unter 2.0 G/l liegt — ein kritischer Zustand, der sofortige Massnahmen erfordert.

Die Funktion `build_parameter_status()` erzeugt eine kompakte Statusübersicht für die Frontend-Leiste. Jeder Parameter bekommt einen Status (ok, warn, critical, na) und einen Detail-Text. Diese Daten werden als Liste in der API-Response mitgeliefert, sodass das Frontend ohne eigene Logik eine farbcodierte Statusleiste rendern kann.

Der Schreib-Block enthält `seed_dummy_cases_to_db()`, das die aus Excel geladenen Fälle in die Datenbank schreibt. Dabei werden zunächst alle als `source="demo"` markierten Fälle gelöscht, dann die neuen eingefügt. Das Feld `source` erlaubt es, Demo-Daten von manuell hochgeladenen oder aus KISim importierten Daten zu unterscheiden.

### 10.3 Regelauswertung: `rule_engine.py`

Die Datei `backend/app/rule_engine.py` (187 Zeilen) bildet das Herz des Alerting-Systems. Sie enthält drei wesentliche Funktionen.

`load_rule_definitions()` lädt die Regeln aus der Datenbank und cached sie für 60 Sekunden. Der Cache verhindert, dass bei jedem Request alle Regeln erneut aus der Datenbank gelesen werden. Wenn der Cache abgelaufen ist, wird er beim nächsten Aufruf automatisch erneuert. Beim allerersten Aufruf — wenn die Datenbank noch keine Regeln enthält — werden die Regeln aus `rules/rules.yaml` gelesen und in die Datenbank geschrieben.

`evaluate_alerts(case: dict)` ist die Hauptfunktion. Sie nimmt einen angereicherten Fall (also das Ergebnis von `enrich_case()`) und evaluiert alle aktiven Regeln dagegen. Für jede Regel, deren Bedingung erfüllt ist, wird ein Alert-Objekt erzeugt. Ein Alert enthält die `rule_id`, die `severity`, die `message` (ein menschenlesbarer Text wie „HoNOS Eintritt fehlt >3 Tage"), die `explanation` (eine ausführlichere Erklärung) und den `condition_hash`.

Der `condition_hash` ist ein SHA-256-Hash über die Regel-ID, die Metrik, den Operator, den erwarteten Wert und — entscheidend — den aktuellen Wert. Dieser Hash macht den Auto-Reopen-Mechanismus möglich: Wenn eine Quittierung mit einem bestimmten Hash gespeichert wird und sich der zugrundeliegende Wert ändert (z.B. weil jemand den HoNOS-Score nachträgt), ändert sich auch der Hash. Die gespeicherte Quittierung stimmt nicht mehr mit dem aktuellen Hash überein und wird automatisch ungültig — der Alert erscheint wieder.

```python
def compute_condition_hash(*, rule_id, metric, operator, expected, actual, discharge_date):
    payload = {"rule_id": rule_id, "actual": actual, ...}
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

`eval_rule(metric_value, operator, value)` evaluiert eine einzelne Bedingung. Die unterstützten Operatoren sind: `is_true` (der Metrik-Wert ist truthy), `is_false` (der Metrik-Wert ist falsy), `>` und `>=` (numerische Vergleiche), und `is_null` (der Wert fehlt). Diese Operatoren decken alle derzeit definierten klinischen Regeln ab.

### 10.4 Klinische Regeldefinitionen: `rules.yaml`

Die Datei `rules/rules.yaml` (242 Zeilen) enthält die klinischen Regeldefinitionen in einem strukturierten YAML-Format. Jede Regel hat folgende Felder:

```yaml
- id: HONOS_ENTRY_MISSING_3D
  category: completeness
  severity: CRITICAL
  metric: honos_entry_missing_over_3d
  operator: is_true
  value: true
  message: "HoNOS Eintritt fehlt (>3 Tage)"
  explanation: "Der HoNOS-Eintrittsscore wurde nicht erfasst, obwohl ..."
```

Die Regeln sind in zwei Kategorien unterteilt: `completeness`-Regeln prüfen, ob Pflichtdokumentationen vorliegen (HoNOS, BSCL, BFS, Behandlungsplan, EKG), und `medical`-Regeln prüfen klinische Werte auf kritische Zustände (Neutrophile unter Clozapin, QTc-Verlängerung, fehlende Blutbildkontrollen). Diese Unterscheidung spiegelt sich im Frontend wider: Completeness-Alerts werden mit „Behoben" quittiert, Medical-Alerts mit „Gesehen".

### 10.5 Der vollständige Datenfluss als Zusammenfassung

```
Excel (demo_cases.xlsx)
    ↓  excel_loader.get_demo_cases()
Python-Dicts (Rohdaten, ~35 Felder pro Fall)
    ↓  case_logic.seed_dummy_cases_to_db()
Datenbank (case_data-Tabelle, Datumswerte als ISO-Strings)
    ↓  case_logic._load_raw_cases_from_db()
Python-Dicts (Strings → date-Objekte konvertiert)
    ↓  case_logic.enrich_case()
Angereicherte Dicts (+_derived-Dict mit ~20 berechneten Booleans)
    ↓  rule_engine.evaluate_alerts()
Liste von Alert-Objekten (rule_id, severity, message, condition_hash)
    ↓  routers/cases.py → JSON-Serialisierung
API-Response an das Frontend
```

---

## 11. Die API-Schicht: Alle Endpunkte im Detail

### 11.1 Fallverwaltung: `cases.py`

Die Datei `backend/routers/cases.py` (453 Zeilen) ist die wichtigste Router-Datei, denn sie stellt die Endpunkte bereit, die das klinische Personal täglich nutzt.

`GET /api/cases` liefert die Fallliste einer Station als Array von `CaseSummary`-Objekten. Für jeden Fall werden die Alerts evaluiert und die Severity zusammengefasst. Die Response enthält pro Fall die IDs, Daten, den Severity-Status und die Parameter-Statusleiste, aber nicht die vollständigen Alert-Details — die kommen erst beim Klick auf einen Fall.

`GET /api/cases/{case_id}` liefert die vollständige Detailansicht eines Falls als `CaseDetail`-Objekt. Dieses enthält alle Felder des Falls, alle evaluierten Alerts (inklusive Nachricht und Erklärung), und den ACK-Status jeder Regel — also ob und wann ein Alert quittiert oder geschoben wurde.

`POST /api/ack` ist der Quittierungs-Endpunkt. Er erwartet einen `AckRequest` im Body mit den Feldern `case_id`, `ack_scope` (immer „rule"), `scope_id` (die Rule-ID), `action` (ACK oder SHIFT) und optional einem `shift_code`. Vor dem Speichern wird geprüft, ob der Fall existiert und ob die Regel aktiv ist. Der `condition_hash` wird zum Zeitpunkt der Quittierung berechnet und mitgespeichert.

`POST /api/reset_today` inkrementiert die Tagesversion einer Station, was alle Quittierungen des laufenden Tages invalidiert. Diese Funktion ist typischerweise der Schichtleitung vorbehalten.

Zusätzlich bietet der Router Endpunkte für klinische Verlaufsdaten: `GET /api/cases/{id}/lab-history` liefert Laborwerte (Neutrophile, Troponin, ALAT/ASAT) als Zeitreihe, und `GET /api/cases/{id}/ekg-history` liefert EKG-Daten (QTc-Werte) als Zeitreihe. Diese Daten werden vom MonitoringPanel im Frontend als SVG-Charts dargestellt.

### 11.2 Hierarchische Stationsübersicht: `overview.py`

Die Datei `backend/routers/overview.py` (79 Zeilen) implementiert einen einzigen Endpunkt, der aber für die Navigation zentral ist: `GET /api/overview` liefert für jede Station im System eine aggregierte Zusammenfassung. Für jede Station werden alle Fälle geladen, die Alerts evaluiert, und die Anzahl der kritischen, warnenden und OK-Fälle gezählt. Die Response enthält pro Station auch die Klinik- und Zentrumszuordnung, was dem Frontend die hierarchische Drill-Down-Navigation ermöglicht.

### 11.3 Administration: `admin.py`

Die Datei `backend/routers/admin.py` ist mit 1085 Zeilen die grösste Datei des Projekts. Sie implementiert vollständige CRUD-Operationen (Create, Read, Update, Delete) für alle administrativen Entitäten: Benutzer, Rollen, Permissions, Regeln, Audit-Einträge, Break-Glass-Sessions und CSV-Datenimport. Jeder Endpunkt ist mit den passenden Permission-Gates geschützt: Lese-Operationen erfordern `admin:read`, Schreib-Operationen `admin:write`, und Audit-Zugriff erfordert `audit:read`.

Besonders hervorzuheben ist der CSV-Upload-Endpunkt (`POST /api/admin/csv/upload`), der es erlaubt, Falldaten per CSV-Datei zu aktualisieren. Die CSV-Datei wird zeilenweise verarbeitet: Existiert ein Fall bereits (gleiches `case_id`), werden seine Felder aktualisiert; andernfalls wird ein neuer Fall angelegt. Jeder Upload wird im Audit-Log protokolliert.

### 11.4 Exporte und Reports: `export.py`

Die Datei `backend/routers/export.py` (297 Zeilen) definiert ein Report-System auf Basis der gleichen Regel-Engine. Jeder Report entspricht einer Regel oder einer Gruppe von Regeln. Die verfügbaren Endpunkte sind: `GET /api/export/reports` (Liste aller Reportdefinitionen), `GET /api/export/data?report_id=...` (Daten eines spezifischen Reports als JSON) und `GET /api/export/csv?report_id=...` (derselbe Report als CSV-Download).

### 11.5 Metadaten: `meta.py`

Die Datei `backend/routers/meta.py` (102 Zeilen) stellt drei Endpunkte bereit, die das Frontend für seine Konfiguration braucht: `GET /api/meta/me` liefert Informationen über den aktuellen Benutzer (Rollen, Permissions, Break-Glass-Status), `GET /api/meta/stations` liefert die Liste aller verfügbaren Stationen, und `GET /api/meta/rules` liefert alle aktiven Regeln.

### 11.6 Benachrichtigungen, Debug und Health

Die Datei `routers/notifications.py` (188 Zeilen) implementiert CRUD für E-Mail-Benachrichtigungsregeln. Diese Funktionalität ist vorbereitet, aber noch nicht aktiv — sie wird relevant, sobald der E-Mail-Versand implementiert wird.

Die Datei `routers/debug.py` (73 Zeilen) bietet zwei Endpunkte für die Entwicklung: `GET /api/debug/rules` listet alle Regeln als JSON, und `GET /api/debug/ack-events` zeigt die letzten Quittierungs-Events. Beide erfordern die Permission `debug:view`.

Die Datei `routers/health.py` (10 Zeilen) besteht aus einem einzigen Endpunkt: `GET /health` gibt `{"status": "ok"}` zurück. Dieser Endpunkt dient als Liveness-Probe für Container-Orchestrierung (Docker, Kubernetes).

---

## 12. Der ACK/Shift-Lifecycle: Quittieren und Schieben von Alerts

### 12.1 Der Quittierungs-Speicher: `ack_store.py`

Die Datei `backend/app/ack_store.py` (257 Zeilen) verwaltet die Persistenz von Quittierungen und Schiebungen. Sie verwendet einen Hybrid-Ansatz aus In-Memory-Cache und Datenbankzugriff.

Die Klasse `AckStore` hält pro Station einen Cache der Quittierungen mit einer TTL (Time-To-Live) von 5 Sekunden. Das bedeutet: Wenn innerhalb von 5 Sekunden mehrere Requests die Quittierungen einer Station abfragen, wird nur beim ersten Request die Datenbank kontaktiert. Alle folgenden Requests lesen aus dem Cache.

Die wichtigsten Methoden sind `save_ack()` (speichert eine neue Quittierung in der Datenbank und invalidiert den Cache), `get_acks_for_cases()` (liest alle Quittierungen für eine Liste von Fällen, mit Cache) und `invalidate_rule_ack_if_mismatch()` (prüft, ob der `condition_hash` einer gespeicherten Quittierung noch mit dem aktuellen Hash übereinstimmt, und löscht die Quittierung bei Abweichung).

### 12.2 Tagesversion und Geschäftstag: `day_state.py`

Die Datei `backend/app/day_state.py` (70 Zeilen) verwaltet den Geschäftstag und die Tagesversion. Der Geschäftstag wird immer in der Zeitzone Europe/Zurich berechnet — ein für ein Schweizer Spital naheliegendes, aber technisch nicht-triviales Detail. Ein Request um 23:30 UTC im Winter (also 00:30 in Zürich) wird dem neuen Geschäftstag zugeordnet.

Die Funktion `get_day_version()` ist race-condition-sicher: Wenn zwei gleichzeitige Requests den ersten Eintrag für einen neuen Tag erstellen wollen, fängt der zweite den UNIQUE-Constraint-Fehler ab und liest stattdessen den von ersten erstellten Eintrag. Diese Absicherung verhindert, dass bei hoher Last am Tageswechsel Fehler auftreten.

Die Funktion `ack_is_valid_today()` prüft, ob eine gespeicherte Quittierung noch gültig ist. Dazu werden zwei Bedingungen geprüft: Der gespeicherte Geschäftstag muss dem heutigen entsprechen, und die gespeicherte Version muss mit der aktuellen übereinstimmen. Ist eine der Bedingungen nicht erfüllt, gilt die Quittierung als abgelaufen.

### 12.3 Drei Wege zur Invalidierung

Eine Quittierung kann auf drei Wegen ungültig werden:

Erstens durch **Tageswechsel**: Jede Nacht um Mitternacht (Europe/Zurich) beginnt ein neuer Geschäftstag. Quittierungen, die auf den gestrigen Tag gespeichert wurden, stimmen mit dem heutigen Datum nicht mehr überein und werden nicht mehr berücksichtigt. Das stellt sicher, dass jeden Morgen alle Alerts frisch bewertet werden.

Zweitens durch einen **manuellen Reset**: Wenn die Schichtleitung den Endpunkt `POST /api/reset_today` aufruft, wird die Tagesversion inkrementiert. Alle Quittierungen des laufenden Tages, die mit der alten Version gespeichert wurden, stimmen mit der neuen Version nicht mehr überein. Dieser Mechanismus erlaubt es, nach einer Datenaktualisierung alle Alerts erneut zu prüfen.

Drittens durch **Datenänderung (Auto-Reopen)**: Wenn sich der zugrundeliegende klinische Wert ändert (z.B. weil ein fehlender HoNOS-Score nachgetragen wurde), ändert sich der `condition_hash`. Die gespeicherte Quittierung hat den alten Hash und wird vom `ack_store` als ungültig erkannt und gelöscht. Dieser Mechanismus ist besonders elegant, weil er keine explizite Invalidierung braucht — die Änderung der Daten genügt.

### 12.4 Datenfluss einer Quittierung — Schritt für Schritt

```
┌──────────────────┐
│  Alert angezeigt  │
│  (unquittiert)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  "Behoben"       │     │  "Nochmal         │
│  (Completeness)  │     │   erinnern"       │
│  → ACK           │     │  → SHIFT + Grund  │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         └────────┬───────────────┘
                  ▼
┌──────────────────────────────────┐
│  In DB gespeichert mit:           │
│  - condition_hash (SHA-256)       │
│  - business_date ("2026-02-23")   │
│  - version (1)                    │
│  - action (ACK oder SHIFT)        │
└────────┬─────────────────────────┘
         │
         │    ┌─────────────────┐
         ├────│ Neuer Tag       │──→ business_date stimmt nicht → ungültig
         │    └─────────────────┘
         │    ┌─────────────────┐
         ├────│ Reset Today     │──→ version stimmt nicht → ungültig
         │    └─────────────────┘
         │    ┌─────────────────┐
         └────│ Daten ändern    │──→ condition_hash stimmt nicht → ungültig
              │ sich            │
              └─────────────────┘
                      │
                      ▼
         ┌──────────────────┐
         │  Alert wird       │
         │  wieder angezeigt │
         └──────────────────┘
```

---

## 13. Audit-Trail und Sicherheitsmechanismen

### 13.1 Das Audit-System: `audit.py`

Die Datei `backend/app/audit.py` (85 Zeilen) implementiert das Security-Event-Logging. Jeder sicherheitsrelevante Vorgang in der Anwendung wird in der Tabelle `security_event` protokolliert, zusammen mit Zeitstempel, Akteur (Benutzer-ID), IP-Adresse, User-Agent und einer maschinenlesbaren Action-Kennung.

Die zentrale Design-Entscheidung ist Resilienz: Die Funktion `log_security_event()` fängt alle eigenen Exceptions ab und propagiert sie niemals an den Aufrufer. Der Grund dafür ist folgender: Wenn ein Arzt einen kritischen Alert quittiert, darf diese Aktion nicht fehlschlagen, nur weil das Audit-Logging in diesem Moment einen Datenbankfehler hat. Ein fehlgeschlagener Audit-Eintrag wird stattdessen ins Python-Logging geschrieben (für spätere Analyse) und die übergeordnete Operation läuft normal weiter.

Die protokollierten Actions umfassen unter anderem: `ACK` und `SHIFT` (Quittierungen), `RESET_TODAY` (Tages-Reset), `BREAK_GLASS_ACTIVATE` und `BREAK_GLASS_REVOKE` (Notfallzugänge), `USER_CREATE` und `ROLE_ASSIGN` (Benutzerverwaltung), `CSV_UPLOAD` und `EXCEL_RELOAD` (Datenimport) sowie `RULE_UPDATE` und `RULE_DELETE` (Regeländerungen).

### 13.2 Der Break-Glass-Mechanismus

Der Break-Glass-Mechanismus ist ein Konzept aus dem klinischen IT-Umfeld, das den Zugriff auf Patientendaten in Notfallsituationen regelt. Im PUK Dashboard funktioniert er folgendermassen:

Ein Benutzer mit der Permission `breakglass:activate` (typischerweise ein Manager) kann über den Endpunkt `POST /api/break_glass` eine Break-Glass-Session starten. Dabei wird eine `BreakGlassSession` in der Datenbank erstellt, die standardmässig nach 4 Stunden abläuft. Solange die Session aktiv ist, erhält der Benutzer temporäre Admin-Permissions, die ihm Zugriff auf Daten und Funktionen gewähren, die ihm normalerweise nicht zustehen.

Jede Break-Glass-Aktivierung wird im Audit-Log protokolliert. Administratoren können über `GET /api/admin/break_glass/sessions` alle aktiven Sessions einsehen und über `POST /api/admin/break_glass/{id}/revoke` eine Session vorzeitig beenden. Auch die Revokation wird im Audit-Log festgehalten.

---

## 14. Pydantic-Schemas: Validierung an der API-Grenze

Die Datei `backend/app/schemas.py` (168 Zeilen) definiert die Pydantic-Modelle, die an der Grenze zwischen HTTP und Business-Logik stehen. Pydantic ist eine Python-Bibliothek für Datenvalidierung, die von FastAPI nativ unterstützt wird.

Request-Modelle definieren, welche Daten ein Client senden darf und muss. Der `AckRequest` beispielsweise erwartet ein `case_id` (Pflicht), ein `ack_scope` (Standard: „rule"), ein `scope_id` (Standard: „*"), eine `action` (Standard: „ACK") und optional einen `shift_code`. Sendet ein Client einen Body, der diesem Schema nicht entspricht — etwa mit einem fehlenden `case_id` — gibt FastAPI automatisch HTTP 422 (Unprocessable Entity) zurück, bevor der Endpunkt-Code überhaupt ausgeführt wird.

Response-Modelle definieren, welche Felder in der API-Response enthalten sind. `CaseSummary` enthält die kompakte Übersicht eines Falls (IDs, Daten, Severity, Parameter-Status). `CaseDetail` erweitert `CaseSummary` um die vollständigen Alert-Details und den ACK-Status jeder Regel. Wenn FastAPI das `response_model` eines Endpunkts kennt, serialisiert es die Rückgabe automatisch gemäss diesem Modell und entfernt Felder, die nicht im Schema definiert sind — ein weiterer Sicherheitsmechanismus gegen unbeabsichtigtes Leaken interner Daten.

Ein spezifisches Detail verdient Erwähnung: Das Feld `bscl` im `CaseDetail` ist als `Optional[float]` definiert, nicht als `int`. Der BSCL-Score ist ein Durchschnittswert im Bereich 0.0 bis 4.0 — die Integer-Annahme in einer früheren Version führte zu Serialisierungsfehlern, wenn die Excel-Daten Dezimalwerte enthielten.

---

## 15. Das Frontend im Detail

### 15.1 Typdefinitionen: `types.ts`

Die Datei `frontend/src/types.ts` (109 Zeilen) definiert die TypeScript-Typen, die im gesamten Frontend verwendet werden. Sie spiegeln die Backend-Schemas 1:1 wider und stellen sicher, dass Frontend und Backend die gleiche Sprache sprechen.

Der Typ `Severity` ist ein String-Union `"OK" | "WARN" | "CRITICAL"` und wird durchgängig für Farbcodierung verwendet. Der Typ `ParameterStatus` beschreibt einen einzelnen Parameter in der Statusleiste (ID, Label, Gruppe, Status, Detail). `CaseSummary` und `CaseDetail` entsprechen exakt den gleichnamigen Backend-Schemas.

### 15.2 Die Hauptkomponente: `App.tsx`

Die Datei `frontend/src/App.tsx` ist mit über 1000 Zeilen die grösste Frontend-Datei. Sie vereint State-Management, API-Kommunikation, Navigation und Layout in einer einzigen Komponente — ein Ansatz, der für ein Dashboard dieser Grösse praktikabel ist, bei weiterem Wachstum aber in Submodule aufgeteilt werden sollte.

Das State-Management folgt einem einfachen Muster: Jede Art von Daten hat einen eigenen `useState`-Hook. Die wichtigsten State-Variablen sind:

`auth` speichert die Authentifizierungsinformationen (User-ID und Station-ID) und wird im LocalStorage persistiert, sodass ein Seitenneustart die Auswahl nicht verliert. `cases` ist das Array der `CaseSummary`-Objekte für die aktuelle Station. `detail` enthält das `CaseDetail` des ausgewählten Falls. `overview` ist das Array der `StationOverviewItem`-Objekte für die Übersichtsseite. `viewMode` bestimmt, welcher Tab aktiv ist (Übersicht, Fallliste, Tagesbericht oder Monitoring). `drillClinic` und `drillCenter` steuern die Drill-Down-Position in der hierarchischen Navigation.

### 15.3 Polling, Caching und Flicker-Vermeidung

Das Frontend nutzt Polling (regelmässiges Abfragen des Servers) statt WebSockets, um die Daten aktuell zu halten. Die Fallliste wird alle 10 Sekunden aktualisiert, die Übersicht alle 15 Sekunden. Diese Intervalle sind ein Kompromiss zwischen Aktualität und Serverlast.

Die Polling-Logik ist in `useEffect`-Hooks implementiert:

```typescript
useEffect(() => {
    const load = async () => {
        const [data, ds] = await Promise.all([
            fetchCases(auth), fetchDayState(auth)
        ]);
        setCases(data);
        setDayState(ds);
    };
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
}, [auth, viewMode]);
```

Das Cleanup-Pattern (`return () => clearInterval(id)`) ist kritisch: Ohne es würde bei jedem Wechsel von `auth` oder `viewMode` ein neuer Intervall gestartet, ohne den alten zu stoppen — nach einigen Tab-Wechseln würden dutzende parallele Intervalle laufen.

Ein subtiler Bug, der im Monitoring-Panel entdeckt und behoben wurde, illustriert die Tücken von React-Dependencies: Die Lab- und EKG-Daten für den aktiven Fall wurden in einem `useEffect` geladen, das vom `activeCase`-Objekt abhing. Weil bei jedem Polling-Zyklus neue Case-Objekte erzeugt werden (sie kommen als JSON vom Server und werden zu neuen JavaScript-Objekten), änderte sich die Objekt-Referenz bei jedem Poll — auch wenn sich die Daten nicht geändert hatten. Das führte dazu, dass die Lab- und EKG-Charts alle 10 Sekunden neu gerendert wurden, was als sichtbarer Flicker wahrgenommen wurde. Die Lösung: Statt vom Objekt hängt der `useEffect` nun von `activeCaseId` (einem primitiven String) ab, der sich nur ändert, wenn tatsächlich ein anderer Fall ausgewählt wird.

### 15.4 Die hierarchische Navigation: Klinik → Zentrum → Station

Die Übersichtsseite implementiert eine dreistufige Drill-Down-Navigation:

Auf der obersten Ebene werden die vier Kliniken (APP – Alterspsychiatrie, EPP – Erwachsenenpsychiatrie, FPP – Forensische Psychiatrie, KJPP – Kinder- und Jugendpsychiatrie) als grosse Karten dargestellt. Jede Karte zeigt aggregierte Zahlen: Gesamtfälle, offene Fälle, Anzahl Zentren und Stationen, und die höchste Severity.

Die Aggregation erfolgt über drei `useMemo`-Hooks. `clinicGroups` gruppiert die `overview`-Daten nach Klinik. `centerGroups` filtert und gruppiert nach Zentrum innerhalb der ausgewählten Klinik. `stationItems` filtert auf die Stationen des ausgewählten Zentrums. Durch die Verwendung von `useMemo` werden diese Berechnungen nur wiederholt, wenn sich die Eingabedaten tatsächlich ändern.

Eine Breadcrumb-Navigation (`Kliniken / EPP / ZAPE`) zeigt die aktuelle Position und erlaubt die Rückkehr zu jeder übergeordneten Ebene.

### 15.5 CaseTable: Die sortierbare Falltabelle

Die Datei `frontend/src/CaseTable.tsx` (331 Zeilen) implementiert eine interaktive Tabelle, in der alle Fälle der aktuellen Station angezeigt werden. Die Spalten umfassen Fall-ID, Patient-ID, Aufnahmedatum, Entlassdatum (oder „Offener Fall"), Severity und Alerts.

Ein Klick auf einen Spaltenheader sortiert die Tabelle nach dieser Spalte — ein erneuter Klick kehrt die Sortierrichtung um. Die Severity-Sortierung folgt einer logischen Reihenfolge (CRITICAL > WARN > OK), nicht der alphabetischen. Zeilen sind farbcodiert: grüner Hintergrund für OK, gelb für WARN, rot für CRITICAL.

### 15.6 ParameterBar: Kompakte Statusübersicht

Die Datei `frontend/src/ParameterBar.tsx` (198 Zeilen) rendert eine horizontale Leiste von farbcodierten Badges, die auf einen Blick zeigt, welche Parameter eines Falls in Ordnung sind und welche nicht. Jeder Badge zeigt den Kurznamen eines Parameters (z.B. „HoNOS ET"), ist farbcodiert (grün, gelb, rot, grau) und hat einen Tooltip mit Details.

### 15.7 MonitoringPanel: SVG-Verlaufs-Charts

Die Datei `frontend/src/MonitoringPanel.tsx` (378 Zeilen) ist die technisch anspruchsvollste Frontend-Komponente. Sie rendert SVG-basierte Liniendiagramme für klinische Verlaufsparameter: Neutrophile (mit Grenzwerten 2.0 und 1.5 G/l), QTc-Verlauf (Grenzwerte 480 und 500 ms), Clozapin-Spiegel, Troponin (erste Wochen nach Therapiebeginn) und Leberwerte (ALAT/ASAT).

Die Daten kommen von den Backend-Endpunkten `/api/cases/{id}/lab-history` und `/api/cases/{id}/ekg-history`. Die Grenzwertlinien sind als farbige Horizontallinien eingezeichnet, Messwerte als Datenpunkte mit Verbindungslinien. Die SVG-Koordinaten werden in der Komponente berechnet — ein externes Charting-Framework wird bewusst vermieden, um die Bundle-Grösse klein zu halten.

### 15.8 MatrixReport: Der Tagesbericht als Heatmap

Die Datei `frontend/src/MatrixReport.tsx` (394 Zeilen) stellt einen Tagesbericht als zweidimensionale Matrix dar: Zeilen sind Fälle, Spalten sind Regeln, und die Zellen sind nach Severity eingefärbt. Auf einen Blick ist erkennbar, welche Fälle in welchen Bereichen Probleme haben. Ein Klick auf eine Zelle navigiert zum entsprechenden Fall.

### 15.9 AdminPanel: Die Verwaltungsoberfläche

Die Datei `frontend/src/AdminPanel.tsx` (750 Zeilen) implementiert eine Tab-basierte Administrationsoberfläche mit Bereichen für Benutzerverwaltung (Benutzer erstellen, deaktivieren, Rollen zuweisen), Rollenverwaltung (Rollen erstellen, Permissions zuweisen), Regelverwaltung (Regeln aktivieren/deaktivieren, Severity ändern), das Audit-Log (durchsuchbar und filterbar) und Break-Glass-Management (aktive Sessions anzeigen und revoken).

### 15.10 ReportPanel: Export-Funktionalität

Die Datei `frontend/src/ReportPanel.tsx` (186 Zeilen) bietet eine Oberfläche zur Auswahl und zum Download von Reports im JSON- oder CSV-Format.

---

## 16. Die Test-Suite

### 16.1 Architektur der Testinfrastruktur: `conftest.py`

Die Datei `backend/tests/conftest.py` (197 Zeilen) definiert die gemeinsamen Fixtures, die von allen Test-Modulen verwendet werden. Die wichtigste Designentscheidung ist die Verwendung von `scope="session"` für die Kern-Fixtures:

```python
@pytest.fixture(scope="session")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

`scope="session"` bedeutet, dass ein einziger TestClient für die gesamte Test-Suite verwendet wird. Das hat zwei Vorteile: Erstens wird der Startup-Overhead (Datenbank initialisieren, Seed-Daten laden) nur einmal bezahlt. Zweitens bleiben Seiteneffekte zwischen Tests erhalten, was realistische Integrationstests ermöglicht, aber auch bedeutet, dass die Reihenfolge der Tests relevant sein kann.

Die `AuthHeaders`-Klasse ist eine Factory, die authentifizierte Header für verschiedene Benutzerrollen erzeugt. Der Aufruf `auth.admin()` liefert Header für den Admin-User, `auth.clinician()` für einen Kliniker, `auth.viewer()` für einen Nur-Leser und `auth.manager()` für einen Manager. Alle Header enthalten automatisch den CSRF-Token, der einmalig beim Start der Test-Suite abgerufen wird.

### 16.2 Die acht Test-Module im Überblick

Die Test-Suite umfasst 150 Tests in acht Modulen. `test_smoke.py` (52 Tests) prüft, dass jeder Endpunkt antwortet und keinen 500-Fehler zurückgibt — die Grundvoraussetzung für eine funktionsfähige Anwendung. `test_admin_crud.py` (29 Tests) testet alle CRUD-Operationen der Admin-API. `test_rbac_enforcement.py` (21 Tests) verifiziert, dass Berechtigungsgrenzen eingehalten werden: Ein Viewer darf nicht quittieren, ein Clinician nicht administrieren. `test_rule_engine.py` (12 Tests) prüft die Alert-Evaluation, Severity-Berechnung und Hash-Stabilität. `test_export_csv.py` (10 Tests) testet Reports und CSV-Downloads. `test_ack_lifecycle.py` (9 Tests) prüft den vollständigen Quittierungs-Workflow inklusive Reset und Auto-Reopen. `test_security.py` (9 Tests) verifiziert den CSRF-Schutz und die Security-Headers. `test_break_glass.py` (6 Tests) testet die Aktivierung und Revokation von Notfallzugängen.

---

## 17. DevOps, Deployment und Betrieb

### 17.1 Docker-Compose-Architektur

Die Datei `docker-compose.yml` (127 Zeilen) definiert drei Services: `backend` (FastAPI-Anwendung mit Uvicorn), `frontend` (Nginx mit dem gebauten React-Bundle) und `db` (PostgreSQL 16 mit einem persistenten Volume). Die Umgebungsvariablen werden über Environment-Sektionen oder eine `.env`-Datei injiziert.

### 17.2 Qualitäts-Gates: Pre-Commit und Pre-Deploy

Das Skript `scripts/pre-commit.sh` (151 Zeilen) wird als Git-Hook vor jedem Commit ausgeführt. Es führt Linting (ruff), Type-Checking (mypy, wo möglich) und die Test-Suite aus. Nur wenn alle Checks bestehen, kann der Commit durchgeführt werden.

Die Skripte `scripts/verify-before-deploy.sh` (253 Zeilen) und `scripts/verify-before-deploy.ps1` (171 Zeilen) sind umfassendere Prüfungen, die vor jedem Deployment laufen sollten. Sie prüfen zusätzlich die Konfiguration (ist SECRET_KEY gesetzt?), die Datenbankverbindung und die Erreichbarkeit der Health-Probe.

---

## 18. Datenfluss-Diagramme: Zwei Szenarien Ende-zu-Ende

### Szenario 1: Laden der Fallliste für Station „59A1 For-SI"

```
Browser                     Frontend (App.tsx)               Backend
───────                     ─────────────────               ───────
Benutzer wählt              fetchCases(auth)
Station im Dropdown               │
                            GET /api/cases?ctx=59A1+For-SI
                                   │
                            ───────┼────────────────────────→
                                   │                    SecurityHeaders: CSP-Nonce setzen
                                   │                    RateLimit: 85/120 → OK
                                   │                    CSRF: GET → überspringen
                                   │                    ↓
                                   │              get_auth_context()
                                   │              → User "pflege1" aus X-User-Id Header
                                   │              → Station "59A1 For-SI" aus ?ctx
                                   │              → resolve_permissions() → {dashboard:view, ack:write}
                                   │                    ↓
                                   │              require_permission("dashboard:view") → ✓
                                   │                    ↓
                                   │              get_station_cases("59A1 For-SI")
                                   │              → _load_raw_cases_from_db("59A1 For-SI")
                                   │              → enrich_case() für jeden Fall
                                   │                    ↓
                                   │              Für jeden Fall:
                                   │                evaluate_alerts(case)
                                   │                summarize_severity(alerts)
                                   │                    ↓
                                   │              Liste von CaseSummary-Objekten
                            ←──────┼─────────────────────────
                                   │
                            setCases(data)
                            → CaseTable rendert Tabelle
                            → ParameterBar zeigt Status pro Fall
```

### Szenario 2: Quittierung eines Alerts

```
Browser                     Frontend                         Backend
───────                     ────────                         ───────
Benutzer klickt             POST /api/ack?ctx=59A1+For-SI
"Behoben" auf               Body: {
HONOS-Alert                   case_id: "30364454",
                              ack_scope: "rule",
                              scope_id: "HONOS_ENTRY_MISSING",
                              action: "ACK"
                            }
                            Header: X-CSRF-Token: abc123
                            Cookie: csrf_token=abc123
                                   │
                            ───────┼────────────────────────→
                                   │                    CSRF: Cookie == Header → ✓
                                   │                    require_permission("ack:write") → ✓
                                   │                    ↓
                                   │              get_single_case("30364454")
                                   │              enrich_case(raw_case)
                                   │              evaluate_alerts(enriched_case)
                                   │              → Alert gefunden, condition_hash = "7a3b..."
                                   │                    ↓
                                   │              ack_store.save_ack(
                                   │                condition_hash = "7a3b...",
                                   │                business_date = "2026-02-23",
                                   │                version = 1
                                   │              )
                                   │                    ↓
                                   │              log_security_event("ACK", target="30364454")
                                   │                    ↓
                                   │              Response: {acked: true}
                            ←──────┼─────────────────────────
                                   │
                            fetchCases() + fetchCaseDetail()
                            → Alert verschwindet aus der Detailansicht
                            → Severity des Falls wird aktualisiert
```

---

## 19. Glossar

| Begriff | Erklärung |
|---------|-----------|
| **ACK** | Quittierung — die Bestätigung, dass ein klinischer Alert gesehen oder behoben wurde |
| **Alert** | Eine klinische Warnung, die von der Rule Engine erzeugt wird, wenn eine Bedingung erfüllt ist |
| **ASGI** | Asynchronous Server Gateway Interface — das Interface-Protokoll für asynchrone Python-Webanwendungen |
| **BFS** | Basisdokumentation Früherfassung Schwangerschaft — drei Datenpunkte zur Patientenbefragung |
| **Break-Glass** | Notfallzugang — ein temporär erhöhter Berechtigungssatz für Ausnahmesituationen |
| **BSCL** | Brief Symptom Checklist — ein Fragebogen zur Selbsteinschätzung psychischer Belastung, Durchschnittswert 0.0–4.0 |
| **Case** | Ein psychiatrischer Behandlungsfall — die Aufnahme eines Patienten auf einer Station |
| **Center** | Ein Zentrum innerhalb einer Klinik, z.B. ZAPE (Zentrum für Allgemeinpsychiatrie und Psychotherapie) |
| **Clinic** | Eine der vier Kliniken der PUK: APP, EPP, FPP, KJPP |
| **Condition Hash** | Ein SHA-256-Hash über Regel und aktuelle Datenwerte; ändert sich der Wert, wird die Quittierung automatisch ungültig |
| **CSRF** | Cross-Site Request Forgery — ein Angriff, bei dem ein Browser unbeabsichtigt Aktionen auf einer authentifizierten Seite ausführt |
| **CSP** | Content Security Policy — ein HTTP-Header, der dem Browser mitteilt, welche Ressourcen er laden darf |
| **Day State** | Der Geschäftstag und seine Version — die Grundlage für die tägliche Invalidierung von Quittierungen |
| **HoNOS** | Health of the Nation Outcome Scales — ein psychiatrischer Standardscore (0–48) zur Erfassung des Gesundheitszustands |
| **KISim** | Klinisches Informationssystem — die zukünftige produktive Datenquelle (derzeit wird eine Excel-Datei verwendet) |
| **Nonce** | Eine einmalig verwendete Zufallszeichenkette, hier im Kontext von CSP zur Autorisierung von Script-Tags |
| **ORM** | Object-Relational Mapper — eine Technik, die Datenbanktabellen als Python-Klassen repräsentiert |
| **RBAC** | Role-Based Access Control — ein Berechtigungssystem, bei dem Rechte über Rollen zugewiesen werden |
| **Reset** | Tages-Reset — das Inkrementieren der Tagesversion, wodurch alle Quittierungen des Tages ungültig werden |
| **Severity** | Schweregrad eines Alerts oder Falls: OK (kein Problem), WARN (Aufmerksamkeit erforderlich), CRITICAL (sofortiger Handlungsbedarf) |
| **SHIFT** | Schiebung — das bewusste Verschieben eines Alerts auf einen späteren Zeitpunkt, mit Angabe eines Grundes |
| **Station** | Eine organisatorische Einheit innerhalb eines Zentrums, z.B. „59A1 For-SI" oder „Station A1" |
