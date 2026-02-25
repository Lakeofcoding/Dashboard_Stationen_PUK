"""
Datei: backend/routers/health.py

Zweck:
- Health-Check-Endpoints
- System-Monitoring
- Readiness/Liveness Probes

Router für Health und Monitoring.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.health import get_basic_health, get_detailed_health, is_ready, is_alive

router = APIRouter(prefix="/api", tags=["health"])


def get_db():
    """Dependency für DB-Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/health")
def health_check():
    """
    Einfacher Health-Check.
    
    - Schnell (< 100ms)
    - Für Load Balancer / Liveness Probes
    - Gibt nur "healthy" Status zurück
    """
    return get_basic_health()


@router.get("/health/detailed")
def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detaillierter Health-Check.
    
    - Vollständige System-Informationen
    - Datenbank-Status
    - Ressourcen-Nutzung
    - Für Monitoring / Debugging
    """
    from app.db import engine
    return get_detailed_health(db, engine)


@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness-Check.
    
    - Für Kubernetes Readiness Probes
    - Prüft ob System bereit für Requests
    - Checked Datenbank-Verbindung
    """
    from app.db import engine
    ready = is_ready(db, engine)
    
    if ready:
        return {"status": "ready"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/health/alive")
def liveness_check():
    """
    Liveness-Check.
    
    - Für Kubernetes Liveness Probes
    - Sehr schnell
    - Prüft nur ob Prozess läuft
    """
    alive = is_alive()
    
    if alive:
        return {"status": "alive"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service not alive")
