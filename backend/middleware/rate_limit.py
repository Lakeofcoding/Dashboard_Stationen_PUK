"""
Rate-Limiting Middleware (In-Memory, Single Worker).

Schützt vor:
  - Brute-Force-Angriffen
  - Überlastung durch fehlerhafte Clients
  - Einfache DoS

Limitiert Requests pro Client (IP oder User-ID) auf konfigurierbare
Werte pro Minute und pro Stunde.

Hinweis: Funktioniert nur mit 1 Worker (SQLite-Betrieb).
Für Multi-Worker (PostgreSQL) auf Redis-basiertes Limiting umstellen.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Pfade die nicht limitiert werden (Health-Checks, Docs)
_EXEMPT_PATHS = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class RateLimitMiddleware(BaseHTTPMiddleware):

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        requests_per_hour: int = 3000,
    ):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.rph = requests_per_hour
        self._minute: dict[str, list[float]] = defaultdict(list)
        self._hour: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _client_id(self, request: Request) -> str:
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return f"u:{user_id}"
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _cleanup(self):
        """Entfernt abgelaufene Einträge (maximal 1x pro Minute)."""
        now = time.time()
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        cutoff_min = now - 60
        cutoff_hr = now - 3600
        for cid in list(self._minute.keys()):
            self._minute[cid] = [t for t in self._minute[cid] if t > cutoff_min]
            if not self._minute[cid]:
                del self._minute[cid]
        for cid in list(self._hour.keys()):
            self._hour[cid] = [t for t in self._hour[cid] if t > cutoff_hr]
            if not self._hour[cid]:
                del self._hour[cid]

    def _check(self, cid: str, bucket: dict, limit: int, window: int) -> int:
        """Prüft Limit. Returns remaining count, or -1 if exceeded."""
        now = time.time()
        cutoff = now - window
        entries = [t for t in bucket.get(cid, []) if t > cutoff]
        bucket[cid] = entries
        if len(entries) >= limit:
            return -1
        bucket[cid].append(now)
        return limit - len(entries) - 1

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)

        self._cleanup()
        cid = self._client_id(request)

        min_remaining = self._check(cid, self._minute, self.rpm, 60)
        if min_remaining < 0:
            raise HTTPException(
                status_code=429,
                detail=f"Rate Limit: max. {self.rpm} Requests/Minute",
                headers={"Retry-After": "60"},
            )

        hr_remaining = self._check(cid, self._hour, self.rph, 3600)
        if hr_remaining < 0:
            raise HTTPException(
                status_code=429,
                detail=f"Rate Limit: max. {self.rph} Requests/Stunde",
                headers={"Retry-After": "300"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(min(min_remaining, hr_remaining))
        return response
