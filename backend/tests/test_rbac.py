
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def h(user: str, station: str = "ST01"):
    return {"X-User-Id": user, "X-Station-Id": station}

def test_viewer_can_view_cases_but_cannot_ack():
    # auto-provisioned user defaults to viewer
    r = client.get("/api/cases", headers=h("someone"))
    assert r.status_code == 200

    r2 = client.post("/api/ack", headers=h("someone"), json={"case_id":"CASE001","ack_scope":"case","scope_id":"*"})
    assert r2.status_code == 403

def test_clinician_can_ack():
    # seeded clinician: pflege1
    r = client.post("/api/ack", headers=h("pflege1"), json={"case_id":"CASE001","ack_scope":"case","scope_id":"*"})
    assert r.status_code == 200

def test_admin_can_list_users():
    r = client.get("/api/admin/users", headers=h("admin"))
    assert r.status_code == 200
    data = r.json()
    assert "users" in data
