"""
Datei: backend/app/rbac.py

Zweck:
- Backend-/Serverlogik dieser Anwendung.
- Kommentare wurden ergänzt, um Einstieg und Wartung zu erleichtern.

Hinweis:
- Sicherheitsrelevante Checks (RBAC/Permissions) werden serverseitig erzwungen.
"""


from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Set

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.audit import log_security_event, utc_now_iso
from app.models import (
    BreakGlassSession,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

# -----------------------------------------------------------------------------
# Catalog (system roles + permissions)
# -----------------------------------------------------------------------------

PERMISSIONS: dict[str, str] = {
    # Dashboard
    "dashboard:view": "Fälle und Detaildaten anzeigen",
    "debug:view": "Debug-Endpunkte (Rules/Eval) lesen",
    "meta:read": "Meta-Informationen (Stationsliste etc.) lesen",
    "ack:write": "Quittieren / Schieben",
    "reset:today": "Tages-Reset (Vers inkrementieren)",

    # RBAC / Admin
    "admin:read": "Admin-Read (User/Rollen/Permissions/Audit)",
    "admin:write": "Admin-Write (User/Rollen-Zuweisung)",
    "audit:read": "Security-/Admin-Audit lesen",

    # Break glass
    "breakglass:activate": "Notfallzugang aktivieren (self)",
    "breakglass:review": "Notfallzugang reviewen/revoken",
}

ROLES: dict[str, dict[str, object]] = {
    "viewer": {
        "description": "Nur lesen (Dashboard + Meta)",
        "perms": {"dashboard:view", "meta:read"},
    },
    "clinician": {
        "description": "Klinisch: lesen + quittieren/schieben",
        "perms": {"dashboard:view", "meta:read", "ack:write"},
    },
    "shift_lead": {
        "description": "Schichtleitung: klinisch + reset",
        "perms": {"dashboard:view", "meta:read", "ack:write", "reset:today"},
    },
    "system_admin": {
        "description": "System Admin (global): alle Berechtigungen, nicht stationsgebunden",
        "perms": set(PERMISSIONS.keys()),
    },
    "admin": {
        "description": "Admin: User/Rollen verwalten + Audit",
        "perms": {"admin:read", "admin:write", "audit:read", "breakglass:review"} | set(PERMISSIONS.keys()),
    },
    "manager": {
        "description": "Management: lesen + break-glass (self)",
        "perms": {"dashboard:view", "meta:read", "breakglass:activate"},
    },
    # Elevation role (granted via break-glass session only)
    "break_glass_admin": {
        "description": "Notfallrolle (temporär): Admin + Reset",
        "perms": {"admin:read", "admin:write", "audit:read", "reset:today", "breakglass:review"},
    },
}

DEFAULT_USERS: dict[str, dict[str, object]] = {
    "admin": {"display_name": "Initial Admin", "roles": [("system_admin", "*")]},
    "demo": {"display_name": "Demo User", "roles": [("viewer", "*")]},
    "pflege1": {"display_name": "Pflege 1", "roles": [("clinician", "*")]},
    "arzt1": {"display_name": "Arzt 1", "roles": [("clinician", "*")]},
    "manager1": {"display_name": "Manager 1", "roles": [("manager", "*")]},
}

# -----------------------------------------------------------------------------
# Seeding
# -----------------------------------------------------------------------------

# Funktion: seed_rbac – kapselt eine wiederverwendbare Backend-Operation.
def seed_rbac(db: Session) -> None:
    # permissions
    for pid, desc in PERMISSIONS.items():
        if db.get(Permission, pid) is None:
            db.add(Permission(perm_id=pid, description=desc, is_system=True))
    db.commit()

    # roles + role_permissions
    for rid, meta in ROLES.items():
        if db.get(Role, rid) is None:
            db.add(Role(role_id=rid, description=str(meta.get("description") or ""), is_system=True))
    db.commit()

    # role permissions reset
    # For system roles: ensure mapping matches catalog exactly.
    for rid, meta in ROLES.items():
        perms: Set[str] = set(meta.get("perms") or set())
        # delete existing mappings for system roles
        db.execute(delete(RolePermission).where(RolePermission.role_id == rid))
        for pid in perms:
            db.add(RolePermission(role_id=rid, perm_id=pid))
    db.commit()

    # default users + assignments
    for uid, meta in DEFAULT_USERS.items():
        if db.get(User, uid) is None:
            db.add(User(user_id=uid, display_name=meta.get("display_name"), is_active=True, created_at=utc_now_iso()))
    db.commit()

    for uid, meta in DEFAULT_USERS.items():
        for (rid, station_id) in meta.get("roles", []):
            if db.get(UserRole, (uid, rid, station_id)) is None:
                db.add(UserRole(user_id=uid, role_id=rid, station_id=station_id, created_at=utc_now_iso(), created_by="seed"))
    db.commit()

# -----------------------------------------------------------------------------
# Resolution
# -----------------------------------------------------------------------------

# Funktion: ensure_user_exists – kapselt eine wiederverwendbare Backend-Operation.
def ensure_user_exists(db: Session, user_id: str) -> User:
    """Ensures user exists. In demo mode: auto-creates with viewer role.
    In production (DEMO_MODE=false): rejects unknown users."""
    from app.config import DEMO_MODE
    u = db.get(User, user_id)
    if u is None:
        if not DEMO_MODE:
            raise HTTPException(status_code=403, detail=f"Unknown user: {user_id}. Contact admin.")
        # Demo-only: auto-create with minimal permissions
        u = User(user_id=user_id, display_name=None, is_active=True, created_at=utc_now_iso())
        db.add(u)
        db.commit()
        db.refresh(u)
        if db.get(UserRole, (user_id, "viewer", "*")) is None:
            db.add(UserRole(user_id=user_id, role_id="viewer", station_id="*", created_at=utc_now_iso(), created_by="auto"))
            db.commit()
    return u

# Funktion: _roles_for_station – kapselt eine wiederverwendbare Backend-Operation.
def _roles_for_station(db: Session, user_id: str, station_id: str) -> Set[str]:
    rows = db.execute(
        select(UserRole.role_id, UserRole.station_id).where(UserRole.user_id == user_id)
    ).all()
    out=set()
    for rid, st in rows:
        if st == "*" or st == station_id:
            out.add(rid)
    return out

# Funktion: _break_glass_roles – kapselt eine wiederverwendbare Backend-Operation.
def _break_glass_roles(db: Session, user_id: str, station_id: str, now_iso: str) -> Set[str]:
    # active sessions only
    sessions = db.execute(
        select(BreakGlassSession.station_id, BreakGlassSession.expires_at, BreakGlassSession.revoked_at)
        .where(BreakGlassSession.user_id == user_id)
    ).all()
    roles=set()
    now = datetime.fromisoformat(now_iso.replace("Z","+00:00")) if "Z" in now_iso else datetime.fromisoformat(now_iso)
    for st, expires_at, revoked_at in sessions:
        if revoked_at is not None:
            continue
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z","+00:00")) if "Z" in expires_at else datetime.fromisoformat(expires_at)
        except Exception:
            continue
        if exp <= now:
            continue
        if st == "*" or st == station_id:
            roles.add("break_glass_admin")
    return roles

# Funktion: resolve_permissions – kapselt eine wiederverwendbare Backend-Operation.
def resolve_permissions(db: Session, *, user_id: str, station_id: str) -> tuple[Set[str], Set[str], bool]:
    now_iso = utc_now_iso()
    roles = _roles_for_station(db, user_id, station_id)
    bg_roles = _break_glass_roles(db, user_id, station_id, now_iso)
    is_break_glass = bool(bg_roles)
    roles |= bg_roles

    if not roles:
        return set(), set(), is_break_glass

    rp = db.execute(
        select(RolePermission.perm_id).where(RolePermission.role_id.in_(sorted(roles)))
    ).scalars().all()
    perms=set(rp)
    return roles, perms, is_break_glass


def enforce_station_scope(db: Session, *, user_id: str, station_id: str) -> None:
    """Validate user has at least one role assignment covering the requested station.
    Raises 403 if user has no role for this station (prevents horizontal escalation).
    Wildcard (*) roles cover all stations."""
    if station_id == "*":
        return  # global scope (admin endpoints)
    rows = db.execute(
        select(UserRole.station_id).where(UserRole.user_id == user_id)
    ).scalars().all()
    allowed = set(rows)
    if "*" in allowed or station_id in allowed:
        return
    raise HTTPException(
        status_code=403,
        detail=f"Kein Zugriff auf Station {station_id}. Kontaktieren Sie den Admin.",
    )

# -----------------------------------------------------------------------------
# Enforcement dependency
# -----------------------------------------------------------------------------

# In app/rbac.py


def require_permission(permission: str):
    # auth-Import hier (nicht oben), um zirkulaere Imports zu vermeiden
    # (rbac.py wird von auth.py importiert)
    from app.auth import get_auth_context, AuthContext

    def _dep(ctx: AuthContext = Depends(get_auth_context)):
        if permission not in ctx.permissions:
            raise HTTPException(
                status_code=403, 
                detail=f"Missing permission: {permission}"
            )
        return None
    
    return _dep

# -----------------------------------------------------------------------------
# Break-glass helpers
# -----------------------------------------------------------------------------

# Funktion: activate_break_glass – kapselt eine wiederverwendbare Backend-Operation.
def activate_break_glass(
    db: Session,
    *,
    request: Request | None,
    actor_user_id: str,
    actor_station_id: str,
    station_scope: str,
    reason: str,
    duration_minutes: int = 60,
) -> BreakGlassSession:
    if duration_minutes < 5 or duration_minutes > 12 * 60:
        raise HTTPException(status_code=400, detail="duration_minutes out of range (5..720)")
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Pflichtbegründung: Mindestens 10 Zeichen erforderlich.")

    now = datetime.now(timezone.utc)
    session = BreakGlassSession(
        session_id=str(uuid.uuid4()),
        user_id=actor_user_id,
        station_id=station_scope,
        reason=reason.strip(),
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=duration_minutes)).isoformat(),
        revoked_at=None,
        revoked_by=None,
        review_note=None,
    )
    db.add(session)
    db.commit()

    log_security_event(
        db,
        request=request,
        actor_user_id=actor_user_id,
        actor_station_id=actor_station_id,
        action="BREAK_GLASS_ACTIVATE",
        target_type="break_glass_session",
        target_id=session.session_id,
        success=True,
        details={"station_scope": station_scope, "duration_minutes": duration_minutes, "reason": reason},
    )
    return session

# Funktion: revoke_break_glass – kapselt eine wiederverwendbare Backend-Operation.
def revoke_break_glass(
    db: Session,
    *,
    request: Request | None,
    actor_user_id: str,
    actor_station_id: str,
    session_id: str,
    review_note: str | None = None,
) -> None:
    s = db.get(BreakGlassSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    if s.revoked_at is not None:
        return
    s.revoked_at = utc_now_iso()
    s.revoked_by = actor_user_id
    s.review_note = review_note
    db.add(s)
    db.commit()

    log_security_event(
        db,
        request=request,
        actor_user_id=actor_user_id,
        actor_station_id=actor_station_id,
        action="BREAK_GLASS_REVOKE",
        target_type="break_glass_session",
        target_id=session_id,
        success=True,
        details={"review_note": review_note},
    )