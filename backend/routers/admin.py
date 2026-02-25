"""Admin-Endpoints: User/Role/Permission CRUD, Rules, Audit, Break-Glass, CSV, ShiftReasons."""
from __future__ import annotations
import io
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from app.auth import AuthContext, get_auth_context, require_ctx
from app.rbac import require_permission, activate_break_glass, revoke_break_glass
from app.audit import log_security_event
from app.db import SessionLocal
from app.models import (
    User, Role, Permission, UserRole, RolePermission,
    BreakGlassSession, RuleDefinition, Case, ShiftReason, Ack, AckEvent,
)
from app.schemas import (
    AdminUserCreate, AdminUserUpdate, AdminAssignRole,
    AdminPermissionCreate, AdminPermissionUpdate,
    AdminRoleCreate, AdminRoleUpdate, AdminRolePermissions,
    AdminRuleUpsert, BreakGlassActivateReq, BreakGlassRevokeReq,
    ShiftReasonCreate, ShiftReasonUpdate, AdminUserRoleAssignment,
)
from app.config import STATION_CENTER
from app.rule_engine import invalidate_rule_cache, load_rules_yaml
from app.case_logic import seed_dummy_cases_to_db

router = APIRouter()



@router.get("/api/admin/users")
def admin_list_users(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import User, UserRole
    with SessionLocal() as db:
        users = db.query(User).order_by(User.user_id.asc()).all()
        roles = db.query(UserRole).all()
        by_user: dict[str, list[dict[str, str]]] = {}
        for r in roles:
            by_user.setdefault(r.user_id, []).append({"role_id": r.role_id, "station_id": r.station_id})
        return {
            "users": [
                {
                    "user_id": u.user_id,
                    "display_name": u.display_name,
                    "is_active": bool(u.is_active),
                    "created_at": u.created_at,
                    "roles": sorted(by_user.get(u.user_id, []), key=lambda x: (x["role_id"], x["station_id"])),
                }
                for u in users
            ]
        }


@router.post("/api/admin/users")
def admin_create_user(
    body: AdminUserCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, UserRole, Role
    with SessionLocal() as db:
        if db.get(User, body.user_id) is not None:
            raise HTTPException(status_code=409, detail="user already exists")
        u = User(user_id=body.user_id.strip(), display_name=body.display_name, is_active=body.is_active, created_at=datetime.now(timezone.utc).isoformat())
        db.add(u)

        # optional: initial role assignments
        for ra in body.roles or []:
            rid = (ra.role_id or "").strip()
            st = (ra.station_id or "*").strip() or "*"
            if not rid:
                continue
            if db.get(Role, rid) is None:
                continue
            if db.get(UserRole, (u.user_id, rid, st)) is None:
                db.add(UserRole(user_id=u.user_id, role_id=rid, station_id=st, created_at=datetime.now(timezone.utc).isoformat(), created_by=ctx.user_id))

        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_CREATE",
            target_type="user",
            target_id=u.user_id,
            success=True,
            details={"display_name": body.display_name, "is_active": body.is_active},
        )
        return {"user_id": u.user_id}


@router.put("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User
    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        if body.display_name is not None:
            u.display_name = body.display_name
        if body.is_active is not None:
            u.is_active = bool(body.is_active)
        db.add(u)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_UPDATE",
            target_type="user",
            target_id=user_id,
            success=True,
            details={"display_name": body.display_name, "is_active": body.is_active},
        )
        return {"ok": True}


@router.post("/api/admin/users/{user_id}/roles")
def admin_assign_role(
    user_id: str,
    body: AdminAssignRole,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, Role, UserRole
    with SessionLocal() as db:
        if db.get(User, user_id) is None:
            raise HTTPException(status_code=404, detail="user not found")
        if db.get(Role, body.role_id) is None:
            raise HTTPException(status_code=404, detail="role not found")
        key=(user_id, body.role_id, body.station_id)
        if db.get(UserRole, key) is None:
            db.add(UserRole(user_id=user_id, role_id=body.role_id, station_id=body.station_id, created_at=datetime.now(timezone.utc).isoformat(), created_by=ctx.user_id))
            db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_ASSIGN",
            target_type="user_role",
            target_id=":".join(key),
            success=True,
            details={"user_id": user_id, "role_id": body.role_id, "station_id": body.station_id},
        )
        return {"ok": True}


@router.delete("/api/admin/users/{user_id}/roles/{role_id}/{station_id}")
def admin_remove_role(
    user_id: str,
    role_id: str,
    station_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import UserRole
    with SessionLocal() as db:
        r = db.get(UserRole, (user_id, role_id, station_id))
        if r is None:
            raise HTTPException(status_code=404, detail="assignment not found")
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_REMOVE",
            target_type="user_role",
            target_id=":".join([user_id, role_id, station_id]),
            success=True,
        )
        return {"ok": True}


@router.get("/api/admin/roles")
def admin_list_roles(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import Role, RolePermission
    with SessionLocal() as db:
        roles = db.query(Role).order_by(Role.role_id.asc()).all()
        rp = db.query(RolePermission).all()
        by_role: dict[str, list[str]] = {}
        for row in rp:
            by_role.setdefault(row.role_id, []).append(row.perm_id)
        return {
            "roles": [
                {
                    "role_id": r.role_id,
                    "description": r.description,
                    "permissions": sorted(by_role.get(r.role_id, [])),
                    "is_system": bool(r.is_system),
                }
                for r in roles
            ]
        }


@router.get("/api/admin/permissions")
def admin_list_permissions(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    from app.models import Permission
    with SessionLocal() as db:
        rows = db.query(Permission).order_by(Permission.perm_id.asc()).all()
        return {
            "permissions": [
                {"perm_id": p.perm_id, "description": p.description, "is_system": bool(p.is_system)}
                for p in rows
            ]
        }


@router.post("/api/admin/permissions")
def admin_create_permission(
    body: AdminPermissionCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission
    with SessionLocal() as db:
        pid = body.perm_id.strip()
        if db.get(Permission, pid) is not None:
            raise HTTPException(status_code=409, detail="permission already exists")
        db.add(Permission(perm_id=pid, description=body.description, is_system=False))
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_CREATE",
            target_type="permission",
            target_id=pid,
            success=True,
            details={"description": body.description},
        )
        return {"perm_id": pid}


@router.put("/api/admin/permissions/{perm_id}")
def admin_update_permission(
    perm_id: str,
    body: AdminPermissionUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission
    with SessionLocal() as db:
        p = db.get(Permission, perm_id)
        if p is None:
            raise HTTPException(status_code=404, detail="permission not found")
        if body.description is not None:
            p.description = body.description
        db.add(p)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_UPDATE",
            target_type="permission",
            target_id=perm_id,
            success=True,
            details={"description": body.description},
        )
        return {"ok": True}


@router.delete("/api/admin/permissions/{perm_id}")
def admin_delete_permission(
    perm_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Permission, RolePermission
    with SessionLocal() as db:
        p = db.get(Permission, perm_id)
        if p is None:
            raise HTTPException(status_code=404, detail="permission not found")
        if bool(p.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system permission")
        # remove mappings first
        db.query(RolePermission).filter(RolePermission.perm_id == perm_id).delete()
        db.delete(p)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_PERMISSION_DELETE",
            target_type="permission",
            target_id=perm_id,
            success=True,
        )
        return {"ok": True}


@router.post("/api/admin/roles")
def admin_create_role(
    body: AdminRoleCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role
    with SessionLocal() as db:
        rid = body.role_id.strip()
        if db.get(Role, rid) is not None:
            raise HTTPException(status_code=409, detail="role already exists")
        db.add(Role(role_id=rid, description=body.description, is_system=False))
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_CREATE",
            target_type="role",
            target_id=rid,
            success=True,
            details={"description": body.description},
        )
        return {"role_id": rid}


@router.put("/api/admin/roles/{role_id}")
def admin_update_role(
    role_id: str,
    body: AdminRoleUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role
    with SessionLocal() as db:
        r = db.get(Role, role_id)
        if r is None:
            raise HTTPException(status_code=404, detail="role not found")
        if body.description is not None:
            r.description = body.description
        db.add(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_UPDATE",
            target_type="role",
            target_id=role_id,
            success=True,
            details={"description": body.description},
        )
        return {"ok": True}


@router.delete("/api/admin/roles/{role_id}")
def admin_delete_role(
    role_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role, RolePermission, UserRole
    with SessionLocal() as db:
        r = db.get(Role, role_id)
        if r is None:
            raise HTTPException(status_code=404, detail="role not found")
        if bool(r.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system role")
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        db.query(UserRole).filter(UserRole.role_id == role_id).delete()
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_DELETE",
            target_type="role",
            target_id=role_id,
            success=True,
        )
        return {"ok": True}


@router.put("/api/admin/roles/{role_id}/permissions")
def admin_set_role_permissions(
    role_id: str,
    body: AdminRolePermissions,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import Role, Permission, RolePermission
    with SessionLocal() as db:
        role = db.get(Role, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="role not found")
        if bool(role.is_system):
            raise HTTPException(status_code=400, detail="cannot edit system role permissions")

        desired = sorted({p.strip() for p in (body.permissions or []) if p and p.strip()})
        # validate permissions exist
        for pid in desired:
            if db.get(Permission, pid) is None:
                raise HTTPException(status_code=400, detail=f"unknown permission: {pid}")

        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        for pid in desired:
            db.add(RolePermission(role_id=role_id, perm_id=pid))
        db.commit()

        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_ROLE_PERMISSIONS_SET",
            target_type="role",
            target_id=role_id,
            success=True,
            details={"permissions": desired},
        )
        return {"ok": True, "permissions": desired}


@router.delete("/api/admin/users/{user_id}")
def admin_delete_user(
    user_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    from app.models import User, UserRole
    with SessionLocal() as db:
        u = db.get(User, user_id)
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        # prevent locking yourself out accidentally
        if u.user_id == ctx.user_id:
            raise HTTPException(status_code=400, detail="cannot delete own user")

        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        db.delete(u)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_USER_DELETE",
            target_type="user",
            target_id=user_id,
            success=True,
        )
        return {"ok": True}


@router.get("/api/admin/rules")
def admin_list_rules(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
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


@router.put("/api/admin/rules/{rule_id}")
def admin_upsert_rule(
    rule_id: str,
    body: AdminRuleUpsert,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    if body.rule_id.strip() != rule_id.strip():
        raise HTTPException(status_code=400, detail="rule_id mismatch")

    # Hard guard: prevent unknown operator injection
    allowed_ops = {">", ">=", "is_null", "is_true", "is_false"}
    if body.operator not in allowed_ops:
        raise HTTPException(status_code=400, detail=f"unsupported operator: {body.operator}")

    with SessionLocal() as db:
        r = db.get(RuleDefinition, rule_id)
        if r is None:
            r = RuleDefinition(rule_id=rule_id, is_system=False)
            db.add(r)

        r.display_name = body.display_name
        r.message = body.message
        r.explanation = body.explanation
        r.category = body.category
        r.severity = body.severity
        r.metric = body.metric
        r.operator = body.operator
        r.value_json = json.dumps(body.value, ensure_ascii=False)
        r.enabled = bool(body.enabled)
        r.updated_at = datetime.now(timezone.utc).isoformat()
        r.updated_by = ctx.user_id
        db.add(r)
        db.commit()

        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_RULE_UPSERT",
            target_type="rule_definition",
            target_id=rule_id,
            success=True,
            details={
                "display_name": body.display_name,
                "message": body.message,
                "category": body.category,
                "severity": body.severity,
                "metric": body.metric,
                "operator": body.operator,
                "value": body.value,
                "enabled": body.enabled,
            },
        )
        return {"ok": True, "rule_id": rule_id}


@router.delete("/api/admin/rules/{rule_id}")
def admin_delete_rule(
    rule_id: str,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    with SessionLocal() as db:
        r = db.get(RuleDefinition, rule_id)
        if r is None:
            raise HTTPException(status_code=404, detail="rule not found")
        if bool(r.is_system):
            raise HTTPException(status_code=400, detail="cannot delete system rule")
        db.delete(r)
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="ADMIN_RULE_DELETE",
            target_type="rule_definition",
            target_id=rule_id,
            success=True,
        )
        return {"ok": True}


@router.get("/api/admin/audit")
def admin_audit(
    limit: int = 200,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("audit:read")),
):
    from app.models import SecurityEvent
    with SessionLocal() as db:
        rows = (
            db.query(SecurityEvent)
            .order_by(SecurityEvent.ts.desc())
            .limit(max(1, min(int(limit), 1000)))
            .all()
        )
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "ts": e.ts,
                    "actor_user_id": e.actor_user_id,
                    "actor_station_id": e.actor_station_id,
                    "action": e.action,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "success": bool(e.success),
                    "message": e.message,
                    "ip": e.ip,
                    "user_agent": e.user_agent,
                    "details": e.details,
                }
                for e in rows
            ]
        }


@router.post("/api/break_glass/activate")
def break_glass_activate(
    body: BreakGlassActivateReq,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _ctx: str = Depends(require_ctx),
    _perm: None = Depends(require_permission("breakglass:activate")),
):
    with SessionLocal() as db:
        s = activate_break_glass(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            station_scope=body.station_scope,
            reason=body.reason,
            duration_minutes=body.duration_minutes,
        )
        return {"session_id": s.session_id, "expires_at": s.expires_at, "station_scope": s.station_id}


@router.post("/api/admin/break_glass/{session_id}/revoke")
def break_glass_revoke(
    session_id: str,
    body: BreakGlassRevokeReq,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("breakglass:review")),
):
    with SessionLocal() as db:
        revoke_break_glass(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            session_id=session_id,
            review_note=body.review_note,
        )
    return {"ok": True}


@router.get("/api/admin/break_glass")
def break_glass_list(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("breakglass:review")),
):
    from app.models import BreakGlassSession
    with SessionLocal() as db:
        rows = db.query(BreakGlassSession).order_by(BreakGlassSession.created_at.desc()).limit(200).all()
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "station_id": s.station_id,
                    "reason": s.reason,
                    "created_at": s.created_at,
                    "expires_at": s.expires_at,
                    "revoked_at": s.revoked_at,
                    "revoked_by": s.revoked_by,
                    "review_note": s.review_note,
                }
                for s in rows
            ]
        }


