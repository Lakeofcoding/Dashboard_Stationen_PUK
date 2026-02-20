"""
Audit-Logging (Security Events).

Schreibt Sicherheits-Events in die SecurityEvent-Tabelle.
Resilient: Audit-Fehler werden geloggt, aber NIEMALS nach oben propagiert,
damit die aufrufende Operation nicht durch einen Audit-Fehler crasht.

Klinischer Kontext: Ein fehlgeschlagener Audit-Eintrag darf nicht dazu fuehren,
dass ein kritischer klinischer Workflow (z.B. ACK einer Warnung) fehlschlaegt.
"""


from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import SecurityEvent

logger = logging.getLogger("puk.audit")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_security_event(
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
    """Schreibt ein Security-Event. Faengt eigene Fehler ab (resilient).

    WICHTIG: Diese Funktion darf NIEMALS eine Exception nach oben propagieren.
    Wenn db.commit() fehlschlaegt, wird ein Rollback durchgefuehrt und der
    Fehler geloggt, aber die aufrufende Operation bleibt intakt.
    """
    try:
        ip = None
        ua = None
        if request is not None:
            ip = request.client.host if request.client else None
            ua = request.headers.get("User-Agent")

        ev = SecurityEvent(
            event_id=str(uuid.uuid4()),
            ts=utc_now_iso(),
            actor_user_id=actor_user_id,
            actor_station_id=actor_station_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            success=bool(success),
            message=message,
            ip=ip,
            user_agent=ua,
            details=json.dumps(details, ensure_ascii=False) if details is not None else None,
        )
        db.add(ev)
        db.commit()
    except Exception:
        # Rollback um die Session nicht in einem kaputten Zustand zu lassen
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            "Audit-Logging fehlgeschlagen fuer action=%s target=%s/%s",
            action, target_type, target_id,
            exc_info=True,
        )
