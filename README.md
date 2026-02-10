# Dashboard Stationen (Intranet-MVP)

Dieses Projekt ist ein **Intranet-orientiertes MVP** für Stationen-Dashboards.
Wichtiges Ziel: Die Anwendung soll **nicht ins öffentliche Internet** kommunizieren.

## Architektur (Variante A)

- **Frontend:** React + TypeScript + Vite (SPA)
- **Backend:** FastAPI (Python)
- **Betrieb (empfohlen):** Interner Reverse Proxy vor dem Backend (TLS, SSO, CSP)

> Hinweis: Das Framework an sich macht die App nicht "internetfrei". Entscheidend sind
> Netzwerk-Policies (Egress blockieren) und Security-Header (z.B. CSP `connect-src 'self'`).

## Ordnerstruktur

- `frontend/` – React/Vite Anwendung
- `backend/` – FastAPI Backend
- `rules/` – Regeldefinitionen (YAML), die das Backend auswertet

## Lokale Entwicklung (Demo)

### Backend starten

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

# Demo-Auth explizit erlauben (nur lokal!)
set DASHBOARD_ALLOW_DEMO_AUTH=1
set DASHBOARD_DEBUG=1

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

## Produktion (Intranet)

- **DEMO ausschalten:**
  - kein `VITE_DEMO_AUTH=1`
  - kein `DASHBOARD_ALLOW_DEMO_AUTH=1`
- **SSO/Proxy:** Der Reverse Proxy authentifiziert den Benutzer und setzt verlässliche Claims/Headers/JWT.
- **Egress blockieren:** Backend/Server sollten keinen Internet-Outbound haben.
- **Caching verhindern:** Für Patientendaten sind `Cache-Control: no-store` und strikte CSP empfehlenswert.