# ============================================================
# CSV Import / Export
# ============================================================

_CSV_FIELDS = [
    "case_id", "station_id", "patient_id", "patient_initials", "clinic", "center",
    "admission_date", "discharge_date",
    "honos_entry_total", "honos_entry_date", "honos_discharge_total", "honos_discharge_date", "honos_discharge_suicidality",
    "bscl_total_entry", "bscl_entry_date", "bscl_total_discharge", "bscl_discharge_date", "bscl_discharge_suicidality",
    "bfs_1", "bfs_2", "bfs_3",
    "is_voluntary", "treatment_plan_date", "sdep_complete",
    "ekg_last_date", "ekg_last_reported", "ekg_entry_date",
    "clozapin_active", "clozapin_start_date", "neutrophils_last_date", "neutrophils_last_value",
    "troponin_last_date", "cbc_last_date",
    "emergency_bem_start_date", "emergency_med_start_date",
    "allergies_recorded", "isolations_json",
]

def generate_sample_csv() -> str:
    """Gibt eine Beispiel-CSV mit Header + 2 Beispielzeilen zurück."""
    import csv as csv_mod
    buf = io.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(_CSV_FIELDS)
    writer.writerow([
        "F-2025-0001", "Station A1", "P001", "MM", "EPP", "ZAPE",
        "2025-02-01", "",
        "18", "2025-02-02", "", "", "",
        "45", "2025-02-02", "", "", "",
        "A", "B", "",
        "True", "2025-02-03", "",
        "2025-02-01", "True", "2025-02-01",
        "False", "", "", "",
        "", "",
        "", "",
        "True", "",
    ])
    writer.writerow([
        "F-2025-0002", "Station A1", "P002", "AB", "EPP", "ZAPE",
        "2025-02-10", "2025-02-18",
        "22", "2025-02-11", "15", "2025-02-18", "0",
        "50", "2025-02-11", "38", "2025-02-18", "0",
        "A", "B", "C",
        "False", "2025-02-11", "True",
        "2025-02-10", "True", "2025-02-10",
        "True", "2025-02-12", "2025-02-15", "3.2",
        "2025-02-14", "2025-02-15",
        "", "",
        "True", "",
    ])
    return buf.getvalue()


