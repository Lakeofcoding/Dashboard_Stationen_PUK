"""
Response-Cache für Hot-Path-Endpoints.

PROBLEM:
  50 User × 2 Endpoints × alle 15s = ~400 schwere Requests/Minute.
  Jeder Request: N+1 DB-Queries + 46 Regeln × 100 Fälle = ~4600 Evaluationen.

LÖSUNG:
  TTL-basierter Cache: Berechnung 1x, alle User bekommen dasselbe Ergebnis
  für ~10 Sekunden. Danach wird frisch berechnet.

  Cache-Keys berücksichtigen RBAC (visible_stations), damit User nur
  ihre erlaubten Daten sehen.

INVALIDIERUNG:
  - TTL-basiert (Standard: 10s)
  - Explizit via invalidate() bei Schreiboperationen (ACK, Admin-Änderungen)

THREAD-SAFETY:
  Lock-basiert. Ein Thread berechnet, alle anderen warten max. kurz
  und bekommen das gecachte Ergebnis.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable


class _CacheEntry:
    __slots__ = ("value", "ts", "etag")

    def __init__(self, value: Any, ts: float, etag: str):
        self.value = value
        self.ts = ts
        self.etag = etag


class ResponseCache:
    """Thread-safe TTL cache für API-Responses."""

    def __init__(self, default_ttl: float = 10.0):
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._computing: dict[str, threading.Event] = {}

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: float | None = None,
    ) -> tuple[Any, str]:
        """Cache-Lookup oder frische Berechnung.

        Returns: (result, etag)

        Wenn mehrere Threads gleichzeitig denselben Key anfragen,
        berechnet nur einer – die anderen warten auf das Ergebnis.
        """
        ttl = ttl or self._default_ttl
        now = time.time()

        # Fast path: gültiger Cache-Eintrag
        with self._lock:
            entry = self._store.get(key)
            if entry and (now - entry.ts) < ttl:
                return entry.value, entry.etag

            # Prüfen ob ein anderer Thread gerade berechnet
            event = self._computing.get(key)
            if event:
                # Warten bis der andere Thread fertig ist
                pass
            else:
                # Wir berechnen
                event = threading.Event()
                self._computing[key] = event

        # Wenn ein anderer Thread berechnet: kurz warten
        if key in self._computing and self._computing[key] is not event:
            self._computing[key].wait(timeout=5.0)
            with self._lock:
                entry = self._store.get(key)
                if entry and (now - entry.ts) < ttl:
                    return entry.value, entry.etag

        # Berechnung durchführen
        try:
            result = compute_fn()
            etag = _compute_etag(result)

            with self._lock:
                self._store[key] = _CacheEntry(result, time.time(), etag)
                if key in self._computing:
                    self._computing[key].set()
                    del self._computing[key]

            return result, etag

        except Exception:
            with self._lock:
                if key in self._computing:
                    self._computing[key].set()
                    del self._computing[key]
            raise

    def invalidate(self, prefix: str = "") -> int:
        """Löscht Cache-Einträge (alle oder nach Prefix).

        Returns: Anzahl gelöschter Einträge.
        """
        with self._lock:
            if not prefix:
                n = len(self._store)
                self._store.clear()
                return n
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def check_etag(self, key: str, client_etag: str | None) -> bool:
        """True wenn Client-ETag mit Cache-ETag übereinstimmt (= 304)."""
        if not client_etag:
            return False
        with self._lock:
            entry = self._store.get(key)
            if entry and entry.etag == client_etag:
                return True
        return False


def _compute_etag(data: Any) -> str:
    """Schneller ETag aus JSON-Hash."""
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ── Globale Instanz ──────────────────────────────────────────────────
cache = ResponseCache(default_ttl=10.0)
