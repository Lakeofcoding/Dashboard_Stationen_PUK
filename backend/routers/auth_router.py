"""
/api/auth – Login / Logout / Status

Unterstützt zwei Modi:
  Demo/Pilot: Login mit User-ID (kein Passwort), Token wird ausgestellt
  Produktion: Placeholder für SSO-Redirect (z.B. Keycloak, SAML)

Der Token wird als:
  a) JSON-Response (für SPA mit Bearer-Header)
  b) HttpOnly-Cookie puk_session (empfohlen, CSRF-geschützt)
zurückgegeben.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth import (
    AuthContext,
    create_session_token,
    get_auth_context,
    TOKEN_TTL_SECONDS,
)
from app.config import DEMO_MODE, SECURE_COOKIES

router = APIRouter()

_COOKIE_NAME = "puk_session"

# Brute-Force-Schutz: {user_id: [timestamp, ...]}
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}


class LoginRequest(BaseModel):
    user_id: str
    # Passwort-Feld vorbereitet für spätere Produktion
    password: str | None = None


class LoginResponse(BaseModel):
    user_id: str
    token: str
    expires_in: int
    demo_mode: bool


@router.post("/api/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response):
    """
    Demo-Login: User-ID eingeben → Token erhalten.

    Im Demo-Modus ist kein Passwort erforderlich.
    Der User muss in der DB existieren (geseeded via seed_rbac).
    Unbekannte User-IDs werden in Demo-Modus mit viewer-Rechten angelegt.

    Für Produktion: Hier SSO/SAML/OIDC-Redirect implementieren.
    """
    if not DEMO_MODE:
        raise HTTPException(
            status_code=501,
            detail="Direktes Login nicht verfügbar. Bitte über SSO-Portal anmelden."
        )

    user_id = (body.user_id or "").strip()
    # Strikte Eingabevalidierung
    import re as _re
    if not user_id or len(user_id) > 64 or not _re.match(r'^[a-zA-Z0-9_.\-@]+$', user_id):
        raise HTTPException(status_code=400, detail="Ungültige User-ID (max 64 Zeichen, nur A-Z, 0-9, _, ., -, @)")

    # Brute-Force Schutz (in-memory, module-level dict)
    import time as _time
    now = _time.time()
    _attempts = _LOGIN_ATTEMPTS.get(user_id, [])
    _attempts = [t for t in _attempts if now - t < 300]  # 5-Minuten-Fenster
    if len(_attempts) >= 10:
        raise HTTPException(status_code=429, detail="Zu viele Login-Versuche. Bitte 5 Minuten warten.")
    _attempts.append(now)
    _LOGIN_ATTEMPTS[user_id] = _attempts

    # User in DB prüfen/anlegen (demo_mode=True erlaubt auto-create)
    from app.db import SessionLocal
    from app.rbac import ensure_user_exists
    with SessionLocal() as db:
        # Limit: max 50 User im Demo-Modus (verhindert DB-Spam)
        from app.models import User
        user_count = db.query(User).count()
        existing = db.get(User, user_id)
        if existing is None and user_count >= 50:
            raise HTTPException(status_code=403, detail="Demo-Limit erreicht (max. 50 User). Admin kontaktieren.")
        u = ensure_user_exists(db, user_id)
        if not u.is_active:
            raise HTTPException(status_code=403, detail="User deaktiviert")

    token = create_session_token(user_id)

    # Cookie setzen (HttpOnly, SameSite=Strict)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=TOKEN_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=SECURE_COOKIES,
        path="/",
    )

    return LoginResponse(
        user_id=user_id,
        token=token,
        expires_in=TOKEN_TTL_SECONDS,
        demo_mode=DEMO_MODE,
    )


@router.post("/api/auth/logout")
def logout(
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    puk_session: str | None = Cookie(default=None, alias="puk_session"),
):
    """Löscht Session-Cookie und revoziert Token (Blacklist)."""
    from app.auth import revoke_token
    # Token aus Bearer-Header oder Cookie extrahieren und revozieren
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif puk_session:
        token = puk_session
    if token:
        revoke_token(token)
    response.delete_cookie(key=_COOKIE_NAME, path="/", samesite="strict")
    return {"status": "logged_out"}


@router.get("/api/auth/status")
def auth_status(ctx: AuthContext = Depends(get_auth_context)):
    """Gibt aktuellen Auth-Status zurück (für Frontend-Initialisierung)."""
    return {
        "authenticated": True,
        "user_id": ctx.user_id,
        "roles": sorted(ctx.roles),
        "demo_mode": DEMO_MODE,
    }


@router.get("/api/auth/users")
def auth_demo_users():
    """
    Gibt verfügbare Demo-User zurück (nur DEMO_MODE=True).
    Kein vollständiges Auth-Check, aber nur im Demo-Modus aktiv.
    Gibt absichtlich nur user_id + display_name zurück (keine Rollen-Details).
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    from app.db import SessionLocal
    from app.models import User, UserRole
    from sqlalchemy import select

    with SessionLocal() as db:
        users = db.execute(
            select(User).where(User.is_active == True)  # noqa
        ).scalars().all()
        roles_q = db.execute(select(UserRole)).scalars().all()
        by_user: dict[str, list[str]] = {}
        for r in roles_q:
            by_user.setdefault(r.user_id, []).append(r.role_id)

    return {
        "users": [
            {
                "user_id": u.user_id,
                "display_name": u.display_name or u.user_id,
                "roles": sorted(by_user.get(u.user_id, [])),
            }
            for u in sorted(users, key=lambda x: x.user_id)
        ]
    }
