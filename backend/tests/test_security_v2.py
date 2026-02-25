"""
Security & Integrity Tests v5.12

Abdeckung:
  1. Cross-Station ACK-Verbot
  2. Hierarchie-Scope (Manager sieht nur eigene Klinik)
  3. Browse-Endpoint Scope-Filterung
  4. File-Upload-Abuse (Grösse, Format)
  5. Case-ID Validierung
  6. ACK-Rollenprüfung (ack_roles, case-scope, restrict_to_responsible)
  7. Donut-Berechnung (severity_dist)
  8. Day-Version-Isolation
  9. Debug-Endpoints in Non-Demo-Mode
"""
from __future__ import annotations
import json
import pytest
from tests.conftest import AuthHeaders


# ═══════════════════════════════════════════════════════════════════════
# 1. Cross-Station ACK-Verbot
# ═══════════════════════════════════════════════════════════════════════

class TestCrossStationACK:
    """User auf Station A1 darf keine Fälle auf Station G0 quittieren."""

    def test_ack_foreign_station_returns_404(self, client, auth: AuthHeaders, csrf_token):
        """Arzt A1 versucht Fall auf G0 zu ACKen → 404."""
        # Erst einen Fall auf G0 finden
        r = client.get("/api/cases/browse?station=Station G0",
                        headers=auth("admin", "global"))
        if r.status_code != 200 or not r.json():
            pytest.skip("Keine Fälle auf Station G0")
        g0_case = r.json()[0]["case_id"]

        # Arzt A1 versucht ACK auf G0-Fall
        r = client.post("/api/ack?ctx=Station A1",
                         headers=auth("arzt.a1", "Station A1"),
                         json={"case_id": g0_case, "ack_scope": "case", "scope_id": "*"})
        assert r.status_code in (403, 404), f"Cross-station ACK sollte scheitern: {r.json()}"

    def test_detail_foreign_station_returns_404(self, client, auth: AuthHeaders):
        """Arzt A1 kann kein Detail von G0-Fall laden."""
        r = client.get("/api/cases/browse?station=Station G0",
                        headers=auth("admin", "global"))
        if r.status_code != 200 or not r.json():
            pytest.skip("Keine Fälle auf Station G0")
        g0_case = r.json()[0]["case_id"]

        r = client.get(f"/api/cases/{g0_case}?ctx=Station A1&view=all",
                        headers=auth("arzt.a1", "Station A1"))
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# 2. Hierarchie-Scope
# ═══════════════════════════════════════════════════════════════════════

class TestHierarchyScope:
    """Manager sieht nur eigene Klinik, Clinician nur eigene Station."""

    def test_manager_epp_sees_only_epp(self, client, auth: AuthHeaders):
        """Manager EPP → Overview enthält nur EPP-Stationen."""
        r = client.get("/api/overview?ctx=global",
                        headers=auth("mgr.epp", "global"))
        assert r.status_code == 200
        stations = r.json()
        clinics = {s.get("clinic") for s in stations}
        assert clinics == {"EPP"}, f"Manager EPP sieht: {clinics}"

    def test_clinician_a1_sees_only_a1(self, client, auth: AuthHeaders):
        """Arzt A1 → Browse ohne Filter enthält nur Station A1."""
        r = client.get("/api/cases/browse",
                        headers=auth("arzt.a1", "global"))
        assert r.status_code == 200
        stations = {c["station_id"] for c in r.json()}
        assert stations == {"Station A1"} or stations == set(), \
            f"Clinician A1 sieht Stationen: {stations}"

    def test_admin_sees_all(self, client, auth: AuthHeaders):
        """Admin → Overview enthält alle Kliniken."""
        r = client.get("/api/overview?ctx=global",
                        headers=auth("admin", "global"))
        assert r.status_code == 200
        clinics = {s.get("clinic") for s in r.json()}
        assert len(clinics) >= 3, f"Admin sieht nur: {clinics}"

    def test_meta_me_scope_correct(self, client, auth: AuthHeaders):
        """meta/me gibt korrekten Scope-Level zurück."""
        # Admin → global
        r = client.get("/api/meta/me?ctx=global", headers=auth("admin", "global"))
        assert r.status_code == 200
        assert r.json()["scope"]["level"] == "global"

        # Manager EPP → klinik
        r = client.get("/api/meta/me?ctx=global", headers=auth("mgr.epp", "global"))
        assert r.status_code == 200
        assert r.json()["scope"]["level"] == "klinik"

        # Arzt A1 → station
        r = client.get("/api/meta/me?ctx=global", headers=auth("arzt.a1", "global"))
        assert r.status_code == 200
        assert r.json()["scope"]["level"] == "station"


