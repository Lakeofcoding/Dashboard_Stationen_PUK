"""Station-Uebersicht Endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.schemas import StationOverviewItem
from app.config import STATION_CENTER
from app.case_logic import get_station_cases
from app.rule_engine import evaluate_alerts, summarize_severity
from app.ack_store import AckStore
from app.db import SessionLocal
from app.models import Case

ack_store = AckStore()

router = APIRouter()



@router.get("/api/overview", response_model=list[StationOverviewItem])
def station_overview(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Liefert Übersicht über ALLE Stationen mit Ampel-Status."""
    # Alle Stationen aus DB holen
    with SessionLocal() as db:
        db_stations = db.query(Case.station_id).distinct().all()
        station_ids = sorted({s[0] for s in db_stations})
    if not station_ids:
        station_ids = sorted({c["station_id"] for c in DUMMY_CASES})

    result = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        total = len(cases)
        open_cases = sum(1 for c in cases if c.get("discharge_date") is None)

        station_critical = 0
        station_warn = 0
        station_ok = 0

        for c in cases:
            alerts = evaluate_alerts(c)
            sev, _, cc, wc = summarize_severity(alerts)
            if sev == "CRITICAL":
                station_critical += 1
            elif sev == "WARN":
                station_warn += 1
            else:
                station_ok += 1

        if station_critical > 0:
            worst = "CRITICAL"
        elif station_warn > 0:
            worst = "WARN"
        else:
            worst = "OK"

        result.append(StationOverviewItem(
            station_id=sid,
            center=STATION_CENTER.get(sid, "UNKNOWN"),
            total_cases=total,
            open_cases=open_cases,
            critical_count=station_critical,
            warn_count=station_warn,
            ok_count=station_ok,
            severity=worst,
        ))

    return result
