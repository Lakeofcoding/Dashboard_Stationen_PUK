from __future__ import annotations

from dataclasses import dataclass
from typing import Set

from fastapi import Header, HTTPException
import os


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
    """Liefert den Auth-Kontext.

    SECURITY-Hinweis:
    - In Produktion dürfen Rollen/Station nicht "vom Browser" kommen.
    - Typischerweise setzt ein Reverse Proxy (SSO) verlässliche Header
      oder ein JWT, das das Backend prüft.

    Für lokale Entwicklung gibt es einen expliziten Demo-Schalter:
      DASHBOARD_ALLOW_DEMO_AUTH=1
    Dann sind Defaults erlaubt.
    """

    allow_demo = os.getenv("DASHBOARD_ALLOW_DEMO_AUTH", "0") == "1"

    user_id = (x_user_id or "").strip()
    station_id = (x_station_id or "").strip()
    roles = {r.strip() for r in (x_roles or "").split(",") if r.strip()}

    if allow_demo:
        # Nur Entwicklung: bequeme Defaults.
        if not user_id:
            user_id = "demo"
        if not station_id:
            station_id = "B0"
        if not roles:
            roles = {"VIEW_DASHBOARD", "ACK_ALERT"}
    else:
        # Produktion: fehlende Identität -> 401.
        if not user_id or not station_id:
            raise HTTPException(status_code=401, detail="Unauthorized: missing identity headers")
        if not roles:
            # Wenn Rollen leer sind, lassen wir den User zwar existieren,
            # aber er hat dann keine Rechte.
            roles = set()

    return AuthContext(user_id=user_id, station_id=station_id, roles=roles)


def require_role(ctx: AuthContext, role: str) -> None:
    if role not in ctx.roles:
        raise HTTPException(status_code=403, detail=f"Missing role: {role}")
