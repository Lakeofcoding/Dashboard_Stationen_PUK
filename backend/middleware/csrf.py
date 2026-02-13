"""
Datei: backend/middleware/csrf.py

Zweck:
- CSRF-Protection Middleware
- Token-Generierung und -Validierung
- Cookie-basiertes CSRF-Token-Management

Schützt vor Cross-Site Request Forgery Angriffen.
"""

from __future__ import annotations

import secrets
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF-Protection Middleware.
    
    Funktionsweise:
    1. Bei GET-Requests: Setze CSRF-Token-Cookie
    2. Bei POST/PUT/DELETE: Validiere CSRF-Token aus Header
    3. Bei Fehler: 403 Forbidden
    
    Token-Flow:
    - Frontend erhält Token via Cookie
    - Frontend sendet Token in X-CSRF-Token Header
    - Backend validiert Token
    """
    
    def __init__(
        self,
        app,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        exempt_paths: list[str] | None = None,
        secret_key: str | None = None,
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.exempt_paths = exempt_paths or [
            "/api/health",
            "/api/health/ready",
            "/api/health/alive",
            "/api/health/detailed",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        self.secret_key = secret_key or secrets.token_hex(32)
    
    def _is_exempt(self, path: str) -> bool:
        """Prüft ob Pfad von CSRF-Check ausgenommen ist."""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    def _generate_token(self) -> str:
        """Generiert ein neues CSRF-Token."""
        return secrets.token_urlsafe(32)
    
    def _get_token_from_cookie(self, request: Request) -> str | None:
        """Holt CSRF-Token aus Cookie."""
        return request.cookies.get(self.cookie_name)
    
    def _get_token_from_header(self, request: Request) -> str | None:
        """Holt CSRF-Token aus Header."""
        return request.headers.get(self.header_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Middleware-Handler.
        
        - GET: Setze Token-Cookie falls nicht vorhanden
        - POST/PUT/DELETE: Validiere Token
        """
        # Exempt paths überspringen
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        method = request.method.upper()
        
        # GET-Requests: Token setzen
        if method in ["GET", "HEAD", "OPTIONS"]:
            response = await call_next(request)
            
            # Token-Cookie setzen falls nicht vorhanden
            if not self._get_token_from_cookie(request):
                token = self._generate_token()
                response.set_cookie(
                    key=self.cookie_name,
                    value=token,
                    httponly=True,
                    samesite="strict",
                    secure=False,  # In Produktion auf True setzen (HTTPS)
                    max_age=86400,  # 24 Stunden
                )
            
            return response
        
        # POST/PUT/DELETE/PATCH: Token validieren
        if method in ["POST", "PUT", "DELETE", "PATCH"]:
            cookie_token = self._get_token_from_cookie(request)
            header_token = self._get_token_from_header(request)
            
            # Token muss in beiden vorhanden sein
            if not cookie_token:
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing in cookie"
                )
            
            if not header_token:
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token missing in header"
                )
            
            # Tokens müssen übereinstimmen
            if not secrets.compare_digest(cookie_token, header_token):
                raise HTTPException(
                    status_code=403,
                    detail="CSRF token mismatch"
                )
        
        return await call_next(request)


def get_csrf_token(request: Request) -> str | None:
    """
    Helper-Funktion um CSRF-Token aus Request zu extrahieren.
    
    Kann in Endpoints verwendet werden um Token an Frontend zu senden.
    """
    return request.cookies.get("csrf_token")
