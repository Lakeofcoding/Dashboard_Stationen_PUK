"""
CSRF-Protection Middleware (Double Submit Cookie Pattern).

Funktionsweise:
  1. GET-Request: Backend setzt CSRF-Token als Cookie (httpOnly=False,
     damit JavaScript es lesen kann).
  2. POST/PUT/DELETE: Frontend muss das Token im X-CSRF-Token Header
     mitsenden. Backend prüft ob Cookie-Token == Header-Token.

Dieses Pattern schützt zuverlässig vor CSRF, weil ein Angreifer von einer
fremden Domain den Cookie-Wert nicht lesen kann (Same-Origin-Policy).
"""

from __future__ import annotations

import os
import secrets
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

_SECURE_COOKIES = os.getenv("DASHBOARD_SECURE_COOKIES", "0") in ("1", "true", "True")

# Pfade die keinen CSRF-Check brauchen (read-only oder Health)
_EXEMPT_PATHS = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class CSRFMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, cookie_name: str = "csrf_token", header_name: str = "X-CSRF-Token"):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Exempt paths überspringen
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)

        method = request.method.upper()

        # ------- Safe Methods: Token-Cookie setzen -------
        if method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            # Token setzen falls noch keins da ist
            if self.cookie_name not in request.cookies:
                token = secrets.token_urlsafe(32)
                response.set_cookie(
                    key=self.cookie_name,
                    value=token,
                    httponly=False,       # Frontend MUSS es lesen können!
                    samesite="strict",
                    secure=_SECURE_COOKIES,
                    max_age=86400,
                    path="/",
                )
            return response

        # ------- Mutating Methods: Token validieren -------
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        if not cookie_token or not header_token:
            raise HTTPException(
                status_code=403,
                detail="CSRF-Token fehlt. Bitte Seite neu laden.",
            )

        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(
                status_code=403,
                detail="CSRF-Token ungültig. Bitte Seite neu laden.",
            )

        return await call_next(request)
