"""Third-party GIS and dashboard interface (Naveen): TMS-NF-010, test case TC-Interop-01."""
from __future__ import annotations

from tms.admin import config_service
from tms.common.config import DEFAULT_INTERSECTION_CONFIG
from tms.infra.interop_contract import API_VERSION, check_feature_collection
from tms.infra.interop_client import CityDashboardClient


def client_for(test_client, headers):
    def get(path):
        response = test_client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    return CityDashboardClient(get)


def test_TC_Interop_01_a_sample_third_party_client_reads_the_published_contract(client, analyst_h, session):
    config_service.create_intersection(session, "INT-002", "Second Street", actor="test",
                                       config={**DEFAULT_INTERSECTION_CONFIG, "latitude": 12.97, "longitude": 77.6})
    third_party = client_for(client, analyst_h)
    found = third_party.intersections()
    assert {f["id"] for f in found} == {"INT-001", "INT-002"}
    second = next(f for f in found if f["id"] == "INT-002")
    assert (second["lat"], second["lon"]) == (12.97, 77.6)
    assert all(f["stage"] in ("GREEN", "YELLOW", "ALL_RED", "PED") for f in found)
    assert third_party.summary() == {"apiVersion": API_VERSION, "intersections": 2, "adaptive": 2, "manual": 0,
                                     "pedestriansWaiting": 0}


def test_the_contract_checker_catches_a_changed_response():
    good = {"type": "FeatureCollection", "apiVersion": API_VERSION, "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [77.5, 12.9]},
        "properties": {"id": "A", "name": "n", "mode": "adaptive", "phase": "NS", "stage": "GREEN",
                       "secondsRemaining": 3.5, "planVersion": 1}}]}
    assert check_feature_collection(good) == []
    broken = {**good, "features": [{**good["features"][0], "geometry": {"type": "Point", "coordinates": ["x"]},
                                    "properties": {"id": "A"}}]}
    assert len(check_feature_collection(broken)) > 3
    assert check_feature_collection({"type": "nope"})


def test_every_published_path_is_versioned(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert paths and all(p.startswith("/api/v1/") for p in paths), [p for p in paths if not p.startswith("/api/v1/")]


def test_meta_is_public_and_data_needs_sign_in(client):
    meta = client.get("/api/v1/meta").json()
    assert meta["apiVersion"] == API_VERSION and "/api/v1/gis/intersections" in meta["endpoints"]
    assert client.get("/api/v1/gis/intersections").status_code == 401
    assert client.get("/api/v1/city/summary").status_code == 401


def test_location_is_part_of_the_configuration(client, admin_h):
    url = "/api/v1/admin/intersections/INT-001/config"
    assert client.put(url, headers=admin_h, json={"changes": {"latitude": 13.0, "longitude": 77.0}}).status_code == 200
    assert client.put(url, headers=admin_h, json={"changes": {"latitude": 99}}).status_code == 422
    assert client.put(url, headers=admin_h, json={"changes": {"longitude": "east"}}).status_code == 422
