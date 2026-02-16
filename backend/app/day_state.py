"""
Tagesversion (DayState) Management.
Race-Condition-sicher fuer gleichzeitige Station-Zugriffe.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from app.db import SessionLocal
from app.models import DayState


def today_local() -> date:
    """Business date (Europe/Zurich)."""
    return datetime.now(ZoneInfo("Europe/Zurich")).date()


def get_day_version(*, station_id: str) -> int:
    """Liefert die aktuelle Tagesversion fuer eine Station.

    Race-Condition-sicher: bei gleichzeitigem INSERT faengt der zweite
    den UNIQUE-Constraint ab und liest stattdessen.
    """
    bdate = today_local().isoformat()
    with SessionLocal() as db:
        row = db.get(DayState, (station_id, bdate))
        if row is not None:
            return int(row.version)
        try:
            row = DayState(station_id=station_id, business_date=bdate, version=1)
            db.add(row)
            db.commit()
            db.refresh(row)
            return int(row.version)
        except Exception:
            db.rollback()
            row = db.get(DayState, (station_id, bdate))
            if row is not None:
                return int(row.version)
            return 1


def _parse_iso_dt(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def ack_is_valid_today(
    *, acked_at_iso: str, business_date: str | None,
    version: int | None, current_version: int,
) -> bool:
    """Prueft ob eine Quittierung/Shift heute gueltig ist."""
    today_str = today_local().isoformat()

    if business_date is not None:
        if business_date != today_str:
            return False
        if version is not None and version != current_version:
            return False
        return True

    # Legacy: nur Zeitstempel-basiert
    try:
        acked_dt = _parse_iso_dt(acked_at_iso)
        if acked_dt.tzinfo is None:
            acked_dt = acked_dt.replace(tzinfo=timezone.utc)
        acked_date = acked_dt.astimezone(ZoneInfo("Europe/Zurich")).date()
        return acked_date == today_local()
    except Exception:
        return False
