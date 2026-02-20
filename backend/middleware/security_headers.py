"""
Security Headers Middleware (Pure ASGI) mit Nonce-basierter CSP.

Architektur:
  1. Pro Request wird ein kryptographischer Nonce generiert (16 Bytes, base64).
  2. Der Nonce wird im ASGI-Scope gespeichert (scope["state"]["csp_nonce"]),
     damit nachgelagerte Endpoints ihn lesen können (z.B. HTML-Serving).
  3. Der CSP-Header verwendet 'nonce-...' statt 'unsafe-inline' fuer script-src.
  4. style-src bleibt bei 'unsafe-inline' (React Inline-Styles sind architektonisch
     inkompatibel mit Style-Nonces).

Klinischer Kontext (Datenschutz):
  Patientendaten sind "besonders schuetzenswerte Personendaten" (Art. 5 lit. c nDSG).
  Nonce-CSP verhindert, dass injiziertes JavaScript auf diese Daten zugreifen kann,
  selbst wenn ein Angreifer HTML in die Seite injizieren konnte.
  Das ist eine technische Massnahme i.S.v. Art. 8 Abs. 1 nDSG.

Warum KEIN Style-Nonce:
  - React erzeugt Inline-Styles per JSX (style={{ ... }}).
  - CSS-Injection ermoeglicht keine Code-Execution.
  - OWASP stuft 'unsafe-inline' fuer Styles als akzeptabel ein,
    wenn script-src mit Nonce abgesichert ist.

Warum Pure ASGI (nicht BaseHTTPMiddleware):
  Starlette-Problem: >=3 gestackte BaseHTTPMiddleware-Layer
  koennen HTTPExceptions verschlucken und als 500 zurueckgeben.
"""
from __future__ import annotations

import os
import secrets
from typing import Any

_SECURE = os.getenv("DASHBOARD_SECURE_COOKIES", "0") in ("1", "true", "True")

# Feature-Flag: Nonce-CSP aktivieren (Standard: an)
# Kann mit DASHBOARD_CSP_NONCE=0 deaktiviert werden (z.B. fuer Debugging)
_NONCE_ENABLED = os.getenv("DASHBOARD_CSP_NONCE", "1") in ("1", "true", "True")

# ---------------------------------------------------------------------------
# Header-Definitionen
# ---------------------------------------------------------------------------

_COMMON_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy",
     b"camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=()"),
]

if _SECURE:
    _COMMON_HEADERS.append(
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
    )

_API_CACHE_HEADERS: list[tuple[bytes, bytes]] = [
    (b"cache-control", b"no-store, no-cache, must-revalidate, private"),
    (b"pragma", b"no-cache"),
]


def _build_csp(nonce: str | None) -> str:
    """Baut den CSP-Header. Mit Nonce wenn verfuegbar, sonst unsafe-inline."""
    if nonce and _NONCE_ENABLED:
        script_src = f"'self' 'nonce-{nonce}'"
    else:
        script_src = "'self' 'unsafe-inline'"

    # style-src bleibt bei unsafe-inline (React Inline-Styles)
    parts = [
        "default-src 'self'",
        f"script-src {script_src}",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
    return "; ".join(parts)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware — generiert Nonce, setzt Security-Headers."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Nonce generieren und im ASGI-Scope speichern
        nonce = secrets.token_urlsafe(16) if _NONCE_ENABLED else None
        scope.setdefault("state", {})["csp_nonce"] = nonce

        path: str = scope.get("path", "")
        is_api = path.startswith("/api/")

        # CSP fuer diesen Request bauen
        csp_value = _build_csp(nonce).encode()

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"content-security-policy", csp_value))
                headers.extend(_COMMON_HEADERS)
                if is_api:
                    headers.extend(_API_CACHE_HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
