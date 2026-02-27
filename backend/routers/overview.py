"""Station-Übersicht & Analytics Endpoints.

PERFORMANCE-OPTIMIERUNG (v6.2):
  - Response-Cache mit 10s TTL: 50 User bekommen dasselbe Ergebnis
  - ETag-Support: 304 Not Modified wenn Daten unverändert
  - Cache-Key = visible_stations Hash (RBAC-konform)

Datenquellen: NUR DB (befüllt aus Excel beim Startup).
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response
from app.auth import AuthContext, get_auth_context
from app.rbac import require_permission
from app.config import STATION_CENTER
from app.case_logic import get_station_cases
from app.rule_engine import evaluate_alerts, summarize_severity
from app.bi_analytics import compute_station_analytics
from app.response_cache import cache
from app.db import SessionLocal
from app.models import Case

router = APIRouter()


# ── Helper: Alle Stationen aus DB (gecached) ─────────────────────────

def _get_all_stations_from_db() -> tuple[list[str], dict[str, str]]:
    """Liest alle station_ids + Klinik-Zuordnung. Gecached 10s."""
    def _compute():
        with SessionLocal() as db:
            rows = db.query(Case.station_id, Case.clinic).distinct().all()
        station_clinic: dict[str, str] = {}
        for sid, clinic in rows:
            if sid not in station_clinic:
                station_clinic[sid] = clinic or "UNKNOWN"
        station_ids = sorted(station_clinic.keys())
        return (station_ids, station_clinic)

    result, _ = cache.get_or_compute("_stations_db", _compute, ttl=10.0)
    return result


def _get_visible_station_ids(ctx: AuthContext) -> list[str]:
    """RBAC-gefilterte Station-IDs für den aktuellen User."""
    from app.rbac import get_user_visible_stations
    station_ids, _ = _get_all_stations_from_db()
    with SessionLocal() as db:
        visible = get_user_visible_stations(db, ctx.user_id)
    if visible is not None:
        station_ids = [s for s in station_ids if s in visible]
    return station_ids


def _compute_overview_for_stations(station_ids: list[str]) -> list[dict]:
    """Berechnet Übersichtsdaten für gegebene Stationen."""
    _, station_clinic = _get_all_stations_from_db()
    result = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        total = len(cases)
        open_cases = sum(1 for c in cases if c.get("discharge_date") is None)
        station_critical = station_warn = station_ok = 0
        comp_crit = comp_warn_n = med_crit = med_warn_n = 0
        for c in cases:
            alerts = evaluate_alerts(c)
            sev, _, _, _ = summarize_severity(alerts)
            if sev == "CRITICAL": station_critical += 1
            elif sev == "WARN": station_warn += 1
            else: station_ok += 1
            comp_alerts = [a for a in alerts if a.category == "completeness"]
            med_alerts = [a for a in alerts if a.category == "medical"]
            c_sev, _, _, _ = summarize_severity(comp_alerts)
            m_sev, _, _, _ = summarize_severity(med_alerts)
            if c_sev == "CRITICAL": comp_crit += 1
            elif c_sev == "WARN": comp_warn_n += 1
            if m_sev == "CRITICAL": med_crit += 1
            elif m_sev == "WARN": med_warn_n += 1

        def _sev(c, w):
            return "CRITICAL" if c > 0 else "WARN" if w > 0 else "OK"

        result.append(dict(
            station_id=sid,
            center=STATION_CENTER.get(sid, "UNKNOWN"),
            clinic=station_clinic.get(sid, "UNKNOWN"),
            total_cases=total, open_cases=open_cases,
            critical_count=station_critical, warn_count=station_warn, ok_count=station_ok,
            severity="CRITICAL" if station_critical > 0 else "WARN" if station_warn > 0 else "OK",
            completeness_critical=comp_crit, completeness_warn=comp_warn_n,
            completeness_severity=_sev(comp_crit, comp_warn_n),
            medical_critical=med_crit, medical_warn=med_warn_n,
            medical_severity=_sev(med_crit, med_warn_n),
        ))
    return result


def _compute_analytics_for_stations(station_ids: list[str]) -> list[dict]:
    """Berechnet BI-Analytics für gegebene Stationen."""
    _, station_clinic = _get_all_stations_from_db()
    result = []
    for sid in station_ids:
        cases = get_station_cases(sid)
        clinic = station_clinic.get(sid, "UNKNOWN")
        result.append(compute_station_analytics(sid, cases, clinic))
    return result


# ══════════════════════════════════════════════════════════════════════
# /api/overview — Ampelübersicht (CACHED, ETag)
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/overview")
def overview(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
    station_ids = _get_visible_station_ids(ctx)
    if not station_ids:
        return []

    cache_key = f"overview:{','.join(station_ids)}"

    # ETag-Check: 304 wenn Daten unverändert
    if if_none_match and cache.check_etag(cache_key, if_none_match):
        return Response(status_code=304)

    result, etag = cache.get_or_compute(
        cache_key,
        lambda: _compute_overview_for_stations(station_ids),
        ttl=10.0,
    )
    return JSONResponse(
        content=result,
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )


# ══════════════════════════════════════════════════════════════════════
# /api/analytics — BI-Auswertung (CACHED, ETag)
# ══════════════════════════════════════════════════════════════════════

@router.get("/api/analytics")
def analytics(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("dashboard:view")),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
    station_ids = _get_visible_station_ids(ctx)
    if not station_ids:
        return {"stations": []}

    cache_key = f"analytics:{','.join(station_ids)}"

    if if_none_match and cache.check_etag(cache_key, if_none_match):
        return Response(status_code=304)

    result, etag = cache.get_or_compute(
        cache_key,
        lambda: {"stations": _compute_analytics_for_stations(station_ids)},
        ttl=10.0,
    )
    return JSONResponse(
        content=result,
        headers={"ETag": etag, "Cache-Control": "private, max-age=5"},
    )
