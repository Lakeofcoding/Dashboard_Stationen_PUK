"""
Smoke Tests: Jeder API-Endpoint wird einmal aufgerufen.

Zweck: Import-Fehler, Schema-Mismatches, fehlende Dependencies sofort erkennen.
Jeder Test prueft nur: kein 500, erwarteter Statuscode-Bereich.

Diese Tests haetten ALLE bisherigen Bugs gefunden:
  - _get_valid_shift_codes NameError → 500
  - notifications.py fehlende Imports → 500
  - overview.py fehlende DUMMY_CASES → 500
  - Schema-Mismatches → 422
"""
import pytest

pytestmark = pytest.mark.smoke


# ═══════════════════════════════════════════════════════════════════════════
# Health & Meta
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestMeta:
    def test_me(self, client, admin_h):
        r = client.get("/api/meta/me?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert "user_id" in data
        assert "roles" in data
        assert "permissions" in data

    def test_stations(self, client, admin_h):
        r = client.get("/api/meta/stations?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        assert "stations" in r.json()

    def test_users(self, client, admin_h):
        r = client.get("/api/meta/users?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_rules(self, client, admin_h):
        r = client.get("/api/meta/rules?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()["rules"]) >= 20


# ═══════════════════════════════════════════════════════════════════════════
# Cases & Day State
# ═══════════════════════════════════════════════════════════════════════════

class TestCasesSmoke:
    def test_list_cases(self, client, admin_h):
        r = client.get("/api/cases?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_case_detail(self, client, admin_h, first_case_id):
        r = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert data["case_id"] == first_case_id
        assert "alerts" in data

    def test_case_not_found(self, client, admin_h):
        r = client.get("/api/cases/NONEXISTENT?ctx=Station A1", headers=admin_h)
        assert r.status_code == 404

    def test_day_state(self, client, admin_h):
        r = client.get("/api/day_state?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert "business_date" in data

    def test_shift_reasons(self, client, admin_h):
        r = client.get("/api/shift_reasons", headers=admin_h)
        assert r.status_code == 200
        reasons = r.json()["reasons"]
        assert len(reasons) >= 3
        assert all("code" in r for r in reasons)


# ═══════════════════════════════════════════════════════════════════════════
# Overview
# ═══════════════════════════════════════════════════════════════════════════

class TestOverviewSmoke:
    def test_overview(self, client, admin_h):
        """Testet /api/overview — hatte fehlende DUMMY_CASES Import."""
        r = client.get("/api/overview?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "station_id" in data[0]
            assert "severity" in data[0]


# ═══════════════════════════════════════════════════════════════════════════
# Admin GET Endpoints (Read-only, alle muessen 200 liefern)
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminSmoke:
    def test_admin_users(self, client, admin_h):
        r = client.get("/api/admin/users?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        assert "users" in r.json()

    def test_admin_roles(self, client, admin_h):
        r = client.get("/api/admin/roles?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_permissions(self, client, admin_h):
        r = client.get("/api/admin/permissions?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_rules(self, client, admin_h):
        r = client.get("/api/admin/rules?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_audit(self, client, admin_h):
        r = client.get("/api/admin/audit?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_shift_reasons(self, client, admin_h):
        r = client.get("/api/admin/shift_reasons?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_notifications(self, client, admin_h):
        r = client.get("/api/admin/notifications?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_notifications_pending(self, client, admin_h):
        r = client.get("/api/admin/notifications/pending?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_break_glass(self, client, admin_h):
        r = client.get("/api/admin/break_glass?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_csv_sample(self, client, admin_h):
        r = client.get("/api/admin/csv/sample?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")

    def test_admin_cases_count(self, client, admin_h):
        r = client.get("/api/admin/cases/count?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Export Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestExportSmoke:
    def test_export_reports(self, client, admin_h):
        r = client.get("/api/export/reports?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_export_summary_daily(self, client, admin_h):
        r = client.get("/api/export/summary?frequency=daily&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_export_summary_weekly(self, client, admin_h):
        r = client.get("/api/export/summary?frequency=weekly&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Debug Endpoints
# ═══════════════════════════════════════════════════════════════════════════

class TestDebugSmoke:
    def test_debug_rules(self, client, admin_h):
        r = client.get("/api/debug/rules?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_debug_eval(self, client, admin_h, first_case_id):
        r = client.get(f"/api/debug/eval/{first_case_id}?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_debug_ack_events(self, client, admin_h):
        r = client.get("/api/debug/ack-events?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Kein 500 auf irgendeinem Endpoint (Regression Guard)
# ═══════════════════════════════════════════════════════════════════════════

class TestNo500:
    """Sicherheitsnetz: KEIN Endpoint darf 500 zurueckgeben.

    Deckt die Hauptkategorie bisheriger Bugs ab (fehlende Imports, NameErrors).
    """

    @pytest.mark.parametrize("path", [
        "/health",
        "/api/meta/me?ctx=Station A1",
        "/api/meta/stations?ctx=Station A1",
        "/api/meta/users?ctx=Station A1",
        "/api/meta/rules?ctx=Station A1",
        "/api/cases?ctx=Station A1",
        "/api/day_state?ctx=Station A1",
        "/api/shift_reasons",
        "/api/overview?ctx=Station A1",
        "/api/admin/users?ctx=Station A1",
        "/api/admin/roles?ctx=Station A1",
        "/api/admin/permissions?ctx=Station A1",
        "/api/admin/rules?ctx=Station A1",
        "/api/admin/audit?ctx=Station A1",
        "/api/admin/shift_reasons?ctx=Station A1",
        "/api/admin/notifications?ctx=Station A1",
        "/api/admin/notifications/pending?ctx=Station A1",
        "/api/admin/break_glass?ctx=Station A1",
        "/api/admin/csv/sample?ctx=Station A1",
        "/api/admin/cases/count?ctx=Station A1",
        "/api/export/reports?ctx=Station A1",
        "/api/export/summary?frequency=daily&ctx=Station A1",
        "/api/debug/rules?ctx=Station A1",
        "/api/debug/ack-events?ctx=Station A1",
    ])
    def test_get_no_500(self, client, admin_h, path):
        r = client.get(path, headers=admin_h)
        assert r.status_code != 500, f"500 on GET {path}: {r.text[:200]}"
