# Refactoring WIP (Work in Progress)

Diese Dateien sind **NICHT AKTIV** und werden **NICHT** vom laufenden System genutzt.

Sie stammen aus einem geplanten Refactoring (Aufteilung von `main.py` in
separate Router/Services/Middleware) das noch nicht abgeschlossen wurde.

**Aktive Entrypoints:**
- `backend/main.py` — einziger aktiver Backend-Code
- `backend/app/` — Models, Auth, RBAC, DB, Audit

**Diese Dateien hier:**
- `main_refactored.py` — geplante Neustrukturierung (nicht verwendet)
- `routers/` — geplante API-Router (nicht eingebunden)
- `services/` — geplante Service-Layer (nicht eingebunden)
- `middleware/` — CSRF/Rate-Limit Middleware (nicht eingebunden)

Bei Bedarf können diese Dateien als Vorlage für das Refactoring dienen.
