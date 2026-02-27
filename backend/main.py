"""
PUK Dashboard Backend - Main Entry Point

Architektur:
  main.py          -> App-Setup, Middleware, Startup, Router-Registrierung
  app/config.py    -> Environment-Variablen, Konstanten (inkl. dotenv-Loading)
  app/auth.py      -> Authentifizierung (Token + SSO-Header)
  routers/auth_router.py -> Login/Logout/Status-Endpoints
  ...
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI

# Config als erstes importieren (lädt dotenv)
from app.config import DEBUG, DEMO_MODE, SECRET_KEY
from app.db import SessionLocal, init_db
from app.rbac import seed_rbac
from app.rule_engine import seed_rule_definitions
from app.case_logic import seed_shift_reasons, seed_dummy_cases_to_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("puk.main")

# ---------------------------------------------------------------------------
# HARD FUSE: Verhindert Demo-Mode mit echtem Secret Key in Produktion
# ---------------------------------------------------------------------------
if SECRET_KEY and len(SECRET_KEY) >= 32 and DEMO_MODE:
    import sys
    logger.critical(
        "FATAL: SECRET_KEY gesetzt (>=32 Zeichen) + DEMO_MODE aktiv -> Startup verweigert. "
        "Fix: ALLOW_DEMO_AUTH=0 in .env setzen."
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# App erstellen
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PUK Dashboard Backend",
    version="1.0.0",
    debug=DEBUG,
    # Swagger/ReDoc nur im Debug-Modus exponieren
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
)

# ---------------------------------------------------------------------------
# Globale DB-Fehlerbehandlung
# ---------------------------------------------------------------------------
from app.db_safety import register_db_error_handlers
register_db_error_handlers(app)

# ---------------------------------------------------------------------------
# Middleware (äusserste zuerst)
# ---------------------------------------------------------------------------
from middleware.csrf import CSRFMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, requests_per_hour=3000)
app.add_middleware(CSRFMiddleware)

# ---------------------------------------------------------------------------
# Router registrieren
# ---------------------------------------------------------------------------
from routers.health import router as health_router
from routers.auth_router import router as auth_router
from routers.cases import router as cases_router
from routers.meta import router as meta_router
from routers.admin import router as admin_router
from routers.debug import router as debug_router
from routers.overview import router as overview_router
from routers.notifications import router as notifications_router
from routers.export import router as export_router

app.include_router(health_router, tags=["health"])
app.include_router(auth_router, tags=["auth"])
app.include_router(cases_router, tags=["cases"])
app.include_router(meta_router, tags=["meta"])
app.include_router(admin_router, tags=["admin"])
# Debug-Endpoints NUR im Demo-Modus
if DEMO_MODE:
    app.include_router(debug_router, tags=["debug"])
app.include_router(overview_router, tags=["overview"])
app.include_router(notifications_router, tags=["notifications"])
app.include_router(export_router, tags=["export"])

# ---------------------------------------------------------------------------
# CSRF-Exemption für Auth-Endpoints
# ---------------------------------------------------------------------------
# /api/auth/login muss von CSRF-Schutz ausgenommen sein (kein Cookie beim ersten Login)
# wird in CSRFMiddleware über _EXEMPT_PATHS gelöst

# ---------------------------------------------------------------------------
# Production Frontend-Serving
# ---------------------------------------------------------------------------
from app.frontend_serving import setup_production_serving
_serving = setup_production_serving(app)
if _serving:
    logger.info("Production-Frontend-Serving aktiviert")
else:
    logger.info("Kein dist/ gefunden -> Dev-Modus (Vite Dev-Server erwartet)")

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def _startup():
    init_db()
    with SessionLocal() as db:
        seed_rbac(db)
        seed_rule_definitions(db)

        # Demo-User sicherstellen
        from app.models import User, UserRole
        user = db.query(User).filter(User.user_id == "demo").first()
        if not user:
            user = User(
                user_id="demo",
                display_name="Demo User",
                is_active=True,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(user)
            db.flush()

        existing_role = db.query(UserRole).filter(
            UserRole.user_id == "demo", UserRole.role_id == "admin"
        ).first()
        if not existing_role:
            db.add(UserRole(
                user_id="demo", role_id="admin", station_id="*",
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="system",
            ))
        db.commit()

    seed_shift_reasons()
    seed_dummy_cases_to_db()
    logger.info("Backend gestartet (demo_mode=%s, debug=%s)", DEMO_MODE, DEBUG)
