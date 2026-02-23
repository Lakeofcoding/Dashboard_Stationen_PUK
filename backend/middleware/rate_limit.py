"""
Rate-Limiting Middleware (In-Memory, Single Worker).

Schuetzt vor Brute-Force, Ueberlastung, einfache DoS.
Limitiert Requests pro Client (IP oder User-ID).

Pure ASGI (nicht BaseHTTPMiddleware) wegen Python 3.11+ ExceptionGroup-Bug.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_EXEMPT_PATHS = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class RateLimitMiddleware:
    """Pure ASGI rate limiter – kein BaseHTTPMiddleware."""

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 120,
        requests_per_hour: int = 3000,
    ):
        self.app = app
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

    def _cleanup(self) -> None:
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
        now = time.time()
        cutoff = now - window
        entries = [t for t in bucket.get(cid, []) if t > cutoff]
        bucket[cid] = entries
        if len(entries) >= limit:
            return -1
        bucket[cid].append(now)
        return limit - len(entries) - 1

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            await self.app(scope, receive, send)
            return

        self._cleanup()
        cid = self._client_id(request)

        min_remaining = self._check(cid, self._minute, self.rpm, 60)
        if min_remaining < 0:
            resp = JSONResponse(
                status_code=429,
                content={"detail": f"Rate Limit: max. {self.rpm} Requests/Minute"},
                headers={"Retry-After": "60"},
            )
            await resp(scope, receive, send)
            return

        hr_remaining = self._check(cid, self._hour, self.rph, 3600)
        if hr_remaining < 0:
            resp = JSONResponse(
                status_code=429,
                content={"detail": f"Rate Limit: max. {self.rph} Requests/Stunde"},
                headers={"Retry-After": "300"},
            )
            await resp(scope, receive, send)
            return

        remaining = str(min(min_remaining, hr_remaining))

        async def inject_rate_header(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-remaining", remaining.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, inject_rate_header)
