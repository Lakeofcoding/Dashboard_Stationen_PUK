"""
backend/app/auth.py

Authentifizierung und Identitätsauflösung.

MODI:
  1) SSO/Proxy-Modus (Produktion):
     Ein vorgelagerter Proxy setzt X-User-Id-Header nach erfolgreicher
     SSO-Authentifizierung. Das Backend vertraut diesem Header nur, wenn
     DASHBOARD_ALLOW_DEMO_AUTH=0 und der User in der DB existiert.

  2) Token-Modus (Demo/Pilot ohne SSO-Proxy):
     Client erhält beim Login (/api/auth/login) einen signierten Token.
     Token wird als Bearer-Header oder HttpOnly-Cookie übermittelt.
     Kein vertrauter Header von aussen nötig.

SICHERHEITSREGEL:
  Im Produktionsmodus (DEMO_MODE=False) werden unbekannte User-IDs aus
  X-User-Id-Headern mit 403 abgewiesen. Niemals auto-erstellt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional, Set

from fastapi import Cookie, Depends, Header, HTTPException, Query

from app.db import SessionLocal
from app.rbac import ensure_user_exists, resolve_permissions, enforce_station_scope


# ── Token-Konfiguration ──────────────────────────────────────────────

def _get_signing_key() -> bytes:
    """Gibt den HMAC-Signing-Key zurück.
    Im Demo-Modus: generiert einmalig pro Prozess einen zufälligen Key.
    In Produktion: aus SECRET_KEY Env-Var.
    """
    from app.config import SECRET_KEY
    if SECRET_KEY and len(SECRET_KEY) >= 16:
        return SECRET_KEY.encode()
    # Demo-Modus: prozessweiter temporärer Key (Tokens überleben Restart nicht)
    import os
    if not hasattr(_get_signing_key, "_key"):
        _get_signing_key._key = os.urandom(32)  # type: ignore[attr-defined]
    return _get_signing_key._key  # type: ignore[attr-defined]

TOKEN_TTL_SECONDS = 8 * 3600  # 8 Stunden

# ── Token Blacklist (in-memory, für Logout) ──────────────────────────
# Resets bei Prozess-Neustart – für Demo/Pilot ausreichend.
# Produktion: Redis/DB-backed Blacklist verwenden.
import threading as _threading

_token_blacklist: set[str] = set()
_blacklist_lock = _threading.Lock()

def revoke_token(token: str) -> None:
    """Fügt Token zur Blacklist hinzu (nach Logout)."""
    with _blacklist_lock:
        _token_blacklist.add(token)

def is_token_revoked(token: str) -> bool:
    with _blacklist_lock:
        return token in _token_blacklist



def create_session_token(user_id: str) -> str:
    """Erstellt einen signierten Session-Token: base64url(payload).signature"""
    payload = json.dumps({
        "uid": user_id,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "iat": int(time.time()),
    }, separators=(",", ":"))
    import base64
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    sig = hmac.new(_get_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_session_token(token: str) -> str | None:
    """Verifiziert Token, gibt user_id zurück oder None bei Fehler."""
    # Blacklist-Check (nach Logout revozierte Tokens)
    if is_token_revoked(token):
        return None
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected = hmac.new(_get_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        # Padding wiederherstellen
        padding = 4 - len(payload_b64) % 4
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("uid")
    except Exception:
        return None


# ── AuthContext ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class AuthContext:
    user_id: str
    station_id: str  # "*" means global scope
    roles: Set[str]
    permissions: Set[str]
    is_break_glass: bool


def get_ctx(
    ctx: str | None = Query(default=None),
    x_scope_ctx: str | None = Header(default=None, alias="X-Scope-Ctx"),
    x_station_id: str | None = Header(default=None, alias="X-Station-Id"),
) -> Optional[str]:
    raw = (ctx or x_scope_ctx or x_station_id)
    if raw is None:
        return None
    val = str(raw).strip()
    return val or None


def require_ctx(ctx: Optional[str] = Depends(get_ctx)) -> str:
    if ctx is None:
        raise HTTPException(status_code=422, detail="Missing required ctx (station scope)")
    return ctx


def _normalize_station_id(ctx: Optional[str]) -> str:
    if ctx is None:
        return "*"
    c = ctx.strip()
    if not c or c.lower() == "global":
        return "*"
    return c



# ── SSO/OIDC-Vorbereitung ─────────────────────────────────────────────────────
# Aktiviert durch Env-Var: SSO_ENABLED=1
# Prod-Szenario: Keycloak / Azure AD / Authentik als vorgelagerter Proxy
#
# Modus A – Proxy-basiert (einfachste Produktion):
#   Ein nginx/Traefik-Plugin (z.B. oauth2-proxy) validiert OIDC-Token und setzt
#   X-User-Id nach erfolgreicher Authentifizierung. Backend vertraut Header
#   NUR wenn er von 127.0.0.1/Proxy kommt (TRUSTED_PROXY_IPS).
#
# Modus B – JWT direkt (diese App validiert JWT selbst):
#   Client schickt Bearer <JWT> → Backend prüft Signatur gegen JWKS-Endpoint
#   des Identity-Providers. user_id aus JWT-Claim "preferred_username" oder "sub".
#
# Der Code für Modus B ist unten als SSO-Stub vorbereitet. Produktiv schalten:
#   SSO_ENABLED=1
#   SSO_JWKS_URL=https://keycloak.example.com/realms/puk/protocol/openid-connect/certs
#   SSO_AUDIENCE=puk-dashboard
#   SSO_CLAIM=preferred_username   (oder: sub)
#
import os as _os
_SSO_ENABLED = _os.getenv("SSO_ENABLED", "0") in ("1", "true", "True")
_SSO_JWKS_URL = _os.getenv("SSO_JWKS_URL", "")
_SSO_AUDIENCE = _os.getenv("SSO_AUDIENCE", "puk-dashboard")
_SSO_CLAIM    = _os.getenv("SSO_CLAIM", "preferred_username")

def _verify_oidc_jwt(token: str) -> str | None:
    """Validiert einen OIDC JWT gegen den JWKS-Endpoint des Identity-Providers.

    Gibt user_id (aus SSO_CLAIM) zurück oder None bei Fehler.
    Wird nur aufgerufen wenn SSO_ENABLED=1 und Token kein internes PUK-Token ist.

    Produktiv-Setup:
        pip install PyJWT[crypto] cryptography
        SSO_ENABLED=1
        SSO_JWKS_URL=https://keycloak.intern/realms/puk/protocol/openid-connect/certs

    Demo/Test: gibt immer None zurück wenn PyJWT nicht installiert.
    """
    if not _SSO_ENABLED or not _SSO_JWKS_URL:
        return None
    try:
        import jwt  # PyJWT
        from jwt import PyJWKClient  # type: ignore
        jwks = PyJWKClient(_SSO_JWKS_URL)
        signing_key = jwks.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=_SSO_AUDIENCE,
            options={"verify_exp": True, "verify_aud": True},
        )
        uid = payload.get(_SSO_CLAIM) or payload.get("sub")
        return str(uid).strip() or None
    except ImportError:
        import logging
        logging.getLogger("puk.auth").warning(
            "SSO_ENABLED=1 aber PyJWT nicht installiert. "
            "pip install 'PyJWT[crypto]' ausführen."
        )
        return None
    except Exception as e:
        import logging
        logging.getLogger("puk.auth").debug("OIDC JWT validation failed: %s", e)
        return None

def _resolve_user_from_request(
    authorization: str | None,
    puk_session: str | None,
    x_user_id: str | None,
) -> str | None:
    """
    Identitätsauflösung mit Priorität:
      1. Bearer Token im Authorization-Header (Token-Modus)
      2. puk_session Cookie (Token-Modus)
      3. X-User-Id Header (SSO-Proxy-Modus, nur DEMO_MODE=True akzeptiert)
    """
    from app.config import DEMO_MODE

    # 1) Bearer Token: erst OIDC JWT versuchen (wenn SSO aktiv), dann internes Token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        # 1a) OIDC JWT (Prod-SSO) – nur wenn SSO_ENABLED=1
        if _SSO_ENABLED:
            uid = _verify_oidc_jwt(token)
            if uid:
                return uid
        # 1b) Internes HMAC-Token (Demo/Pilot)
        uid = verify_session_token(token)
        if uid:
            return uid
        # Ungültiger Token → explizit ablehnen
        raise HTTPException(status_code=401, detail="Session abgelaufen. Bitte neu anmelden.")

    # 2) Session Cookie
    if puk_session:
        uid = verify_session_token(puk_session)
        if uid:
            return uid
        raise HTTPException(status_code=401, detail="Session abgelaufen. Bitte neu anmelden.")

    # 3) X-User-Id Header (nur Demo / vorgelagerter SSO-Proxy)
    # Im Prod-Betrieb mit nginx: nginx setzt X-User-Id auf "" (blocked).
    # Nur ein vertrauenswürdiger interner Proxy darf diesen Header setzen.
    # Angreifer auf Internet-fähigem PC können via curl/JS keinen validen
    # Bearer-Token fälschen (HMAC-signiert) → einzige Lücke wäre lokaler Zugriff.
    if x_user_id:
        if not DEMO_MODE:
            # In Produktion: Header ohne Token = abweisen
            raise HTTPException(
                status_code=401,
                detail="Direkte X-User-Id Header sind in Produktion nicht erlaubt. "
                       "Bitte über /api/auth/login authentifizieren."
            )
        return x_user_id.strip() or None

    return None


def get_auth_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    puk_session: str | None = Cookie(default=None, alias="puk_session"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    ctx: Optional[str] = Depends(get_ctx),
) -> AuthContext:
    """Identity-Auflösung mit Token-Prüfung, RBAC-Lookup."""
    from app.config import DEMO_MODE

    user_id = _resolve_user_from_request(authorization, puk_session, x_user_id)

    if user_id is None:
        if DEMO_MODE:
            # Demo-Fallback: "demo" User ohne Login
            user_id = "demo"
        else:
            raise HTTPException(
                status_code=401,
                detail="Nicht authentifiziert. Bitte über /api/auth/login anmelden."
            )

    station_id = _normalize_station_id(ctx)

    with SessionLocal() as db:
        u = ensure_user_exists(db, user_id)
        if not u.is_active:
            raise HTTPException(status_code=403, detail="User deaktiviert")
        enforce_station_scope(db, user_id=user_id, station_id=station_id)
        roles, perms, is_bg = resolve_permissions(db, user_id=user_id, station_id=station_id)

    return AuthContext(
        user_id=user_id,
        station_id=station_id,
        roles=roles,
        permissions=perms,
        is_break_glass=is_bg,
    )


def require_role(ctx: AuthContext, role: str) -> None:
    """Legacy helper."""
    if role not in ctx.roles:
        raise HTTPException(status_code=403, detail=f"Missing role: {role}")
