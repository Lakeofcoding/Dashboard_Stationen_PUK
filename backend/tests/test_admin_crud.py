"""
Admin CRUD Tests: User, Role, Permission, Rule, ShiftReason, Notification.

Testet CREATE → READ → UPDATE → DELETE fuer jede Admin-Entitaet.
Prueft auch: Duplikat-Handling (409), Not-Found (404), Validierung (400/422).
"""
import pytest
import secrets

pytestmark = pytest.mark.admin

_SUFFIX = secrets.token_hex(4)


# ═══════════════════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestUserCRUD:
    _uid = f"test_user_{_SUFFIX}"

    def test_create_user(self, client, auth):
        r = client.post("/api/admin/users?ctx=A1", headers=auth.admin(), json={
            "user_id": self._uid,
            "display_name": "Test User",
            "is_active": True,
            "roles": [{"role_id": "viewer", "station_id": "*"}],
        })
        assert r.status_code == 200, r.text

    def test_create_duplicate_fails(self, client, auth):
        r = client.post("/api/admin/users?ctx=A1", headers=auth.admin(), json={
            "user_id": self._uid,
            "display_name": "Dupe",
            "is_active": True,
            "roles": [],
        })
        assert r.status_code == 409

    def test_read_user(self, client, admin_h):
        r = client.get("/api/admin/users?ctx=A1", headers=admin_h)
        assert r.status_code == 200
        users = r.json()["users"]
        assert any(u["user_id"] == self._uid for u in users)

    def test_update_user(self, client, auth):
        r = client.put(f"/api/admin/users/{self._uid}?ctx=A1", headers=auth.admin(), json={
            "display_name": "Updated Name",
            "is_active": False,
        })
        assert r.status_code == 200

    def test_delete_user(self, client, auth):
        r = client.delete(f"/api/admin/users/{self._uid}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Role CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestRoleCRUD:
    _rid = f"test_role_{_SUFFIX}"

    def test_create_role(self, client, auth):
        r = client.post("/api/admin/roles?ctx=A1", headers=auth.admin(), json={
            "role_id": self._rid,
            "description": "Test Role",
        })
        assert r.status_code == 200

    def test_update_role(self, client, auth):
        r = client.put(f"/api/admin/roles/{self._rid}?ctx=A1", headers=auth.admin(), json={
            "description": "Updated Description",
        })
        assert r.status_code == 200

    def test_set_role_permissions(self, client, auth):
        r = client.put(
            f"/api/admin/roles/{self._rid}/permissions?ctx=A1",
            headers=auth.admin(),
            json={"permissions": ["dashboard:view", "meta:read"]},
        )
        assert r.status_code == 200

    def test_delete_role(self, client, auth):
        r = client.delete(f"/api/admin/roles/{self._rid}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Permission CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionCRUD:
    _pid = f"test_perm_{_SUFFIX}"

    def test_create_permission(self, client, auth):
        r = client.post("/api/admin/permissions?ctx=A1", headers=auth.admin(), json={
            "perm_id": self._pid,
            "description": "Test Permission",
        })
        assert r.status_code == 200

    def test_update_permission(self, client, auth):
        r = client.put(f"/api/admin/permissions/{self._pid}?ctx=A1", headers=auth.admin(), json={
            "description": "Updated",
        })
        assert r.status_code == 200

    def test_delete_permission(self, client, auth):
        r = client.delete(f"/api/admin/permissions/{self._pid}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Rule CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestRuleCRUD:
    _rule_id = f"TEST_RULE_{_SUFFIX.upper()}"

    def test_create_rule(self, client, auth):
        r = client.put(f"/api/admin/rules/{self._rule_id}?ctx=A1", headers=auth.admin(), json={
            "rule_id": self._rule_id,
            "display_name": "Test Rule",
            "message": "Test message",
            "explanation": "Test explanation",
            "category": "completeness",
            "severity": "WARN",
            "metric": "honos_entry_total",
            "operator": "is_null",
            "value": True,
            "enabled": False,
        })
        assert r.status_code == 200

    def test_read_rule(self, client, admin_h):
        r = client.get("/api/admin/rules?ctx=A1", headers=admin_h)
        assert r.status_code == 200
        rules = r.json()["rules"]
        assert any(rule["rule_id"] == self._rule_id for rule in rules)

    def test_update_rule(self, client, auth):
        r = client.put(f"/api/admin/rules/{self._rule_id}?ctx=A1", headers=auth.admin(), json={
            "rule_id": self._rule_id,
            "display_name": "Updated Rule",
            "message": "Updated",
            "explanation": "Updated",
            "category": "medical",
            "severity": "CRITICAL",
            "metric": "honos_entry_total",
            "operator": "is_null",
            "value": True,
            "enabled": True,
        })
        assert r.status_code == 200

    def test_delete_rule(self, client, auth):
        r = client.delete(f"/api/admin/rules/{self._rule_id}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# ShiftReason CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestShiftReasonCRUD:
    """Testet den Endpoint der den urspruenglichen 500-Fehler hatte."""

    _code = f"t{_SUFFIX[:4]}"

    def test_create_shift_reason(self, client, auth):
        r = client.post("/api/admin/shift_reasons?ctx=A1", headers=auth.admin(), json={
            "code": self._code,
            "label": "Test-Grund",
            "description": "Automatisierter Test",
            "sort_order": 99,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "id" in data
        assert data["code"] == self._code

    def test_duplicate_code_fails(self, client, auth):
        r = client.post("/api/admin/shift_reasons?ctx=A1", headers=auth.admin(), json={
            "code": self._code,
            "label": "Duplikat",
        })
        assert r.status_code == 409

    def test_read_shift_reasons(self, client, admin_h):
        r = client.get("/api/admin/shift_reasons?ctx=A1", headers=admin_h)
        assert r.status_code == 200
        reasons = r.json()["reasons"]
        assert any(sr["code"] == self._code for sr in reasons)

    def test_update_shift_reason(self, client, auth):
        # Erst ID holen
        reasons = client.get("/api/admin/shift_reasons?ctx=A1", headers=auth.admin()).json()["reasons"]
        rid = next(r["id"] for r in reasons if r["code"] == self._code)
        r = client.put(f"/api/admin/shift_reasons/{rid}?ctx=A1", headers=auth.admin(), json={
            "label": "Updated Label",
            "is_active": False,
        })
        assert r.status_code == 200

    def test_delete_shift_reason(self, client, auth):
        reasons = client.get("/api/admin/shift_reasons?ctx=A1", headers=auth.admin()).json()["reasons"]
        rid = next(r["id"] for r in reasons if r["code"] == self._code)
        r = client.delete(f"/api/admin/shift_reasons/{rid}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# NotificationRule CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestNotificationRuleCRUD:
    """Testet den Endpoint der fehlende Imports hatte (Request, datetime, log_security_event)."""

    _rule_id: int | None = None

    def test_create_notification_rule(self, client, auth):
        r = client.post("/api/admin/notifications?ctx=A1", headers=auth.admin(), json={
            "name": f"Test Regel {_SUFFIX}",
            "email": "test@example.com",
            "station_id": "A1",
            "min_severity": "CRITICAL",
            "category": None,
            "delay_minutes": 30,
            "is_active": True,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        TestNotificationRuleCRUD._rule_id = r.json()["id"]

    def test_read_notifications(self, client, admin_h):
        r = client.get("/api/admin/notifications?ctx=A1", headers=admin_h)
        assert r.status_code == 200

    def test_update_notification_rule(self, client, auth):
        if self._rule_id is None:
            pytest.skip("Create failed")
        r = client.put(f"/api/admin/notifications/{self._rule_id}?ctx=A1", headers=auth.admin(), json={
            "is_active": False,
        })
        assert r.status_code == 200

    def test_delete_notification_rule(self, client, auth):
        if self._rule_id is None:
            pytest.skip("Create failed")
        r = client.delete(f"/api/admin/notifications/{self._rule_id}?ctx=A1", headers=auth.admin())
        assert r.status_code == 200

    def test_invalid_severity_rejected(self, client, auth):
        r = client.post("/api/admin/notifications?ctx=A1", headers=auth.admin(), json={
            "name": "Bad", "email": "x@y.com", "min_severity": "LOW",
            "delay_minutes": 0, "is_active": True,
        })
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# Role Assignment
# ═══════════════════════════════════════════════════════════════════════════

class TestRoleAssignment:
    _uid = f"role_test_{_SUFFIX}"

    def test_create_user_then_assign_role(self, client, auth):
        # Create user
        client.post("/api/admin/users?ctx=A1", headers=auth.admin(), json={
            "user_id": self._uid, "display_name": "Role Test", "is_active": True, "roles": [],
        })
        # Assign role
        r = client.post(f"/api/admin/users/{self._uid}/roles?ctx=A1", headers=auth.admin(), json={
            "role_id": "clinician", "station_id": "A1",
        })
        assert r.status_code == 200

    def test_remove_role(self, client, auth):
        r = client.delete(
            f"/api/admin/users/{self._uid}/roles/clinician/A1?ctx=A1",
            headers=auth.admin(),
        )
        assert r.status_code == 200

    def test_cleanup(self, client, auth):
        client.delete(f"/api/admin/users/{self._uid}?ctx=A1", headers=auth.admin())
