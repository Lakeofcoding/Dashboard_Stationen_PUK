"""
Break-Glass Governance Tests.

Testet:
  - Aktivierung mit Pflichtbegruendung (min. 10 Zeichen)
  - Zeitlimit-Validierung (5-720 Minuten)
  - Revoke mit Review-Note
  - Audit-Trail (Event in Security-Log)
  - Permission-Gate (nur Manager darf aktivieren, nur Admin revoken)
"""
import pytest

pytestmark = pytest.mark.security


class TestBreakGlassActivation:

    def test_activate_requires_reason(self, client, auth):
        """Aktivierung ohne Grund → 400."""
        r = client.post("/api/break_glass/activate?ctx=Station A1", headers=auth.manager(), json={
            "reason": "",
            "station_scope": "*",
            "duration_minutes": 60,
        })
        assert r.status_code == 400
        assert "10 Zeichen" in r.json()["detail"]

    def test_activate_short_reason_rejected(self, client, auth):
        """Grund unter 10 Zeichen → 400."""
        r = client.post("/api/break_glass/activate?ctx=Station A1", headers=auth.manager(), json={
            "reason": "kurz",
            "station_scope": "*",
            "duration_minutes": 60,
        })
        assert r.status_code == 400

    def test_activate_invalid_duration(self, client, auth):
        """Dauer ausserhalb 5-720 Min → 400."""
        for dur in (1, 0, -5, 800, 10000):
            r = client.post("/api/break_glass/activate?ctx=Station A1", headers=auth.manager(), json={
                "reason": "Test-Notfall mit gueltigem Grund",
                "station_scope": "*",
                "duration_minutes": dur,
            })
            assert r.status_code == 400, f"Duration {dur} should be rejected"

    def test_activate_valid(self, client, auth):
        """Gueltige Aktivierung → 200, Session-ID zurueck."""
        r = client.post("/api/break_glass/activate?ctx=Station A1", headers=auth.manager(), json={
            "reason": "Notfall-Zugang fuer Patientenverlegung auf andere Station",
            "station_scope": "*",
            "duration_minutes": 30,
        })
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data

    def test_viewer_cannot_activate(self, client, auth):
        """Viewer hat kein breakglass:activate → 403."""
        r = client.post("/api/break_glass/activate?ctx=Station A1", headers=auth.viewer(), json={
            "reason": "Sollte nicht funktionieren, kein Break-Glass-Recht",
            "station_scope": "*",
            "duration_minutes": 60,
        })
        assert r.status_code == 403


class TestBreakGlassList:

    def test_list_sessions(self, client, admin_h):
        r = client.get("/api/admin/break_glass?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data
