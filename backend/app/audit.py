
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import SecurityEvent


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
