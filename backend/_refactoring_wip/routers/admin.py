"""
Datei: backend/routers/admin.py

Zweck:
- Admin-Endpoints für User-, Rollen-, Regel-Verwaltung
- Audit-Log-Zugriff
- Break-Glass-Management

Router für administrative Operationen.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import AuthContext, require_ctx
from app.rbac import require_permission
from services.admin_service import AdminService
from services.models import (
    UserResponse,
    RoleResponse,
    RuleDefinitionResponse,
    AuditEventResponse,
    BreakGlassSessionResponse,
    CreateUserRequest,
    UpdateUserRequest,
    CreateRoleRequest,
    UpdateRoleRequest,
    UpdateRuleRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# User Management
# =============================================================================

@router.get("/users", response_model=List[UserResponse])
def list_users(ctx: AuthContext = Depends(require_ctx)):
    """Listet alle Benutzer (erfordert admin:users:read)."""
    require_permission(ctx, "admin:users:read")
    admin_service = AdminService()
    return admin_service.list_users()


@router.post("/users", response_model=UserResponse)
def create_user(
    req: CreateUserRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """Erstellt einen neuen Benutzer (erfordert admin:users:write)."""
    require_permission(ctx, "admin:users:write")
    admin_service = AdminService()
    return admin_service.create_user(req, created_by=ctx.user_id)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    req: UpdateUserRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """Aktualisiert einen Benutzer (erfordert admin:users:write)."""
    require_permission(ctx, "admin:users:write")
    admin_service = AdminService()
    return admin_service.update_user(user_id, req, updated_by=ctx.user_id)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    ctx: AuthContext = Depends(require_ctx),
):
    """Löscht einen Benutzer (erfordert admin:users:write)."""
    require_permission(ctx, "admin:users:write")
    admin_service = AdminService()
    return admin_service.delete_user(user_id, deleted_by=ctx.user_id)


# =============================================================================
# Role Management
# =============================================================================

@router.get("/roles", response_model=List[RoleResponse])
def list_roles(ctx: AuthContext = Depends(require_ctx)):
    """Listet alle Rollen (erfordert admin:roles:read)."""
    require_permission(ctx, "admin:roles:read")
    admin_service = AdminService()
    return admin_service.list_roles()


@router.post("/roles", response_model=RoleResponse)
def create_role(
    req: CreateRoleRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """Erstellt eine neue Rolle (erfordert admin:roles:write)."""
    require_permission(ctx, "admin:roles:write")
    admin_service = AdminService()
    return admin_service.create_role(req, created_by=ctx.user_id)


# =============================================================================
# Rule Management
# =============================================================================

@router.get("/rules", response_model=List[RuleDefinitionResponse])
def list_rules(ctx: AuthContext = Depends(require_ctx)):
    """Listet alle Regeln (erfordert admin:rules:read)."""
    require_permission(ctx, "admin:rules:read")
    admin_service = AdminService()
    return admin_service.list_rules()


@router.put("/rules/{rule_id}", response_model=RuleDefinitionResponse)
def update_rule(
    rule_id: str,
    req: UpdateRuleRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """Aktualisiert eine Regel (erfordert admin:rules:write)."""
    require_permission(ctx, "admin:rules:write")
    admin_service = AdminService()
    return admin_service.update_rule(rule_id, req, updated_by=ctx.user_id)


# =============================================================================
# Audit Log
# =============================================================================

@router.get("/audit", response_model=List[AuditEventResponse])
def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(require_ctx),
):
    """
    Gibt Audit-Log zurück (erfordert audit:read).
    
    - Paginiert mit limit/offset
    - Sortiert nach Timestamp (neueste zuerst)
    """
    require_permission(ctx, "audit:read")
    admin_service = AdminService()
    return admin_service.get_audit_log(limit=limit, offset=offset)


# =============================================================================
# Break-Glass Management
# =============================================================================

@router.get("/break_glass", response_model=List[BreakGlassSessionResponse])
def list_break_glass_sessions(ctx: AuthContext = Depends(require_ctx)):
    """Listet alle Break-Glass-Sessions (erfordert admin:break_glass:read)."""
    require_permission(ctx, "admin:break_glass:read")
    admin_service = AdminService()
    return admin_service.list_break_glass_sessions()


@router.post("/break_glass/{session_id}/revoke")
def revoke_break_glass_session(
    session_id: str,
    review_note: str,
    ctx: AuthContext = Depends(require_ctx),
):
    """Widerruft eine Break-Glass-Session (erfordert admin:break_glass:write)."""
    require_permission(ctx, "admin:break_glass:write")
    admin_service = AdminService()
    return admin_service.revoke_break_glass(
        session_id=session_id,
        revoked_by=ctx.user_id,
        review_note=review_note
    )


# =============================================================================
# System Status
# =============================================================================

@router.get("/status")
def get_system_status(ctx: AuthContext = Depends(require_ctx)):
    """
    Gibt System-Status zurück (erfordert admin:system:read).
    
    - Datenbank-Info
    - User-Statistiken
    - Audit-Statistiken
    """
    require_permission(ctx, "admin:system:read")
    admin_service = AdminService()
    return admin_service.get_system_status()
