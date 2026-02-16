"""Meta-Endpoints: Stationen, Users, Me, Rules."""
from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission
from app.db import SessionLocal
from app.models import Case, User, UserRole, RuleDefinition
from app.case_logic import DUMMY_CASES
from app.rule_engine import load_rule_definitions

router = APIRouter()



@router.get("/api/meta/stations")
def meta_stations(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    # Stationen aus DB laden (alle einzigartigen station_ids)
    with SessionLocal() as db:
        db_stations = db.query(Case.station_id).distinct().all()
        stations = sorted({s[0] for s in db_stations})
    if not stations:
        # Fallback: aus DUMMY_CASES
        stations = sorted({c["station_id"] for c in DUMMY_CASES})
    return {"stations": stations}


@router.get("/api/meta/users")
def meta_users(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    from app.models import User, UserRole

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
    """Return the caller's effective roles/permissions for the current scope.

    Purpose: UI bootstrap (feature gating) without requiring any elevated meta permission.
    Scope resolution:
      - ctx is optional; if omitted, the auth layer resolves to global scope ("*").
      - callers can still send ?ctx=... or X-Scope-Ctx / X-Station-Id.
    """
    return {
        "user_id": ctx.user_id,
        "station_id": ctx.station_id,
        "roles": sorted(ctx.roles),
        "permissions": sorted(ctx.permissions),
        "break_glass": bool(ctx.is_break_glass),
    }


@router.get("/api/meta/rules")
def meta_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("meta:read")),
):
    # read-only for all permitted clients
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
