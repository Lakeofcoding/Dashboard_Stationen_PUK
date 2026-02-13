"""
Datei: backend/middleware/rate_limit.py

Zweck:
- Rate-Limiting Middleware
- Schutz vor Brute-Force und DoS
- In-Memory Rate-Limiter

Limitiert Anzahl Requests pro IP/User.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate-Limiting Middleware.
    
    Funktionsweise:
    - Trackt Requests pro Client (IP oder User-ID)
    - Limitiert auf X Requests pro Zeitfenster
    - Bei Überschreitung: 429 Too Many Requests
    
    Konfigurierbar:
    - requests_per_minute: Max. Requests pro Minute
    - requests_per_hour: Max. Requests pro Stunde
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.exempt_paths = exempt_paths or [
            "/api/health",
            "/docs",
            "/openapi.json",
        ]
        
        # In-Memory Storage (für Produktion: Redis verwenden!)
        self._minute_buckets = defaultdict(list)
        self._hour_buckets = defaultdict(list)
    
    def _is_exempt(self, path: str) -> bool:
        """Prüft ob Pfad von Rate-Limiting ausgenommen ist."""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    def _get_client_id(self, request: Request) -> str:
        """
        Ermittelt Client-Identifier.
        
        Priorität:
        1. User-ID aus Header (falls authentifiziert)
        2. IP-Adresse
        """
        # User-ID aus Header (falls vorhanden)
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return f"user:{user_id}"
        
        # IP-Adresse als Fallback
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _cleanup_old_entries(self, bucket: dict, window_seconds: int):
        """Entfernt alte Einträge aus Bucket."""
        now = time.time()
        cutoff = now - window_seconds
        
        for client_id in list(bucket.keys()):
            bucket[client_id] = [
                ts for ts in bucket[client_id]
                if ts > cutoff
            ]
            # Lösche leere Buckets
            if not bucket[client_id]:
                del bucket[client_id]
    
    def _check_rate_limit(
        self,
        client_id: str,
        bucket: dict,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """
        Prüft ob Rate-Limit überschritten ist.
        
        Returns:
            True wenn erlaubt, False wenn limitiert
        """
        now = time.time()
        
        # Cleanup alte Einträge
        self._cleanup_old_entries(bucket, window_seconds)
        
        # Zähle Requests im Zeitfenster
        requests = bucket.get(client_id, [])
        
        if len(requests) >= limit:
            return False
        
        # Request hinzufügen
        bucket[client_id].append(now)
        return True
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Middleware-Handler.
        
        - Prüft Rate-Limits
        - Bei Überschreitung: 429 Too Many Requests
        """
        # Exempt paths überspringen
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        
        # Prüfe Minuten-Limit
        if not self._check_rate_limit(
            client_id,
            self._minute_buckets,
            self.requests_per_minute,
            60
        ):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                headers={"Retry-After": "60"}
            )
        
        # Prüfe Stunden-Limit
        if not self._check_rate_limit(
            client_id,
            self._hour_buckets,
            self.requests_per_hour,
            3600
        ):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour",
                headers={"Retry-After": "3600"}
            )
        
        response = await call_next(request)
        
        # Rate-Limit-Headers hinzufügen (informativ)
        minute_remaining = self.requests_per_minute - len(
            self._minute_buckets.get(client_id, [])
        )
        hour_remaining = self.requests_per_hour - len(
            self._hour_buckets.get(client_id, [])
        )
        
        response.headers["X-RateLimit-Minute-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Minute-Remaining"] = str(max(0, minute_remaining))
        response.headers["X-RateLimit-Hour-Limit"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Hour-Remaining"] = str(max(0, hour_remaining))
        
        return response


# =============================================================================
# Redis-basiertes Rate-Limiting (für Produktion)
# =============================================================================

class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-basiertes Rate-Limiting.
    
    Vorteile:
    - Persistent über Server-Restarts
    - Funktioniert mit mehreren Worker-Prozessen
    - Automatisches Cleanup (TTL)
    
    Requires:
        pip install redis
    """
    
    def __init__(
        self,
        app,
        redis_url: str = "redis://localhost:6379",
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        super().__init__(app)
        
        try:
            import redis
            self.redis = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            raise ImportError("redis package required for RedisRateLimitMiddleware")
        
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Redis-basiertes Rate-Limiting."""
        # TODO: Implementierung mit Redis INCR und EXPIRE
        # Siehe: https://redis.io/commands/incr/
        return await call_next(request)
