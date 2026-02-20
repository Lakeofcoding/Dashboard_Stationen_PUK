"""
Zentrale DB-Fehlerbehandlung und sichere Audit-Wrapper.

Zweck:
  1) Globaler FastAPI Exception Handler für SQLAlchemy-Fehler → saubere HTTP-Responses
  2) safe_audit() → Audit-Logging, das NIEMALS die Haupt-Operation crasht
  3) db_context() → Context-Manager mit automatischem Rollback bei Fehler

Klinischer Kontext:
  Ein fehlgeschlagener Audit-Eintrag darf NICHT dazu führen, dass ein
  kritischer klinischer Workflow (z.B. ACK einer Warnung) fehlschlägt.
  Umgekehrt muss ein DB-Constraint-Fehler (z.B. duplicate key) als
  verständliche Fehlermeldung beim Benutzer ankommen, nicht als 500.
"""
from __future__ import annotations

import logging
import traceback
from contextlib import contextmanager
from typing import Any, Generator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal

logger = logging.getLogger("puk.db")


# ---------------------------------------------------------------------------
# 1) Globaler Exception Handler
# ---------------------------------------------------------------------------

def register_db_error_handlers(app: FastAPI) -> None:
    """Registriert globale Handler für SQLAlchemy-Exceptions.

    Effekt: Statt generischem 500 bekommen Clients verständliche Fehlermeldungen.
    """

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # UNIQUE constraint → 409 Conflict
        msg = str(exc.orig) if exc.orig else str(exc)
        if "UNIQUE" in msg.upper() or "duplicate" in msg.lower():
            detail = "Datensatz existiert bereits (Duplikat)."
        elif "NOT NULL" in msg.upper():
            detail = "Pflichtfeld fehlt."
        elif "FOREIGN KEY" in msg.upper() or "foreign key" in msg.lower():
            detail = "Referenzierter Datensatz existiert nicht."
        else:
            detail = "Datenbank-Constraint verletzt."
        logger.warning("IntegrityError auf %s: %s", request.url.path, msg)
        return JSONResponse(status_code=409, content={"detail": detail})

    @app.exception_handler(OperationalError)
    async def handle_operational_error(request: Request, exc: OperationalError) -> JSONResponse:
        msg = str(exc.orig) if exc.orig else str(exc)
        logger.error("OperationalError auf %s: %s", request.url.path, msg)
        # Nicht den internen Fehler leaken
        return JSONResponse(
            status_code=503,
            content={"detail": "Datenbank vorübergehend nicht erreichbar. Bitte erneut versuchen."},
        )


# ---------------------------------------------------------------------------
# 2) Sicherer Audit-Wrapper
# ---------------------------------------------------------------------------

def safe_audit(
    db: Session,
    *,
    request: Optional[Request],
    actor_user_id: Optional[str],
    actor_station_id: Optional[str],
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    success: bool = True,
    message: str | None = None,
    details: Any | None = None,
) -> None:
    """Schreibt ein Audit-Event — fängt Fehler ab, ohne die aufrufende Operation zu gefährden.

    Unterschied zu log_security_event():
      - NIEMALS eine Exception nach oben propagieren
      - Fehler werden geloggt, aber nicht geworfen
      - Kein eigener db.commit() (nutzt die Transaktion des Callers)
    """
    from app.audit import log_security_event
    try:
        log_security_event(
            db,
            request=request,
            actor_user_id=actor_user_id,
            actor_station_id=actor_station_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=success,
            message=message,
            details=details,
        )
    except Exception:
        # Audit-Fehler loggen, aber NICHT die Haupt-Operation abbrechen
        logger.error(
            "Audit-Logging fehlgeschlagen für action=%s: %s",
            action, traceback.format_exc(),
        )


# ---------------------------------------------------------------------------
# 3) DB Context Manager mit automatischem Rollback
# ---------------------------------------------------------------------------

@contextmanager
def db_context() -> Generator[Session, None, None]:
    """Context-Manager für DB-Sessions mit garantiertem Rollback bei Fehler.

    Verwendung:
        with db_context() as db:
            db.add(...)
            db.commit()
        # Bei Exception: automatischer Rollback + Session-Close
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
