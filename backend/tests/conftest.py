"""
Shared Fixtures fuer die gesamte Test-Suite.

Architektur:
  - In-Memory SQLite DB (isoliert, kein Dateisystem-Konflikt)
  - TestClient mit persistenter Cookie-Session (CSRF)
  - Auth-Header-Factories fuer alle Rollen
  - DB-Reset zwischen Tests wo noetig (via fresh_db)

Konvention:
  - Fixtures die mit `_` beginnen sind intern
  - `client` ist der primaere TestClient (session-scoped fuer Performance)
  - `fresh_client` ist ein frischer Client pro Test (function-scoped)
"""
from __future__ import annotations

import os
import sys
import secrets
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# ── sys.path: Tests muessen sowohl aus backend/ als auch aus Root funktionieren
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Env MUSS vor App-Import gesetzt werden ──────────────────────────────
os.environ.setdefault("DASHBOARD_ALLOW_DEMO_AUTH", "1")
os.environ.setdefault("DASHBOARD_CSP_NONCE", "1")
os.environ.setdefault("SECRET_KEY", "")

from main import app  # noqa: E402 – nach env setup

# ---------------------------------------------------------------------------
# CSRF-Helper
# ---------------------------------------------------------------------------

_CSRF_COOKIE = "csrf_token"
_CSRF_HEADER = "X-CSRF-Token"


def _extract_csrf(client: TestClient) -> str:
    """Holt CSRF-Token via GET /health (setzt Cookie)."""
    r = client.get("/api/meta/me", headers={"X-User-Id": "demo"})
    cookie = client.cookies.get(_CSRF_COOKIE)
    if cookie:
        return cookie
    # Fallback: Token aus Set-Cookie Header parsen
    for h in r.headers.get_list("set-cookie"):
        if _CSRF_COOKIE in h:
            return h.split("=")[1].split(";")[0]
    # Wenn kein Cookie gesetzt: synthetischen Token erzeugen
    # (CSRF-Middleware setzt nur bei fehlendem Cookie)
    return "test-csrf-token"


# ---------------------------------------------------------------------------
# Session-scoped Client (einmalig, schnell)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client() -> TestClient:
    """TestClient mit persistenter Session. Startup wird einmalig ausgefuehrt."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def csrf_token(client: TestClient) -> str:
    """Valides CSRF-Token fuer die gesamte Test-Session."""
    return _extract_csrf(client)


# ---------------------------------------------------------------------------
# Auth-Header-Factories
# ---------------------------------------------------------------------------

class AuthHeaders:
    """Factory fuer authentifizierte + CSRF-geschuetzte Headers."""

    def __init__(self, client: TestClient, csrf: str):
        self._client = client
        self._csrf = csrf

    def __call__(
        self,
        user: str = "demo",
        station: str = "A1",
        *,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        h = {
            "X-User-Id": user,
            "X-Station-Id": station,
            "Content-Type": "application/json",
            _CSRF_HEADER: self._csrf,
        }
        if extra:
            h.update(extra)
        return h

    def admin(self, station: str = "A1") -> dict[str, str]:
        return self("admin", station)

    def clinician(self, station: str = "A1") -> dict[str, str]:
        return self("pflege1", station)

    def viewer(self, station: str = "A1") -> dict[str, str]:
        # NICHT "demo" — der hat in main.py zusaetzlich admin-Rolle!
        # "viewer_test" wird in Demo-Mode auto-provisioned als reiner Viewer.
        return self("viewer_test", station)

    def manager(self, station: str = "A1") -> dict[str, str]:
        return self("manager1", station)

    def unknown(self, station: str = "A1") -> dict[str, str]:
        """Unbekannter User (auto-provisioned als viewer in demo mode)."""
        return self(f"unknown_{secrets.token_hex(4)}", station)


@pytest.fixture(scope="session")
def auth(client: TestClient, csrf_token: str) -> AuthHeaders:
    """Auth-Header-Factory (session-scoped)."""
    return AuthHeaders(client, csrf_token)


# ---------------------------------------------------------------------------
# Convenience shortcuts
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_h(auth: AuthHeaders) -> dict[str, str]:
    return auth.admin()


@pytest.fixture(scope="session")
def clinician_h(auth: AuthHeaders) -> dict[str, str]:
    return auth.clinician()


@pytest.fixture(scope="session")
def viewer_h(auth: AuthHeaders) -> dict[str, str]:
    return auth.viewer()


# ---------------------------------------------------------------------------
# Function-scoped fresh client (fuer Tests die Isolation brauchen)
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_client() -> TestClient:
    """Frischer Client pro Test (eigene Cookie-Session)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Test-Data Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def station_cases(client: TestClient, admin_h: dict) -> list[dict[str, Any]]:
    """Alle Faelle auf Station A1 (gecacht fuer die Session)."""
    r = client.get("/api/cases?ctx=A1", headers=admin_h)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def first_case_id(station_cases: list[dict]) -> str:
    """Erste verfuegbare case_id auf A1."""
    assert len(station_cases) > 0, "Keine Demo-Faelle auf A1"
    return station_cases[0]["case_id"]


@pytest.fixture(scope="session")
def all_rule_ids(client: TestClient, admin_h: dict) -> list[str]:
    """Alle aktiven Rule-IDs aus der DB."""
    r = client.get("/api/meta/rules?ctx=A1", headers=admin_h)
    assert r.status_code == 200
    return [rule["rule_id"] for rule in r.json()["rules"]]


@pytest.fixture(scope="session")
def shift_codes(client: TestClient, admin_h: dict) -> list[str]:
    """Alle aktiven Shift-Codes."""
    r = client.get("/api/shift_reasons", headers=admin_h)
    assert r.status_code == 200
    return [reason["code"] for reason in r.json()["reasons"]]
