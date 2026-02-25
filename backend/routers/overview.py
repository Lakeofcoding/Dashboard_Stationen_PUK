"""Station-Uebersicht Endpoint."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.schemas import StationOverviewItem
from app.config import STATION_CENTER
from app.case_logic import get_station_cases, DUMMY_CASES
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
        # Clinic pro Station (haeufigster Wert)
        station_clinic: dict[str, str] = {}
        for sid in station_ids:
            row = db.query(Case.clinic).filter(Case.station_id == sid, Case.clinic.isnot(None)).first()
            station_clinic[sid] = row[0] if row else "UNKNOWN"
    if not station_ids:
        station_ids = sorted({c["station_id"] for c in DUMMY_CASES})
        for c in DUMMY_CASES:
            station_clinic.setdefault(c["station_id"], c.get("clinic", "UNKNOWN"))

    result = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        total = len(cases)
        open_cases = sum(1 for c in cases if c.get("discharge_date") is None)

        station_critical = 0
        station_warn = 0
        station_ok = 0
        comp_crit = 0
        comp_warn_n = 0
        med_crit = 0
        med_warn_n = 0

        for c in cases:
            alerts = evaluate_alerts(c)
            sev, _, cc, wc = summarize_severity(alerts)
            if sev == "CRITICAL":
                station_critical += 1
            elif sev == "WARN":
                station_warn += 1
            else:
                station_ok += 1
            # Per-category: count cases with category-specific issues
            comp_alerts = [a for a in alerts if a.category == "completeness"]
            med_alerts = [a for a in alerts if a.category == "medical"]
            c_sev, _, _, _ = summarize_severity(comp_alerts)
            m_sev, _, _, _ = summarize_severity(med_alerts)
            if c_sev == "CRITICAL":
                comp_crit += 1
            elif c_sev == "WARN":
                comp_warn_n += 1
            if m_sev == "CRITICAL":
                med_crit += 1
            elif m_sev == "WARN":
                med_warn_n += 1

        if station_critical > 0:
            worst = "CRITICAL"
        elif station_warn > 0:
            worst = "WARN"
        else:
            worst = "OK"

        def _sev(c, w):
            return "CRITICAL" if c > 0 else "WARN" if w > 0 else "OK"

        result.append(StationOverviewItem(
            station_id=sid,
            center=STATION_CENTER.get(sid, "UNKNOWN"),
            clinic=station_clinic.get(sid, "UNKNOWN"),
            total_cases=total,
            open_cases=open_cases,
            critical_count=station_critical,
            warn_count=station_warn,
            ok_count=station_ok,
            severity=worst,
            completeness_critical=comp_crit,
            completeness_warn=comp_warn_n,
            completeness_severity=_sev(comp_crit, comp_warn_n),
            medical_critical=med_crit,
            medical_warn=med_warn_n,
            medical_severity=_sev(med_crit, med_warn_n),
        ))

    return result