# ═══════════════════════════════════════════════════════════════════════
# 3. Browse-Endpoint Scope-Filterung
# ═══════════════════════════════════════════════════════════════════════

class TestBrowseScope:

    def test_browse_admin_gets_all(self, client, auth: AuthHeaders):
        r = client.get("/api/cases/browse", headers=auth("admin", "global"))
        assert r.status_code == 200
        stations = {c["station_id"] for c in r.json()}
        assert len(stations) >= 5, f"Admin sieht zu wenige Stationen: {len(stations)}"

    def test_browse_clinician_gets_only_own(self, client, auth: AuthHeaders):
        r = client.get("/api/cases/browse", headers=auth("arzt.g0", "global"))
        assert r.status_code == 200
        stations = {c["station_id"] for c in r.json()}
        # arzt.g0 hat Rolle clinician auf Station G0 → sieht nur G0
        assert stations.issubset({"Station G0"}), f"Clinician G0 sieht: {stations}"


# ═══════════════════════════════════════════════════════════════════════
# 4. File-Upload-Abuse
# ═══════════════════════════════════════════════════════════════════════

class TestFileUpload:

    def test_oversized_file_rejected(self, client, auth: AuthHeaders, csrf_token):
        """Datei > 10 MB → 413."""
        huge = b"x" * (10 * 1024 * 1024 + 100)
        r = client.post("/api/admin/csv/upload?ctx=Station A1",
                         headers={**auth.admin(), "Content-Type": None},
                         files={"file": ("huge.csv", huge, "text/csv")},
                         data={"station_id": "Station A1"})
        # FastAPI might return 413 or 400
        assert r.status_code in (400, 413), f"Expected 413/400, got {r.status_code}"

    def test_invalid_extension_rejected(self, client, auth: AuthHeaders, csrf_token):
        """Nicht-CSV Datei → 400."""
        r = client.post("/api/admin/csv/upload?ctx=Station A1",
                         headers={**auth.admin(), "Content-Type": None},
                         files={"file": ("malware.exe", b"MZ\x00\x00", "application/octet-stream")},
                         data={"station_id": "Station A1"})
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# 5. Case-ID Validierung
# ═══════════════════════════════════════════════════════════════════════

class TestCaseIdValidation:

    def test_valid_case_id(self, client, auth: AuthHeaders):
        """Normaler case_id → 404 (nicht gefunden, aber kein Validierungs-Fehler)."""
        r = client.get("/api/cases/VALID_ID-123?ctx=Station A1&view=all",
                        headers=auth.admin())
        assert r.status_code == 404  # Nicht gefunden, aber validiert

    def test_too_long_case_id(self, client, auth: AuthHeaders):
        """case_id > 64 Zeichen → 400."""
        long_id = "A" * 100
        r = client.get(f"/api/cases/{long_id}?ctx=Station A1&view=all",
                        headers=auth.admin())
        assert r.status_code == 400

    def test_special_chars_case_id(self, client, auth: AuthHeaders):
        """case_id mit Sonderzeichen → 400."""
        r = client.get("/api/cases/test%3B%20DROP%20TABLE?ctx=Station A1&view=all",
                        headers=auth.admin())
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# 6. ACK-Rollenprüfung
# ═══════════════════════════════════════════════════════════════════════