@router.post("/api/admin/csv/upload")
def csv_upload(
    request: Request,
    file: UploadFile = File(...),
    station_id: str = Form(default=""),
    overwrite: str = Form(default="false"),
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """CSV-Upload: Importiert Fälle aus CSV/Excel in die Datenbank."""
    import csv as csv_mod

    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    errors = []
    imported = 0
    skipped = 0
    total = 0

    try:
        raw = file.file.read(MAX_UPLOAD_SIZE + 1)
        if len(raw) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="Datei zu gross (max. 10 MB)")
        # Dateiname-Validierung
        fname = (file.filename or "").strip()
        if fname and not fname.lower().endswith((".csv", ".txt")):
            raise HTTPException(status_code=400, detail="Nur CSV-Dateien erlaubt (.csv, .txt)")
        # Try UTF-8 first, then latin-1
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

        reader = csv_mod.DictReader(io.StringIO(text))
        do_overwrite = overwrite.lower() in ("true", "1", "yes")

        with SessionLocal() as db:
            for row_num, row in enumerate(reader, start=2):
                total += 1
                try:
                    cid = (row.get("case_id") or "").strip()
                    if not cid:
                        errors.append({"row": row_num, "error": "case_id fehlt", "case_id": ""})
                        continue

                    sid = station_id.strip() if station_id.strip() else (row.get("station_id") or "").strip()
                    if not sid:
                        errors.append({"row": row_num, "error": "station_id fehlt", "case_id": cid})
                        continue

                    existing = db.get(Case, cid)
                    if existing and not do_overwrite:
                        skipped += 1
                        continue

                    c = existing or Case(case_id=cid)
                    c.station_id = sid
                    c.patient_id = row.get("patient_id") or None
                    c.patient_initials = row.get("patient_initials") or None
                    c.clinic = row.get("clinic") or "EPP"
                    c.center = row.get("center") or STATION_CENTER.get(sid, "UNKNOWN")
                    c.admission_date = row.get("admission_date") or date.today().isoformat()
                    c.discharge_date = row.get("discharge_date") or None

                    # Int fields
                    for fld in ["honos_entry_total", "honos_discharge_total", "honos_discharge_suicidality",
                                "bscl_total_entry", "bscl_total_discharge", "bscl_discharge_suicidality"]:
                        val = (row.get(fld) or "").strip()
                        setattr(c, fld, int(val) if val else None)

                    # Date fields
                    for fld in ["honos_entry_date", "honos_discharge_date", "bscl_entry_date", "bscl_discharge_date",
                                "treatment_plan_date", "ekg_last_date", "ekg_entry_date",
                                "clozapin_start_date", "neutrophils_last_date", "troponin_last_date", "cbc_last_date",
                                "emergency_bem_start_date", "emergency_med_start_date"]:
                        val = (row.get(fld) or "").strip()
                        setattr(c, fld, val if val else None)

                    # String fields
                    for fld in ["bfs_1", "bfs_2", "bfs_3", "neutrophils_last_value", "isolations_json"]:
                        val = (row.get(fld) or "").strip()
                        setattr(c, fld, val if val else None)

                    # Bool fields
                    for fld in ["is_voluntary", "sdep_complete", "ekg_last_reported", "clozapin_active", "allergies_recorded"]:
                        val = (row.get(fld) or "").strip().lower()
                        if val in ("true", "1", "yes", "ja"):
                            setattr(c, fld, True)
                        elif val in ("false", "0", "no", "nein"):
                            setattr(c, fld, False)
                        else:
                            setattr(c, fld, None)

                    c.imported_at = datetime.now(timezone.utc).isoformat()
                    c.imported_by = ctx.user_id
                    c.source = "csv"

                    if not existing:
                        db.add(c)
                    imported += 1

                except Exception as e:
                    errors.append({"row": row_num, "error": str(e), "case_id": row.get("case_id", "")})

            db.commit()

        # Audit log in separate session
        with SessionLocal() as db2:
            log_security_event(
                db2,
                request=request,
                actor_user_id=ctx.user_id,
                actor_station_id=ctx.station_id,
                action="CSV_UPLOAD",
                target_type="case_data",
                target_id=f"{imported} imported",
                success=imported > 0,
                details={"total": total, "imported": imported, "skipped": skipped, "errors": len(errors)},
            )

    except Exception as e:
        return {
            "success": False, "total_rows": total, "imported_rows": imported,
            "skipped_rows": skipped, "failed_rows": len(errors) + 1,
            "errors": errors + [{"row": 0, "error": str(e), "case_id": ""}],
        }

    return {
        "success": len(errors) == 0,
        "total_rows": total,
        "imported_rows": imported,
        "skipped_rows": skipped,
        "failed_rows": len(errors),
        "errors": errors[:50],  # limit error list
    }


