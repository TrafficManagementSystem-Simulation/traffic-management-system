"""TC-Sim-07: Pagination and filtering on GET /simulation/runs."""
from __future__ import annotations
import pytest


SAMPLE = "single_intersection"


@pytest.fixture
def net_id(client, analyst_h):
    r = client.post("/api/v1/simulation/networks/import-sample",
                    json={"name": SAMPLE}, headers=analyst_h)
    return r.json()["id"]


def _run(client, analyst_h, net_id, seed=42):
    r = client.post("/api/v1/simulation/runs",
                    json={"networkId": net_id, "durationSeconds": 300, "seed": seed},
                    headers=analyst_h)
    assert r.status_code == 201, r.text
    return r.json()["runId"]


def test_TC_Sim_07_list_runs_returns_pagination_envelope(client, analyst_h, net_id):
    _run(client, analyst_h, net_id)
    r = client.get("/api/v1/simulation/runs", headers=analyst_h)
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body
    assert "total" in body
    assert "page" in body
    assert "pageSize" in body


def test_filter_by_network_id(client, analyst_h, net_id):
    _run(client, analyst_h, net_id)
    r = client.get(f"/api/v1/simulation/runs?networkId={net_id}", headers=analyst_h)
    assert r.status_code == 200
    for run in r.json()["runs"]:
        assert run["networkId"] == net_id


def test_filter_by_nonexistent_network_returns_empty(client, analyst_h):
    r = client.get("/api/v1/simulation/runs?networkId=9999", headers=analyst_h)
    assert r.status_code == 200
    assert r.json()["runs"] == []


def test_sort_by_newest(client, analyst_h, net_id):
    id1 = _run(client, analyst_h, net_id, seed=1)
    id2 = _run(client, analyst_h, net_id, seed=2)
    r = client.get("/api/v1/simulation/runs?sortBy=newest", headers=analyst_h)
    ids = [x["runId"] for x in r.json()["runs"]]
    assert ids.index(id2) < ids.index(id1)


def test_sort_by_oldest(client, analyst_h, net_id):
    id1 = _run(client, analyst_h, net_id, seed=1)
    id2 = _run(client, analyst_h, net_id, seed=2)
    r = client.get("/api/v1/simulation/runs?sortBy=oldest", headers=analyst_h)
    ids = [x["runId"] for x in r.json()["runs"]]
    assert ids.index(id1) < ids.index(id2)


def test_sort_by_delay(client, analyst_h, net_id):
    _run(client, analyst_h, net_id, seed=1)
    _run(client, analyst_h, net_id, seed=2)
    r = client.get("/api/v1/simulation/runs?sortBy=delay", headers=analyst_h)
    assert r.status_code == 200
    delays = [x["metrics"]["averageDelaySeconds"] for x in r.json()["runs"]]
    assert delays == sorted(delays)


def test_sort_by_throughput(client, analyst_h, net_id):
    _run(client, analyst_h, net_id, seed=1)
    _run(client, analyst_h, net_id, seed=2)
    r = client.get("/api/v1/simulation/runs?sortBy=throughput", headers=analyst_h)
    assert r.status_code == 200
    tp = [x["metrics"]["throughputPerHour"] for x in r.json()["runs"]]
    assert tp == sorted(tp, reverse=True)


def test_pagination_page_size(client, analyst_h, net_id):
    for s in range(1, 5):
        _run(client, analyst_h, net_id, seed=s)
    r = client.get("/api/v1/simulation/runs?pageSize=2&page=1", headers=analyst_h)
    assert r.status_code == 200
    body = r.json()
    assert len(body["runs"]) <= 2
    assert body["pageSize"] == 2
    assert body["total"] >= 4


def test_pagination_page2(client, analyst_h, net_id):
    for s in range(1, 5):
        _run(client, analyst_h, net_id, seed=s)
    r1 = client.get("/api/v1/simulation/runs?pageSize=2&page=1", headers=analyst_h)
    r2 = client.get("/api/v1/simulation/runs?pageSize=2&page=2", headers=analyst_h)
    ids1 = {x["runId"] for x in r1.json()["runs"]}
    ids2 = {x["runId"] for x in r2.json()["runs"]}
    assert ids1.isdisjoint(ids2)


def test_page_size_capped_at_200(client, analyst_h):
    r = client.get("/api/v1/simulation/runs?pageSize=999", headers=analyst_h)
    assert r.status_code == 200
    assert r.json()["pageSize"] == 200


def test_list_runs_requires_auth(client):
    r = client.get("/api/v1/simulation/runs")
    assert r.status_code in (401, 403)
