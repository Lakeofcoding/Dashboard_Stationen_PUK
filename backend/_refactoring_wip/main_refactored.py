"""
Datei: backend/main_refactored.py

Zweck:
- Haupt-Einstiegspunkt der Anwendung (REFACTORED)
- Router-Registrierung
- Middleware-Konfiguration
- Startup-Events

Dies ist die refactored Version mit aufgeteilten Routern.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.db import init_db, SessionLocal
from app.models import User, UserRole
from app.rbac import seed_rbac
from middleware.csrf import CSRFMiddleware
from middleware.rate_limit import RateLimitMiddleware


# =============================================================================
# Lifespan Context (moderne Alternative zu startup/shutdown events)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan Context Manager.
    
    - Startup: DB initialisieren, Seed-Daten
    - Shutdown: Cleanup (optional)
    """
    # Startup
    print("🚀 Starte PUK Dashboard Backend...")
    
    # Datenbank initialisieren
    init_db()
    
    # Seed-Daten
    with SessionLocal() as db:
        # RBAC seeden
        seed_rbac(db)
        
        # Regeln seeden
        from services.rule_service import RuleService
        rule_service = RuleService()
        rule_service.seed_rules_from_yaml(db)
        
        # Demo-User anlegen (nur wenn DEMO_AUTH aktiv)
        if os.getenv("DASHBOARD_ALLOW_DEMO_AUTH") == "1":
            user = db.query(User).filter(User.user_id == "demo").first()
            if not user:
                from datetime import datetime
                user = User(
                    user_id="demo",
                    display_name="Demo User",
                    is_active=True,
                    created_at=datetime.utcnow().isoformat()
                )
                db.add(user)
                db.flush()
            
            # Admin-Rolle zuweisen
            existing_role = db.query(UserRole).filter(
                UserRole.user_id == "demo",
                UserRole.role_id == "admin"
            ).first()
            
            if not existing_role:
                from datetime import datetime
                role = UserRole(
                    user_id="demo",
                    role_id="admin",
                    station_id="*",
                    created_at=datetime.utcnow().isoformat(),
                    created_by="system"
                )
                db.add(role)
                print("✓ Demo-User 'demo' mit Admin-Rechten erstellt")
        
        db.commit()
    
    print("✓ Datenbank initialisiert")
    print("✓ Backend bereit!")
    
    yield
    
    # Shutdown (optional)
    print("👋 Shutdown...")


# =============================================================================
# App Initialisierung
# =============================================================================

app = FastAPI(
    title="PUK Dashboard API",
    version="1.0.0",
    description="Klinisches Qualitäts-Dashboard für psychiatrische Stationen",
    lifespan=lifespan,
    debug=os.getenv("DASHBOARD_DEBUG") == "1",
)


# =============================================================================
# Middleware (Reihenfolge wichtig!)
# =============================================================================

# 1. CORS (muss als erstes!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Rate Limiting (nur in Produktion)
if os.getenv("ENABLE_RATE_LIMITING") == "1":
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
    )

# 4. CSRF Protection (nur in Produktion)
if os.getenv("ENABLE_CSRF_PROTECTION") == "1":
    app.add_middleware(
        CSRFMiddleware,
        secret_key=os.getenv("SECRET_KEY"),
    )


# =============================================================================
# Router Registration
# =============================================================================

from routers import health, auth, cases, admin

# Health & Monitoring (keine Auth erforderlich)
app.include_router(health.router)

# Authentication & Session
app.include_router(auth.router)

# Case Management (erfordert Auth)
app.include_router(cases.router)

# Administration (erfordert Admin-Rechte)
app.include_router(admin.router)


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/")
def root():
    """
    Root-Endpoint.
    
    - Gibt API-Info zurück
    - Redirect zu /docs für API-Dokumentation
    """
    return {
        "name": "PUK Dashboard API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
    }


# =============================================================================
# Exception Handlers
# =============================================================================

from fastapi import Request
from fastapi.responses import JSONResponse
from app.logging_config import get_logger

logger = get_logger(__name__)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Globaler Exception-Handler.
    
    - Loggt alle unbehandelten Exceptions
    - Gibt generische Fehlermeldung zurück (keine Details in Produktion)
    """
    logger.error(
        f"Unhandled exception",
        exc_info=exc,
        extra={
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    # In Produktion: Keine Details
    if os.getenv("DASHBOARD_DEBUG") != "1":
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_id": "Contact support with this ID",  # TODO: Generate UUID
            }
        )
    
    # In Debug: Details zeigen
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
        }
    )


# =============================================================================
# Startup Message
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main_refactored:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DASHBOARD_DEBUG") == "1",
        workers=1 if os.getenv("DASHBOARD_DEBUG") == "1" else 2,
    )
