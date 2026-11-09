"""Simulation endpoints (Naveen): analysts and administrators only."""
from __future__ import annotations

import copy
import json
from pathlib import Path

BASE = "/api/v1/simulation"
SAMPLE = json.loads((Path(__file__).resolve().parents[3] / "data" / "sample_networks" / "single_intersection.json").read_text())


def import_sample(client, headers, name="single_intersection"):
    return client.post(f"{BASE}/networks/import-sample", json={"name": name}, headers=headers)


def test_roles(client, operator_h, analyst_h, admin_h):
    assert client.get(f"{BASE}/samples").status_code == 401
    assert client.get(f"{BASE}/samples", headers=operator_h).status_code == 403
    assert client.get(f"{BASE}/samples", headers=analyst_h).json() == ["corridor_3", "single_intersection"]
    assert client.get(f"{BASE}/samples", headers=admin_h).status_code == 200


def test_validate_endpoint_reports_problems(client, analyst_h):
    assert client.post(f"{BASE}/networks/validate", json=SAMPLE, headers=analyst_h).json() == {"valid": True, "errors": []}
    broken = copy.deepcopy(SAMPLE)
    broken["links"][0]["to"] = "GHOST"
    result = client.post(f"{BASE}/networks/validate", json=broken, headers=analyst_h).json()
    assert result["valid"] is False and any("GHOST" in e for e in result["errors"])


def test_import_list_and_read_back(client, analyst_h):
    created = import_sample(client, analyst_h)
    assert created.status_code == 201 and created.json()["nodes"] == 5 and created.json()["links"] == 4
    network_id = created.json()["id"]
    assert [n["id"] for n in client.get(f"{BASE}/networks", headers=analyst_h).json()] == [network_id]
    assert client.get(f"{BASE}/networks/{network_id}", headers=analyst_h).json()["topology"]["name"] == "Single intersection"


def test_import_rejects_unknown_and_tricky_names(client, analyst_h):
    assert import_sample(client, analyst_h, "nope").status_code == 404
    assert import_sample(client, analyst_h, "../../etc/passwd").status_code == 404


def test_invalid_network_is_not_saved(client, analyst_h):
    broken = copy.deepcopy(SAMPLE)
    broken["nodes"].append({"id": "LOST", "type": "junction"})
    response = client.post(f"{BASE}/networks", json={"name": "bad", "topology": broken}, headers=analyst_h)
    assert response.status_code == 422
    assert client.get(f"{BASE}/networks", headers=analyst_h).json() == []


def test_run_stores_metrics_and_trajectories(client, analyst_h):
    network_id = import_sample(client, analyst_h).json()["id"]
    run = client.post(f"{BASE}/runs", json={"networkId": network_id, "durationSeconds": 600, "seed": 3}, headers=analyst_h)
    assert run.status_code == 201
    body = run.json()
    assert body["metrics"]["vehiclesEntered"] > 0 and body["metrics"]["runSeconds"] < 5
    run_id = body["runId"]
    assert client.get(f"{BASE}/runs/{run_id}", headers=analyst_h).json()["metrics"] == body["metrics"]
    assert client.get(f"{BASE}/runs/{run_id}/trajectories", headers=analyst_h).json()["runId"] == run_id
    assert [r["runId"] for r in client.get(f"{BASE}/runs", headers=analyst_h).json()["runs"]] == [run_id]


def test_run_errors(client, analyst_h):
    network_id = import_sample(client, analyst_h).json()["id"]
    assert client.post(f"{BASE}/runs", json={"networkId": 999}, headers=analyst_h).status_code == 404
    assert client.post(f"{BASE}/runs", json={"networkId": network_id, "durationSeconds": 5}, headers=analyst_h).status_code == 422
    assert client.get(f"{BASE}/runs/999", headers=analyst_h).status_code == 404
    assert client.get(f"{BASE}/runs/999/trajectories", headers=analyst_h).status_code == 404


def test_operator_cannot_run(client, operator_h, analyst_h):
    network_id = import_sample(client, analyst_h).json()["id"]
    assert client.post(f"{BASE}/runs", json={"networkId": network_id}, headers=operator_h).status_code == 403