@router.get("/api/admin/csv/sample")
def csv_sample(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    """Gibt eine Beispiel-CSV zurück."""
    from fastapi.responses import Response
    csv_content = generate_sample_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_cases.csv"},
    )


@router.get("/api/admin/cases/count")
def admin_cases_count(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    """Gibt die Anzahl der importierten Fälle zurück."""
    with SessionLocal() as db:
        total = db.query(Case).count()
        by_station = {}
        stations = db.query(Case.station_id).distinct().all()
        for (sid,) in stations:
            by_station[sid] = db.query(Case).filter(Case.station_id == sid).count()
    return {"total": total, "by_station": by_station}


@router.delete("/api/admin/cases/all")
def admin_delete_all_cases(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Löscht ALLE importierten Fälle (Vorsicht!)."""
    with SessionLocal() as db:
        count = db.query(Case).count()
        db.query(Case).delete()
        db.commit()
        log_security_event(
            db,
            request=request,
            actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id,
            action="CASES_DELETE_ALL",
            target_type="case_data",
            target_id="*",
            success=True,
            details={"deleted_count": count},
        )
    return {"ok": True, "deleted": count}


@router.get("/api/admin/shift_reasons")
def admin_list_shift_reasons(
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:read")),
):
    """Gibt alle Schiebe-Gründe zurück (inkl. inaktiver)."""
    with SessionLocal() as db:
        reasons = db.query(ShiftReason).order_by(ShiftReason.sort_order).all()
        return {
            "reasons": [
                {
                    "id": r.id,
                    "code": r.code,
                    "label": r.label,
                    "description": r.description,
                    "is_active": r.is_active,
                    "sort_order": r.sort_order,
                }
                for r in reasons
            ]
        }


@router.post("/api/admin/shift_reasons")
def create_shift_reason(
    body: ShiftReasonCreate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Erstellt einen neuen Schiebe-Grund."""
    with SessionLocal() as db:
        existing = db.query(ShiftReason).filter(ShiftReason.code == body.code).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Code '{body.code}' existiert bereits")
        reason = ShiftReason(
            code=body.code.strip(),
            label=body.label.strip(),
            description=body.description,
            sort_order=body.sort_order,
            is_active=True,
        )
        db.add(reason)
        db.commit()
        db.refresh(reason)
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="SHIFT_REASON_CREATE",
            target_type="shift_reason", target_id=str(reason.id), success=True,
            details={"code": body.code, "label": body.label},
        )
        return {"id": reason.id, "code": reason.code}


@router.put("/api/admin/shift_reasons/{reason_id}")
def update_shift_reason(
    reason_id: int,
    body: ShiftReasonUpdate,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Aktualisiert einen Schiebe-Grund."""
    with SessionLocal() as db:
        reason = db.get(ShiftReason, reason_id)
        if not reason:
            raise HTTPException(status_code=404, detail="Shift-Grund nicht gefunden")
        if body.label is not None:
            reason.label = body.label.strip()
        if body.description is not None:
            reason.description = body.description
        if body.is_active is not None:
            reason.is_active = body.is_active
        if body.sort_order is not None:
            reason.sort_order = body.sort_order
        db.commit()
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="SHIFT_REASON_UPDATE",
            target_type="shift_reason", target_id=str(reason_id), success=True,
        )
        return {"ok": True}


@router.delete("/api/admin/shift_reasons/{reason_id}")
def delete_shift_reason(
    reason_id: int,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Löscht einen Schiebe-Grund."""
    with SessionLocal() as db:
        reason = db.get(ShiftReason, reason_id)
        if not reason:
            raise HTTPException(status_code=404, detail="Shift-Grund nicht gefunden")
        db.delete(reason)
        db.commit()
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="SHIFT_REASON_DELETE",
            target_type="shift_reason", target_id=str(reason_id), success=True,
        )
        return {"ok": True}


# ───────────────────────────────────────────────────────────────
# Excel-Daten Reload
# ───────────────────────────────────────────────────────────────

@router.post("/api/admin/reload-excel")
def reload_excel_data(
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    _perm: None = Depends(require_permission("admin:write")),
):
    """Laedt Excel-Demodaten neu (nach Austausch von demo_cases.xlsx).

    Leert den Cache des Excel-Loaders und seeded die DB neu.
    """
    from app.excel_loader import reload as excel_reload, get_demo_cases
    excel_reload()
    seed_dummy_cases_to_db()

    # Station-Center Map neu laden
    if hasattr(STATION_CENTER, '_loaded'):
        STATION_CENTER.reload()

    with SessionLocal() as db:
        log_security_event(
            db, request=request, actor_user_id=ctx.user_id,
            actor_station_id=ctx.station_id, action="EXCEL_RELOAD",
            target_type="data", target_id="demo_cases.xlsx", success=True,
        )

    cases = get_demo_cases()
    stations = sorted({c["station_id"] for c in cases})

    return {
        "ok": True,
        "cases_loaded": len(cases),
        "stations": stations,
    }
