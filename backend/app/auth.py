from __future__ import annotations

from dataclasses import dataclass
from typing import Set

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    station_id: str
    roles: Set[str]


def get_auth_context(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_station_id: str | None = Header(default=None, alias="X-Station-Id"),
    x_roles: str | None = Header(default="", alias="X-Roles"),
) -> AuthContext:
    # Prototyp-Defaults (später via SSO/KISIM ersetzen)
    user_id = (x_user_id or "demo").strip() or "demo"
    station_id = (x_station_id or "default").strip() or "default"

    roles = {r.strip() for r in (x_roles or "").split(",") if r.strip()}
    if not roles:
        roles = {"VIEW_DASHBOARD", "ACK_ALERT"}

    return AuthContext(user_id=user_id, station_id=station_id, roles=roles)


def require_role(ctx: AuthContext, role: str) -> None:
    if role not in ctx.roles:
        raise HTTPException(status_code=403, detail=f"Missing role: {role}")
