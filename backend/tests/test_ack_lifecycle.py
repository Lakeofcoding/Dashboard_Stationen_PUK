"""
ACK/SHIFT/Reset Lifecycle Tests.

Testet den vollstaendigen klinischen Workflow:
  1. Alert wird angezeigt (unquittiert)
  2. Rule-Level ACK → Alert verschwindet
  3. Rule-Level SHIFT → Alert verschwindet, Shift-Code gespeichert
  4. Case-Level ACK → nur wenn alle Rules quittiert/geschoben
  5. Reset Today → alle Acks invalidiert, Alerts wieder sichtbar
  6. Condition-Hash-Change → Auto-Reopen

Klinischer Kontext:
  Die ACK-Logik ist das Herzstück des Dashboards. Ein Bug hier bedeutet:
  entweder werden kritische Warnungen nicht angezeigt (Patientengefährdung),
  oder sie lassen sich nicht quittieren (Workflow-Blockade).
"""
import pytest

pytestmark = pytest.mark.lifecycle


class TestRuleLevelAck:
    """Rule-Level Quittierung: Einzelne Warnung bestätigen."""

    def test_ack_active_rule(self, client, auth, first_case_id):
        """Aktive Regel quittieren → 200."""
        # Erst Detail holen um eine aktive Rule-ID zu finden
        h = auth.admin()
        detail = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=h)
        assert detail.status_code == 200
        alerts = detail.json().get("alerts", [])
        if not alerts:
            pytest.skip("Keine aktiven Alerts auf diesem Case")

        rule_id = alerts[0]["rule_id"]
        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": rule_id,
            "action": "ACK",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["acked"] is True
        assert data["condition_hash"] is not None

    def test_ack_inactive_rule_fails(self, client, auth, first_case_id):
        """Nicht-aktive Regel quittieren → 409."""
        h = auth.admin()
        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": "NONEXISTENT_RULE",
            "action": "ACK",
        })
        assert r.status_code == 409


class TestShift:
    """SHIFT: Warnung mit Begründung verschieben."""

    def test_shift_with_valid_code(self, client, auth, first_case_id, shift_codes):
        """SHIFT mit gueltigem Code → 200."""
        h = auth.admin()
        detail = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=h)
        alerts = detail.json().get("alerts", [])
        if not alerts:
            pytest.skip("Keine aktiven Alerts")

        rule_id = alerts[0]["rule_id"]
        code = shift_codes[0] if shift_codes else "a"
        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": rule_id,
            "action": "SHIFT",
            "shift_code": code,
        })
        assert r.status_code == 200

    def test_shift_without_code_fails(self, client, auth, first_case_id):
        """SHIFT ohne shift_code → 400."""
        h = auth.admin()
        detail = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=h)
        alerts = detail.json().get("alerts", [])
        if not alerts:
            pytest.skip("Keine aktiven Alerts")

        rule_id = alerts[0]["rule_id"]
        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": rule_id,
            "action": "SHIFT",
            "shift_code": None,
        })
        assert r.status_code == 400

    def test_shift_with_invalid_code_fails(self, client, auth, first_case_id):
        """SHIFT mit ungueltigem Code → 400."""
        h = auth.admin()
        detail = client.get(f"/api/cases/{first_case_id}?ctx=Station A1", headers=h)
        alerts = detail.json().get("alerts", [])
        if not alerts:
            pytest.skip("Keine aktiven Alerts")

        rule_id = alerts[0]["rule_id"]
        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": first_case_id,
            "ack_scope": "rule",
            "scope_id": rule_id,
            "action": "SHIFT",
            "shift_code": "INVALID_CODE_XYZ",
        })
        assert r.status_code == 400


class TestCaseLevelAck:
    """Case-Level ACK: Ganzen Fall quittieren (nur wenn alle Rules erledigt)."""

    def test_case_ack_with_open_rules_fails(self, client, auth):
        """Fall mit offenen Warnungen kann nicht komplett quittiert werden → 409."""
        h = auth.admin()
        cases = client.get("/api/cases?ctx=Station A1", headers=h).json()
        # Finde einen Case mit aktiven Alerts
        case_with_alerts = None
        for c in cases:
            if c.get("critical_count", 0) + c.get("warn_count", 0) > 0:
                case_with_alerts = c["case_id"]
                break
        if not case_with_alerts:
            pytest.skip("Kein Case mit offenen Alerts")

        r = client.post("/api/ack?ctx=Station A1", headers=h, json={
            "case_id": case_with_alerts,
            "ack_scope": "case",
            "scope_id": "*",
        })
        assert r.status_code == 409
        assert "open_rules" in str(r.json())


class TestResetToday:
    """Reset Today: Alle Acks der Station invalidieren."""

    def test_reset_increments_version(self, client, auth):
        """Reset inkrementiert die Tagesversion."""
        h = auth.admin()
        before = client.get("/api/day_state?ctx=Station A1", headers=h).json()
        v_before = before["version"]

        r = client.post("/api/reset_today?ctx=Station A1", headers=h)
        assert r.status_code == 200

        after = client.get("/api/day_state?ctx=Station A1", headers=h).json()
        assert after["version"] == v_before + 1


class TestAckValidation:
    """Input-Validierung fuer ACK-Requests."""

    def test_invalid_scope(self, client, auth, first_case_id):
        r = client.post("/api/ack?ctx=Station A1", headers=auth.admin(), json={
            "case_id": first_case_id,
            "ack_scope": "INVALID",
            "scope_id": "*",
        })
        assert r.status_code == 400

    def test_nonexistent_case(self, client, auth):
        r = client.post("/api/ack?ctx=Station A1", headers=auth.admin(), json={
            "case_id": "CASE_DOES_NOT_EXIST",
            "ack_scope": "case",
            "scope_id": "*",
        })
        assert r.status_code == 404
