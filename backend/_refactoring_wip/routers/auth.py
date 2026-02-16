"""
Datei: backend/routers/auth.py

Zweck:
- Authentifizierungs-Endpoints
- Session-Management
- Break-Glass-Activation

Router für Auth-bezogene Operationen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import AuthContext, require_ctx, get_auth_context
from services.auth_service import AuthService

router = APIRouter(prefix="/api", tags=["auth"])


class WhoAmIResponse(BaseModel):
    """Response für /me Endpoint."""
    user_id: str
    station_id: str
    roles: list[str]
    permissions: list[str]
    break_glass: bool


class BreakGlassRequest(BaseModel):
    """Request für Break-Glass Activation."""
    reason: str
    station_id: str = "*"
    duration_hours: int = 2


@router.get("/me", response_model=WhoAmIResponse)
def who_am_i(ctx: AuthContext = Depends(get_auth_context)):
    """
    Gibt Informationen über den aktuellen User zurück.
    
    - User-ID
    - Station-ID
    - Rollen
    - Permissions
    - Break-Glass-Status
    """
    return WhoAmIResponse(
        user_id=ctx.user_id,
        station_id=ctx.station_id,
        roles=ctx.roles,
        permissions=ctx.permissions,
        break_glass=ctx.break_glass
    )


@router.post("/break_glass/activate")
def activate_break_glass(
    req: BreakGlassRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """
    Aktiviert Break-Glass-Zugriff.
    
    - Erfordert Permission "break_glass:self"
    - Zeitlich begrenzt (default: 2 Stunden)
    - Vollständig auditiert
    - Erfordert Begründung
    """
    from app.rbac import require_permission, activate_break_glass as rbac_activate
    
    require_permission(ctx, "break_glass:self")
    
    if not req.reason or len(req.reason) < 10:
        raise HTTPException(
            status_code=400,
            detail="Begründung muss mindestens 10 Zeichen haben"
        )
    
    auth_service = AuthService()
    session = auth_service.activate_break_glass(
        user_id=ctx.user_id,
        station_id=req.station_id,
        reason=req.reason,
        duration_hours=req.duration_hours
    )
    
    return {
        "session_id": session.session_id,
        "expires_at": session.expires_at,
        "message": "Break-Glass aktiviert. Zugriff läuft ab: " + session.expires_at
    }


@router.get("/stations")
def list_stations(ctx: AuthContext = Depends(require_ctx)):
    """
    Listet alle verfügbaren Stationen.
    
    - Für User-Dropdown im Frontend
    - Filtert nach Berechtigungen des Users
    """
    auth_service = AuthService()
    return auth_service.list_stations_for_user(ctx.user_id)


@router.get("/users")
def list_demo_users(ctx: AuthContext = Depends(get_auth_context)):
    """
    Listet Demo-User (nur wenn DEMO_AUTH aktiviert).
    
    - Nur für Entwicklung!
    - In Produktion nicht verfügbar
    """
    import os
    
    if os.getenv("DASHBOARD_ALLOW_DEMO_AUTH") != "1":
        raise HTTPException(status_code=403, detail="Demo-Auth nicht aktiviert")
    
    auth_service = AuthService()
    return auth_service.list_demo_users()
