"""
CSRF-Protection Middleware (Double Submit Cookie Pattern).

Funktionsweise:
  1. GET-Request: Backend setzt CSRF-Token als Cookie (httpOnly=False,
     damit JavaScript es lesen kann).
  2. POST/PUT/DELETE: Frontend muss das Token im X-CSRF-Token Header
     mitsenden. Backend prueft ob Cookie-Token == Header-Token.

Dieses Pattern schuetzt zuverlaessig vor CSRF, weil ein Angreifer von einer
fremden Domain den Cookie-Wert nicht lesen kann (Same-Origin-Policy).

HINWEIS: Bewusst als reines ASGI-Middleware implementiert (NICHT
BaseHTTPMiddleware), weil Starlettes BaseHTTPMiddleware auf Python 3.11+
Exceptions in ExceptionGroups wrappen kann, was FastAPIs HTTPException-Handler
bricht und 500 statt 403 liefert.
"""

from __future__ import annotations

import os
import secrets
from http.cookies import SimpleCookie
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_SECURE_COOKIES = os.getenv("DASHBOARD_SECURE_COOKIES", "0") in ("1", "true", "True")

# Pfade die keinen CSRF-Check brauchen (read-only oder Health)
_EXEMPT_PATHS = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware:
    """Pure ASGI CSRF middleware – kein BaseHTTPMiddleware, kein TaskGroup."""

    def __init__(
        self,
        app: ASGIApp,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
    ):
        self.app = app
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path
        method = request.method.upper()

        # Exempt paths -> direkt durchreichen
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        # -- Safe Methods: ggf. CSRF-Cookie setzen --
        if method in _SAFE_METHODS:
            need_cookie = self.cookie_name not in request.cookies

            if not need_cookie:
                # Cookie schon vorhanden -> einfach durchreichen
                await self.app(scope, receive, send)
                return

            # Cookie fehlt -> Token generieren und als Set-Cookie Header injizieren
            token = secrets.token_urlsafe(32)
            cookie = SimpleCookie()
            cookie[self.cookie_name] = token
            morsel = cookie[self.cookie_name]
            morsel["httponly"] = ""  # leer = False -> Frontend kann lesen
            morsel["samesite"] = "Strict"
            morsel["path"] = "/"
            morsel["max-age"] = "86400"
            if _SECURE_COOKIES:
                morsel["secure"] = True
            set_cookie_bytes = cookie[self.cookie_name].OutputString().encode("latin-1")

            async def inject_cookie(message: dict[str, Any]) -> None:
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"set-cookie", set_cookie_bytes))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, inject_cookie)
            return

        # -- Mutating Methods: CSRF-Token validieren --
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token:
            response = JSONResponse(
                status_code=403,
                content={"detail": "CSRF-Token fehlt. Bitte Seite neu laden."},
            )
            await response(scope, receive, send)
            return

        if not secrets.compare_digest(cookie_token, header_token):
            response = JSONResponse(
                status_code=403,
                content={"detail": "CSRF-Token ungueltig. Bitte Seite neu laden."},
            )
            await response(scope, receive, send)
            return

        # Token OK -> Request durchreichen
        await self.app(scope, receive, send)
