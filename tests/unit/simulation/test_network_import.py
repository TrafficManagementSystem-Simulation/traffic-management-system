"""TC-Sim-06: Network file upload and delete (TMS-F-009 extension)."""
from __future__ import annotations
import json, io
import pytest
from fastapi.testclient import TestClient


VALID_NET = {
    "nodes": [
        {"id": "src", "type": "entry"},
        {"id": "X", "type": "signal", "signal": {
            "yellow": 3, "all_red": 2, "offset": 0,
            "phases": [
                {"name": "NS", "green": 30, "links": ["src_X"]},
                {"name": "EW", "green": 25, "links": ["src_X"]},
            ],
        }, "turns": {"src_X": {"X_dst": 1.0}}},
        {"id": "dst", "type": "exit"},
    ],
    "links": [
        {"id": "src_X", "from": "src", "to": "X",   "length_m": 100, "speed_limit_kmh": 50, "lanes": 1},
        {"id": "X_dst", "from": "X",   "to": "dst",  "length_m": 100, "speed_limit_kmh": 50, "lanes": 1},
    ],
    "demand": [{"link": "src_X", "rate_per_hour": 400}],
}


def _upload(client, analyst_h, payload, filename="net.json", *, expect=201):
    data = json.dumps(payload).encode()
    resp = client.post(
        "/api/v1/simulation/networks/upload",
        files={"file": (filename, io.BytesIO(data), "application/json")},
        headers=analyst_h,
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def test_TC_Sim_06_valid_upload_creates_network(client, analyst_h):
    r = _upload(client, analyst_h, VALID_NET, "my_net.json")
    assert r["name"] == "my_net"
    assert r["nodes"] == 3
    assert r["links"] == 2  # 2 links
    assert "id" in r


def test_upload_non_json_extension_rejected(client, analyst_h):
    r = _upload(client, analyst_h, VALID_NET, "net.txt", expect=422)
    assert r["detail"]["error"] == "invalid_file_type"


def test_upload_invalid_json_rejected(client, analyst_h):
    resp = client.post(
        "/api/v1/simulation/networks/upload",
        files={"file": ("bad.json", io.BytesIO(b"not json!!"), "application/json")},
        headers=analyst_h,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_json"


def test_upload_invalid_network_schema_rejected(client, analyst_h):
    r = _upload(client, analyst_h, {"nodes": [], "links": []}, "empty.json", expect=422)
    assert r["detail"]["error"] == "validation_failure"


def test_upload_requires_analyst_role(client, operator_h):
    _upload(client, operator_h, VALID_NET, expect=403)


def test_delete_network_no_runs(client, admin_h, analyst_h):
    net = _upload(client, analyst_h, VALID_NET)
    resp = client.delete(f"/api/v1/simulation/networks/{net['id']}", headers=admin_h)
    assert resp.status_code == 204


def test_delete_network_with_runs_rejected(client, admin_h, analyst_h):
    net = _upload(client, analyst_h, VALID_NET)
    client.post("/api/v1/simulation/runs",
                json={"networkId": net["id"], "durationSeconds": 60, "seed": 1}, headers=analyst_h)
    resp = client.delete(f"/api/v1/simulation/networks/{net['id']}", headers=admin_h)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "network_has_runs"


def test_delete_network_requires_admin(client, analyst_h):
    net = _upload(client, analyst_h, VALID_NET)
    resp = client.delete(f"/api/v1/simulation/networks/{net['id']}", headers=analyst_h)
    assert resp.status_code == 403


def test_delete_unknown_network_is_404(client, admin_h):
    resp = client.delete("/api/v1/simulation/networks/9999", headers=admin_h)
    assert resp.status_code == 404
