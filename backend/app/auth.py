from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from fastapi import Depends, Header, HTTPException, Query

from app.db import SessionLocal
from app.rbac import ensure_user_exists, resolve_permissions


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    station_id: str  # "*" means global scope
    roles: Set[str]
    permissions: Set[str]
    is_break_glass: bool


def get_ctx(
    ctx: str | None = Query(default=None, description="Station context (e.g. ST01) or 'global'"),
    x_scope_ctx: str | None = Header(default=None, alias="X-Scope-Ctx"),
    x_station_id: str | None = Header(default=None, alias="X-Station-Id"),
) -> Optional[str]:
    """Returns the requested scope context.

    Priority:
      1) query ?ctx=...
      2) header X-Scope-Ctx
      3) legacy header X-Station-Id
    """
    raw = (ctx or x_scope_ctx or x_station_id)
    if raw is None:
        return None
    val = str(raw).strip()
    return val or None


def require_ctx(ctx: Optional[str] = Depends(get_ctx)) -> str:
    """Station endpoints must be called with an explicit context."""
    if ctx is None:
        raise HTTPException(status_code=422, detail="Missing required ctx (station scope)")
    return ctx


def _normalize_station_id(ctx: Optional[str]) -> str:
    if ctx is None:
        return "*"
    c = ctx.strip()
    if not c:
        return "*"
    if c.lower() == "global":
        return "*"
    return c


def get_auth_context(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    ctx: Optional[str] = Depends(get_ctx),
) -> AuthContext:
    """Identity hint via headers; authorization resolved from DB (RBAC).

    - Identity/SSO is intentionally *not* coupled to roles.
    - Scope context is optional for global admin endpoints, but required for station-scoped endpoints.
    """
    user_id = (x_user_id or "demo").strip() or "demo"
    station_id = _normalize_station_id(ctx)

    with SessionLocal() as db:
        u = ensure_user_exists(db, user_id)
        if not u.is_active:
            raise HTTPException(status_code=403, detail="User disabled")
        roles, perms, is_bg = resolve_permissions(db, user_id=user_id, station_id=station_id)

    return AuthContext(user_id=user_id, station_id=station_id, roles=roles, permissions=perms, is_break_glass=is_bg)


def require_role(ctx: AuthContext, role: str) -> None:
    """Legacy helper (kept for compatibility)."""
    if role not in ctx.roles:
        raise HTTPException(status_code=403, detail=f"Missing role: {role}")
