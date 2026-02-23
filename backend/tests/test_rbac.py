"""
RBAC-Basistests: Viewer/Clinician-Rechte.

Prueft dass:
  - Viewer Cases sehen aber nicht quittieren kann
  - Clinician quittieren kann
"""
import pytest

# Verwende session-scoped fixtures aus conftest statt eigener Clients
pytestmark = pytest.mark.rbac


def test_viewer_can_view_cases_but_cannot_ack(client, auth):
    """Auto-provisioned user (viewer) kann Cases sehen, aber nicht ACKen."""
    viewer_h = auth("someone")

    r = client.get("/api/cases?ctx=Station A1", headers=viewer_h)
    assert r.status_code == 200

    r2 = client.post(
        "/api/ack?ctx=Station A1",
        headers=viewer_h,
        json={"case_id": "CASE001", "ack_scope": "case", "scope_id": "*"},
    )
    assert r2.status_code == 403, f"Viewer sollte 403 bekommen, got {r2.status_code}: {r2.text}"


def test_clinician_can_ack(client, auth, first_case_id):
    """Seeded clinician (pflege1) kann quittieren."""
    clin_h = auth.clinician()

    r = client.post(
        "/api/ack?ctx=Station A1",
        headers=clin_h,
        json={"case_id": first_case_id, "ack_scope": "case", "scope_id": "*"},
    )
    assert r.status_code in (200, 201, 409), f"Clinician ACK failed: {r.status_code}: {r.text}"
