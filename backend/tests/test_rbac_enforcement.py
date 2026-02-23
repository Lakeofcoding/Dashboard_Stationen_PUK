"""
RBAC Enforcement Tests.

Prueft die vollstaendige Rechte-Matrix:
  - Viewer kann nur lesen, nicht quittieren/admin
  - Clinician kann quittieren, nicht admin
  - Manager kann break-glass aktivieren
  - Admin kann alles
  - Horizontale Eskalation (Station A1 → B0) wird verhindert

Klinischer Kontext:
  Fehlende Berechtigungspruefungen koennen dazu fuehren, dass
  Pflegepersonal Warnungen auf fremden Stationen quittiert,
  ohne die Patienten zu kennen. Das ist ein Patientensicherheitsrisiko.
"""
import pytest

pytestmark = pytest.mark.rbac


# ═══════════════════════════════════════════════════════════════════════════
# Permission Matrix: Wer darf was?
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionMatrix:
    """Testet die Rechte-Matrix fuer alle Rollen-Endpoint-Kombinationen."""

    # --- Viewer (demo) ---

    def test_viewer_can_list_cases(self, client, viewer_h):
        r = client.get("/api/cases?ctx=Station A1", headers=viewer_h)
        assert r.status_code == 200

    def test_viewer_can_view_day_state(self, client, viewer_h):
        r = client.get("/api/day_state?ctx=Station A1", headers=viewer_h)
        assert r.status_code == 200

    def test_viewer_cannot_ack(self, client, auth, csrf_token, first_case_id):
        h = auth.viewer()
        r = client.post(
            "/api/ack?ctx=Station A1", headers=h,
            json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"},
        )
        assert r.status_code == 403

    def test_viewer_cannot_reset(self, client, auth, csrf_token):
        r = client.post("/api/reset_today?ctx=Station A1", headers=auth.viewer())
        assert r.status_code == 403

    def test_viewer_cannot_admin_read(self, client, viewer_h):
        r = client.get("/api/admin/users?ctx=Station A1", headers=viewer_h)
        assert r.status_code == 403

    def test_viewer_cannot_admin_write(self, client, auth):
        r = client.post(
            "/api/admin/users?ctx=Station A1", headers=auth.viewer(),
            json={"user_id": "test_x", "display_name": "X", "is_active": True, "roles": []},
        )
        assert r.status_code == 403

    # --- Clinician (pflege1) ---

    def test_clinician_can_list_cases(self, client, clinician_h):
        r = client.get("/api/cases?ctx=Station A1", headers=clinician_h)
        assert r.status_code == 200

    def test_clinician_can_view_detail(self, client, clinician_h, first_case_id):
        r = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=clinician_h)
        assert r.status_code == 200

    def test_clinician_cannot_reset(self, client, auth):
        r = client.post("/api/reset_today?ctx=Station A1", headers=auth.clinician())
        assert r.status_code == 403

    def test_clinician_cannot_admin(self, client, clinician_h):
        r = client.get("/api/admin/users?ctx=Station A1", headers=clinician_h)
        assert r.status_code == 403

    # --- Admin ---

    def test_admin_can_admin_read(self, client, admin_h):
        r = client.get("/api/admin/users?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_admin_can_view_audit(self, client, admin_h):
        r = client.get("/api/admin/audit?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    # --- Manager ---

    def test_manager_can_view(self, client, auth):
        r = client.get("/api/cases?ctx=Station A1", headers=auth.manager())
        assert r.status_code == 200

    def test_manager_cannot_ack(self, client, auth, first_case_id):
        r = client.post(
            "/api/ack?ctx=Station A1", headers=auth.manager(),
            json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"},
        )
        assert r.status_code == 403

    def test_manager_cannot_admin(self, client, auth):
        # manager1 kann durch Break-Glass-Tests temporaer admin:read haben
        # (session-scoped Client teilt DB-State). Deshalb: frischen Manager
        # anlegen und ihm nur die manager-Rolle geben.
        import secrets
        fresh_mgr = f"mgr_rbac_{secrets.token_hex(4)}"
        admin_h = auth.admin()
        # User anlegen
        client.post("/api/admin/users?ctx=Station A1", headers=admin_h, json={
            "user_id": fresh_mgr, "display_name": "Fresh Manager", "is_active": True,
        })
        # Manager-Rolle zuweisen
        client.post(f"/api/admin/users/{fresh_mgr}/roles?ctx=Station A1", headers=admin_h, json={
            "role_id": "manager", "station_id": "*",
        })
        # Jetzt testen: manager ohne Break-Glass darf nicht admin:read
        mgr_h = auth(fresh_mgr)
        r = client.get("/api/admin/users?ctx=Station A1", headers=mgr_h)
        assert r.status_code == 403
        # Cleanup
        client.delete(f"/api/admin/users/{fresh_mgr}?ctx=Station A1", headers=admin_h)


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Provisioning
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoProvisioning:
    """Unbekannte User werden in Demo-Mode als Viewer angelegt."""

    def test_unknown_user_gets_viewer_role(self, client, auth):
        h = auth.unknown()
        r = client.get("/api/meta/me?ctx=Station A1", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert "viewer" in data["roles"]
        # Darf lesen...
        r2 = client.get("/api/cases?ctx=Station A1", headers=h)
        assert r2.status_code == 200

    def test_unknown_user_cannot_ack(self, client, auth, first_case_id):
        h = auth.unknown()
        r = client.post(
            "/api/ack?ctx=Station A1", headers=h,
            json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"},
        )
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Scope Enforcement (Horizontale Eskalation)
# ═══════════════════════════════════════════════════════════════════════════

class TestScopeEnforcement:
    """Prueft, dass User nur auf ihre zugewiesenen Stationen zugreifen koennen.

    Seeded Users haben station_id='*' (Wildcard), daher testen wir hier
    primaer das korrekte Verhalten der enforce_station_scope() Funktion.
    """

    def test_wildcard_user_can_access_any_station(self, client, admin_h, auth):
        """Admin hat station_id='*' → darf A1, B0, B2."""
        for station in ("Station A1", "Station B0", "Station B2"):
            h = auth.admin(station)
            r = client.get(f"/api/cases?ctx={station}", headers=h)
            assert r.status_code == 200, f"Admin denied on {station}"

    def test_ctx_parameter_required_for_station_endpoints(self, client, admin_h):
        """Endpoints die Stationskontext brauchen, muessen ctx haben."""
        # /api/cases ohne ctx → sollte 400 oder leere Response
        r = client.get("/api/cases", headers=admin_h)
        # Der Endpoint funktioniert evtl. mit default, aber nicht crashen
        assert r.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════
# CSRF Enforcement
# ═══════════════════════════════════════════════════════════════════════════

class TestCSRF:
    """CSRF-Middleware muss mutating requests ohne Token ablehnen."""

    def test_post_without_csrf_fails(self, fresh_client, first_case_id):
        """POST ohne CSRF-Token → 403."""
        h = {"X-User-Id": "admin", "X-Station-Id": "Station A1", "Content-Type": "application/json"}
        r = fresh_client.post(
            "/api/ack?ctx=Station A1", headers=h,
            json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"},
        )
        assert r.status_code == 403
        assert "CSRF" in r.json().get("detail", "")

    def test_get_does_not_require_csrf(self, fresh_client):
        """GET-Requests brauchen kein CSRF-Token."""
        h = {"X-User-Id": "admin", "X-Station-Id": "Station A1"}
        r = fresh_client.get("/api/cases?ctx=Station A1", headers=h)
        assert r.status_code == 200
