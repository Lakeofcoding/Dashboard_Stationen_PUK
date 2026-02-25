"""Station-Übersicht & Analytics Endpoints.

Datenquellen: NUR DB (befüllt aus Excel beim Startup).
Kein Fallback auf statische Daten. Leere DB → leere Antwort.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.schemas import StationOverviewItem
from app.config import STATION_CENTER
from app.case_logic import get_station_cases, enrich_case
from app.rule_engine import evaluate_alerts, summarize_severity
from app.bi_analytics import compute_station_analytics
from app.db import SessionLocal
from app.models import Case

router = APIRouter()


# ── Helper: Alle Stationen aus DB lesen ──────────────────────────────

def _get_all_stations_from_db() -> tuple[list[str], dict[str, str]]:
    """Liest alle station_ids + deren Klinik-Zuordnung aus der DB.
    Returns: (station_ids, {station_id: clinic})
    """
    with SessionLocal() as db:
        db_stations = db.query(Case.station_id).distinct().all()
        station_ids = sorted({s[0] for s in db_stations})
        station_clinic: dict[str, str] = {}
        for sid in station_ids:
            row = db.query(Case.clinic).filter(
                Case.station_id == sid, Case.clinic.isnot(None)
            ).first()
            station_clinic[sid] = row[0] if row else "UNKNOWN"
    return station_ids, station_clinic


# ══════════════════════════════════════════════════════════════════════
# /api/overview — Ampelübersicht aller Stationen
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/overview", response_model=list[StationOverviewItem])
def overview(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """Liefert Übersicht über sichtbare Stationen mit Ampel-Status.
    Datenquelle: ausschliesslich DB. Leere DB → leere Liste.
    """
    from app.rbac import get_user_visible_stations

    station_ids, station_clinic = _get_all_stations_from_db()

    # RBAC-Filter
    with SessionLocal() as db:
        visible = get_user_visible_stations(db, ctx.user_id)
    if visible is not None:
        station_ids = [s for s in station_ids if s in visible]

    if not station_ids:
        return []

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

        worst = "CRITICAL" if station_critical > 0 else "WARN" if station_warn > 0 else "OK"

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


# ══════════════════════════════════════════════════════════════════════
# /api/analytics — BI-Auswertung (delegiert an app.bi_analytics)
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/analytics")
def analytics(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
):
    """BI-Auswertung: Completeness-Quoten, Austrittsberichte, ACK-Aktivität.

    Alle Metriken auf EINZELFALL-Ebene. Datenquelle: nur DB.
    Berechnung: app.bi_analytics.compute_station_analytics()
    """
    from app.rbac import get_user_visible_stations

    station_ids, station_clinic = _get_all_stations_from_db()

    # RBAC-Filter
    with SessionLocal() as db:
        visible = get_user_visible_stations(db, ctx.user_id)
    if visible is not None:
        station_ids = [s for s in station_ids if s in visible]

    if not station_ids:
        return {"stations": []}

    stations = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        clinic = station_clinic.get(sid, "UNKNOWN")
        stations.append(compute_station_analytics(sid, cases, clinic))

    return {"stations": stations}
