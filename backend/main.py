"""
PUK Dashboard Backend - Main Entry Point

Architektur:
  main.py          → App-Setup, Middleware, Startup, Router-Registrierung
  app/config.py    → Environment-Variablen, Konstanten
  app/schemas.py   → Pydantic Request/Response-Modelle
  app/models.py    → SQLAlchemy DB-Modelle
  app/db.py        → Datenbank-Session
  app/auth.py      → Authentifizierung (AuthContext)
  app/rbac.py      → Rollen/Rechte (RBAC)
  app/audit.py     → Audit-Logging
  app/ack_store.py → ACK-Persistenz
  app/day_state.py → Tagesversion (Business Date)
  app/rule_engine.py → Regel-Evaluation (mit Cache)
  app/case_logic.py  → Fall-Laden, Anreicherung, Dummy-Daten
  middleware/       → CSRF, Rate-Limiting
  routers/          → API-Endpoints (7 Router-Module)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI

from app.config import DEBUG
from app.db import SessionLocal, init_db
from app.rbac import seed_rbac
from app.rule_engine import seed_rule_definitions
from app.case_logic import seed_shift_reasons, seed_dummy_cases_to_db

# ---------------------------------------------------------------------------
# App erstellen
# ---------------------------------------------------------------------------

app = FastAPI(title="PUK Dashboard Backend", version="1.0.0", debug=DEBUG)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

from middleware.csrf import CSRFMiddleware
from middleware.rate_limit import RateLimitMiddleware

# Reihenfolge: Rate-Limit (äussere Schicht) → CSRF (innere Schicht)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, requests_per_hour=3000)
app.add_middleware(CSRFMiddleware)

# ---------------------------------------------------------------------------
# Router registrieren
# ---------------------------------------------------------------------------

from routers.health import router as health_router
from routers.cases import router as cases_router
from routers.meta import router as meta_router
from routers.admin import router as admin_router
from routers.debug import router as debug_router
from routers.overview import router as overview_router
from routers.notifications import router as notifications_router

app.include_router(health_router, tags=["health"])
app.include_router(cases_router, tags=["cases"])
app.include_router(meta_router, tags=["meta"])
app.include_router(admin_router, tags=["admin"])
app.include_router(debug_router, tags=["debug"])
app.include_router(overview_router, tags=["overview"])
app.include_router(notifications_router, tags=["notifications"])

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _startup():
    init_db()
    with SessionLocal() as db:
        seed_rbac(db)
        seed_rule_definitions(db)

        from app.models import User, UserRole
        user = db.query(User).filter(User.user_id == "demo").first()
        if not user:
            user = User(user_id="demo", full_name="Demo User", is_active=True)
            db.add(user)
            db.flush()

        existing_role = db.query(UserRole).filter(
            UserRole.user_id == "demo", UserRole.role_id == "admin"
        ).first()
        if not existing_role:
            db.add(UserRole(
                user_id="demo", role_id="admin", station_id="*",
                created_at=datetime.now().isoformat(), created_by="system",
            ))
        db.commit()

    seed_shift_reasons()
    seed_dummy_cases_to_db()
    print("Backend gestartet.")