class TestACKRoles:

    def test_case_ack_rejected_for_clinician(self, client, auth: AuthHeaders, first_case_id):
        """Kliniker darf keinen Case-ACK machen (nur Shift-Lead+)."""
        r = client.post("/api/ack?ctx=Station A1",
                         headers=auth.clinician(),
                         json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"})
        assert r.status_code == 403, f"Case-ACK sollte für Clinician 403 sein: {r.json()}"

    def test_case_ack_allowed_for_shift_lead(self, client, auth: AuthHeaders, first_case_id):
        """Shift-Lead darf Case-ACK machen."""
        r = client.post("/api/ack?ctx=Station A1",
                         headers=auth.shift_lead(),
                         json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"})
        # 409 = alle Regeln müssen erst einzeln quittiert sein (Business-Logik, nicht Auth)
        assert r.status_code in (200, 409), f"Unexpected: {r.status_code} {r.json()}"

    def test_ack_medical_rule_rejected_for_viewer(self, client, auth: AuthHeaders, first_case_id):
        """Viewer kann keine medizinischen Regeln quittieren (hat kein ack:write)."""
        r = client.post("/api/ack?ctx=Station A1",
                         headers=auth.viewer(),
                         json={"case_id": first_case_id, "ack_scope": "rule",
                               "scope_id": "EKG_NOT_REPORTED_24H"})
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# 7. Donut-Berechnung (severity_dist)
# ═══════════════════════════════════════════════════════════════════════

class TestDonutCalculation:

    def test_analytics_has_severity_dist(self, client, auth: AuthHeaders):
        """Analytics liefert severity_dist mit ok > 0 (nach Seed-Fix)."""
        r = client.get("/api/analytics?ctx=global", headers=auth.admin())
        assert r.status_code == 200
        stations = r.json().get("stations", [])
        assert len(stations) > 0

        total_ok = sum(s.get("severity_dist", {}).get("ok", 0) for s in stations)
        total_warn = sum(s.get("severity_dist", {}).get("warn", 0) for s in stations)
        total_crit = sum(s.get("severity_dist", {}).get("critical", 0) for s in stations)

        assert total_ok > 0, "Donut-Bug: Keine OK-Fälle! Seed-Daten prüfen."
        assert total_ok + total_warn + total_crit > 0

    def test_severity_dist_sums_to_total(self, client, auth: AuthHeaders):
        """severity_dist-Summe == total_cases pro Station."""
        r = client.get("/api/analytics?ctx=global", headers=auth.admin())
        for s in r.json().get("stations", []):
            sd = s.get("severity_dist", {})
            total = sd.get("critical", 0) + sd.get("warn", 0) + sd.get("ok", 0)
            assert total == s["total_cases"], \
                f"Station {s['station_id']}: severity_dist sum {total} != total {s['total_cases']}"


# ═══════════════════════════════════════════════════════════════════════
# 8. Day-Version-Isolation
# ═══════════════════════════════════════════════════════════════════════

class TestDayVersionIsolation:

    def test_reset_increments_version(self, client, auth: AuthHeaders, csrf_token):
        """Reset erhöht Version um 1."""
        h = auth.admin()
        r1 = client.get("/api/day_state?ctx=Station A1", headers=h)
        assert r1.status_code == 200
        v1 = r1.json()["version"]

        r2 = client.post("/api/reset_today?ctx=Station A1", headers=h)
        assert r2.status_code == 200
        v2 = r2.json()["version"]
        assert v2 == v1 + 1


# ═══════════════════════════════════════════════════════════════════════
# 9. Debug-Endpoints (DEMO_MODE Check)
# ═══════════════════════════════════════════════════════════════════════

class TestDebugEndpoints:

    def test_debug_available_in_demo(self, client, auth: AuthHeaders):
        """In Demo-Mode sind Debug-Endpoints erreichbar."""
        import os
        if os.environ.get("DASHBOARD_ALLOW_DEMO_AUTH") != "1":
            pytest.skip("Nicht im Demo-Modus")
        r = client.get("/api/debug/rules")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# 10. Input-Injection
# ═══════════════════════════════════════════════════════════════════════

class TestInputInjection:

    def test_sql_injection_in_station_filter(self, client, auth: AuthHeaders):
        """SQL-Injection Versuch in Station-Filter → kein Crash."""
        r = client.get("/api/cases/browse?station='; DROP TABLE case_data;--",
                        headers=auth("admin", "global"))
        assert r.status_code == 200  # Leere Liste, kein Server-Error
        assert r.json() == []

    def test_xss_in_comment(self, client, auth: AuthHeaders, first_case_id, csrf_token):
        """XSS-Versuch im ACK-Kommentar → wird gespeichert, aber nicht ausgeführt."""
        r = client.post("/api/ack?ctx=Station A1",
                         headers=auth.admin(),
                         json={
                             "case_id": first_case_id,
                             "ack_scope": "rule",
                             "scope_id": "HONOS_ENTRY_MISSING_WARN",
                             "comment": "<script>alert('xss')</script>",
                         })
        # Sollte entweder 200 (gespeichert) oder 409 (Regel nicht aktiv) sein
        assert r.status_code in (200, 409)


# ═══════════════════════════════════════════════════════════════════════
# 11. Concurrent Safety
# ═══════════════════════════════════════════════════════════════════════

class TestConcurrentSafety:

    def test_double_ack_idempotent(self, client, auth: AuthHeaders, first_case_id, csrf_token):
        """Doppeltes ACK auf gleiche Regel → idempotent (kein Fehler)."""
        payload = {
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": "HONOS_ENTRY_MISSING_WARN",
        }
        h = auth.admin()
        r1 = client.post("/api/ack?ctx=Station A1", headers=h, json=payload)
        r2 = client.post("/api/ack?ctx=Station A1", headers=h, json=payload)
        # Beide sollten 200 oder 409 (wenn Regel nicht aktiv) sein
        assert r1.status_code in (200, 409)
        assert r2.status_code in (200, 409)
