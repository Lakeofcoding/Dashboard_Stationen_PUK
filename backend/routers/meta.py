"""Meta-Endpoints: Stationen, Users, Me, Rules.

Datenquellen: DB + excel_loader. Keine statischen Fallbacks.
"""
from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission
from app.db import SessionLocal
from app.models import Case, User, UserRole, RuleDefinition
from app.rule_engine import load_rule_definitions

router = APIRouter()


@router.get("/api/meta/stations")
def meta_stations(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    """Alle Stationen aus DB. Leere DB → leere Liste."""
    with SessionLocal() as db:
        db_stations = db.query(Case.station_id).distinct().all()
        stations = sorted({s[0] for s in db_stations})
    return {"stations": stations}


@router.get("/api/meta/users")
def meta_users(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    with SessionLocal() as db:
        users = db.query(User).filter(User.is_active == True).order_by(User.user_id.asc()).all()  # noqa: E712
        roles = db.query(UserRole).all()
        by_user: dict[str, set[str]] = {}
        for r in roles:
            if r.station_id == "*" or r.station_id == ctx.station_id:
                by_user.setdefault(r.user_id, set()).add(r.role_id)

        return {
            "users": [
                {"user_id": u.user_id, "roles": sorted(by_user.get(u.user_id, set()))}
                for u in users
            ]
        }


@router.get("/api/meta/me")
def meta_me(
    ctx: AuthContext = Depends(get_auth_context),
):
    """Rollen, Permissions und Scope des aktuellen Users.

    Scope-Berechnung basiert ausschliesslich auf:
    - excel_loader (Station→Klinik, Station→Zentrum Mapping)
    - DB (alle bekannten station_ids als Fallback)
    """
    from app.config import ROLE_SCOPE

    # Daten aus Excel laden (einzige Quelle für Hierarchie)
    try:
        from app.excel_loader import get_station_klinik_map, get_station_center_map
        station_clinic = get_station_klinik_map() or {}
        station_center = get_station_center_map() or {}
    except Exception:
        station_clinic = {}
        station_center = {}

    # Wenn Excel leer: Station-IDs zumindest aus DB kennen
    if not station_clinic:
        with SessionLocal() as db:
            db_stations = db.query(Case.station_id).distinct().all()
            for s in db_stations:
                station_clinic.setdefault(s[0], "UNKNOWN")

    # Höchster Scope-Level über alle Rollen
    scope_priority = {"global": 0, "klinik": 1, "zentrum": 2, "station": 3}
    best_scope = "station"
    for role in ctx.roles:
        rs = ROLE_SCOPE.get(role, "station")
        if scope_priority.get(rs, 3) < scope_priority.get(best_scope, 3):
            best_scope = rs

    # Scope-Entity bestimmen
    sid = ctx.station_id
    scope_clinic = station_clinic.get(sid)
    scope_center = station_center.get(sid)

    # Sichtbare Stationen
    visible_stations: list[str] = []
    if best_scope == "global":
        visible_stations = sorted(station_clinic.keys())
    elif best_scope == "klinik" and scope_clinic:
        visible_stations = sorted(s for s, k in station_clinic.items() if k == scope_clinic)
    elif best_scope == "zentrum" and scope_center:
        visible_stations = sorted(s for s, z in station_center.items() if z == scope_center)
    elif sid and sid != "*":
        visible_stations = [sid]

    # Letzter Fallback: alle bekannten Stationen (wenn Mapping unvollständig)
    if not visible_stations and station_clinic:
        visible_stations = sorted(station_clinic.keys())

    return {
        "user_id": ctx.user_id,
        "station_id": ctx.station_id,
        "roles": sorted(ctx.roles),
        "permissions": sorted(ctx.permissions),
        "break_glass": bool(ctx.is_break_glass),
        "scope": {
            "level": best_scope,
            "clinic": scope_clinic,
            "center": scope_center,
            "station": sid if sid != "*" else None,
            "visible_stations": visible_stations,
        },
    }


@router.get("/api/meta/rules")
def meta_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    with SessionLocal() as db:
        rows = db.query(RuleDefinition).order_by(RuleDefinition.rule_id.asc()).all()
        return {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "display_name": r.display_name,
                    "message": r.message,
                    "explanation": r.explanation,
                    "category": r.category,
                    "severity": r.severity,
                    "metric": r.metric,
                    "operator": r.operator,
                    "value_json": r.value_json,
                    "enabled": bool(r.enabled),
                    "is_system": bool(r.is_system),
                    "updated_at": r.updated_at,
                    "updated_by": r.updated_by,
                }
                for r in rows
            ]
        }
