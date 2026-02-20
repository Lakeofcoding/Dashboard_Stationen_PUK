"""
Security Headers & CSP Nonce Tests.

Prueft:
  - Content-Security-Policy Header vorhanden und korrekt
  - Nonce in CSP (wenn aktiviert)
  - X-Frame-Options: DENY (Clickjacking)
  - X-Content-Type-Options: nosniff
  - Cache-Control auf API-Responses (keine Patient-Daten im Cache)
  - Referrer-Policy
  - Permissions-Policy

Klinischer Kontext:
  Fehlende Security-Headers koennen dazu fuehren, dass Patientendaten
  im Browser-Cache landen oder per Clickjacking exfiltriert werden.
"""
import pytest

pytestmark = pytest.mark.security


class TestSecurityHeaders:
    """Alle Responses muessen Security-Headers haben."""

    def test_csp_present(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        csp = r.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    def test_csp_script_nonce(self, client, admin_h):
        """CSP sollte nonce-basiertes script-src haben (kein unsafe-inline)."""
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        csp = r.headers.get("content-security-policy", "")
        # Wenn Nonce aktiviert: 'nonce-...' statt 'unsafe-inline'
        if "nonce-" in csp:
            assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
        # Style-src darf unsafe-inline haben (React Inline-Styles)
        assert "style-src" in csp

    def test_x_frame_options(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        assert r.headers.get("x-frame-options", "").upper() == "DENY"

    def test_x_content_type_options(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        assert "strict-origin" in r.headers.get("referrer-policy", "")

    def test_permissions_policy(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        pp = r.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp


class TestAPICacheControl:
    """API-Responses duerfen NICHT gecacht werden (Patientendaten)."""

    def test_api_no_cache(self, client, admin_h):
        r = client.get("/api/cases?ctx=A1", headers=admin_h)
        cc = r.headers.get("cache-control", "")
        assert "no-store" in cc
        assert "private" in cc

    def test_health_no_cache_control(self, client):
        """Health-Endpoint ist kein API-Pfad → kein Cache-Control noetig."""
        r = client.get("/health")
        # Health braucht kein no-store (keine sensitiven Daten)
        assert r.status_code == 200


class TestCSPNoncePerRequest:
    """Jeder Request muss einen EIGENEN Nonce bekommen."""

    def test_different_nonces(self, client, admin_h):
        """Zwei aufeinanderfolgende Requests → verschiedene Nonces."""
        r1 = client.get("/api/cases?ctx=A1", headers=admin_h)
        r2 = client.get("/api/cases?ctx=A1", headers=admin_h)

        csp1 = r1.headers.get("content-security-policy", "")
        csp2 = r2.headers.get("content-security-policy", "")

        # Nonces extrahieren
        import re
        nonces1 = re.findall(r"nonce-([A-Za-z0-9_-]+)", csp1)
        nonces2 = re.findall(r"nonce-([A-Za-z0-9_-]+)", csp2)

        if nonces1 and nonces2:
            assert nonces1[0] != nonces2[0], "Nonces muessen pro Request einzigartig sein"
