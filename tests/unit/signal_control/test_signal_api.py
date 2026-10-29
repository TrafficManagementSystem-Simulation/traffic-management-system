"""Signal control endpoints (Manoj): POST .../signal-command follows SAD section 4.3."""
from __future__ import annotations

from tms.common import clock

from tests.conftest import START

BASE = "/api/v1/intersections/INT-001"


def command(client, headers, **body):
    return client.post(f"{BASE}/signal-command", json=body, headers=headers)


def test_signal_state_needs_a_signed_in_user(client, analyst_h):
    assert client.get(f"{BASE}/signal-state").status_code == 401
    state = client.get(f"{BASE}/signal-state", headers=analyst_h)
    assert state.status_code == 200 and state.json()["phase"] == "NS"


def test_operator_overrides_and_returns_to_auto(client, operator_h):
    applied = command(client, operator_h, mode="manual", phase="EW", duration=30)
    assert applied.status_code == 200
    body = applied.json()
    assert body["status"] == "applied" and body["commandId"].startswith("CMD-") and body["appliedAt"]
    assert client.get(f"{BASE}/signal-state", headers=operator_h).json()["mode"] == "manual"

    back = command(client, operator_h, mode="auto")
    assert back.status_code == 200 and back.json()["mode"] == "adaptive"
    assert client.get(f"{BASE}/signal-state", headers=operator_h).json()["mode"] == "adaptive"


def test_TC_Adm_01_analyst_is_denied_the_override(client, analyst_h, admin_h):
    assert command(client, analyst_h, mode="manual", phase="EW", duration=30).status_code == 403
    assert command(client, admin_h, mode="manual", phase="EW", duration=30).status_code == 403
    assert command(client, {}, mode="manual", phase="EW", duration=30).status_code == 401
    log = client.get("/api/v1/admin/security-log", headers=admin_h).json()
    assert [row["event"] for row in log].count("access_denied") >= 2


def test_bad_commands_are_400(client, operator_h):
    assert command(client, operator_h, mode="manual", phase="EW").json()["error"] == "invalid_command"
    assert command(client, operator_h, mode="fly").status_code == 400
    assert command(client, operator_h, mode="manual", phase="ZZ", duration=30).json()["error"] == "invalid_phase"
    assert command(client, operator_h, mode="manual", phase="EW", duration=1).json()["error"] == "invalid_duration"


def test_unknown_intersection_is_404(client, operator_h):
    response = client.post("/api/v1/intersections/NOPE/signal-command", json={"mode": "auto"}, headers=operator_h)
    assert response.status_code == 404


def test_interlock_conflict_is_409(client, operator_h, sensor_h):
    client.get(f"{BASE}/signal-state", headers=operator_h)                      # creates the state at the start time
    ped = {"intersectionId": "INT-001", "timestamp": "2026-10-19T09:00:10Z", "sourceId": "x", "detectionType": "pedestrian",
           "count": 1, "confidence": 0.9}
    assert client.post("/api/v1/detections", json=ped, headers=sensor_h).status_code == 201
    clock.advance(50)                                                            # inside the 45 to 67 second pedestrian stage
    conflict = command(client, operator_h, mode="manual", phase="EW", duration=30)
    assert conflict.status_code == 409 and conflict.json()["error"] == "interlock_conflict"


def test_audit_log_endpoint_is_for_operators_and_administrators(client, operator_h, admin_h, analyst_h):
    command(client, operator_h, mode="manual", phase="EW", duration=30)
    rows = client.get(f"{BASE}/audit-log", headers=operator_h).json()
    assert any(row["event"] == "override_applied" and row["actor"] == "operator" for row in rows)
    assert client.get(f"{BASE}/audit-log", headers=admin_h).status_code == 200
    assert client.get(f"{BASE}/audit-log", headers=analyst_h).status_code == 403
    assert client.get(f"{BASE}/audit-log", params={"event": "override_applied"}, headers=operator_h).json()


def test_tick_and_recompute_endpoints(client, operator_h, analyst_h):
    assert client.post(f"{BASE}/signal-control/tick", headers=operator_h).status_code == 200
    recomputed = client.post(f"{BASE}/adaptive/recompute", headers=operator_h)
    assert recomputed.status_code == 200 and "densities" in recomputed.json()
    assert client.post(f"{BASE}/adaptive/recompute", headers=analyst_h).status_code == 403
    clock.advance(10)
    assert client.get(f"{BASE}/signal-state", headers=operator_h).json()["secondsRemaining"] == 30.0
    assert clock.now() > START
