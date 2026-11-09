"""Green-wave coordination (Manoj): TMS-F-005, test case TC-Sig-05."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tms.common.errors import ValidationFailure
from tms.signal_control import coordination
from tms.simulation.engine import run_simulation
from tms.simulation.metrics import compute_metrics

CORRIDOR = {"targetSpeedMps": 14.0, "cycleSeconds": 90, "greenSeconds": 40,
            "intersections": [{"id": "S1"}, {"id": "S2", "distanceFromPreviousM": 420},
                              {"id": "S3", "distanceFromPreviousM": 560}]}
SAMPLE = Path(__file__).resolve().parents[3] / "data" / "sample_networks" / "corridor_3.json"


def test_offsets_follow_the_travel_time_between_intersections():
    offsets = coordination.compute_offsets(CORRIDOR)
    assert [o["offsetSeconds"] for o in offsets] == [0.0, 30.0, 70.0]      # 420/14 = 30 s, 980/14 = 70 s


def test_offsets_wrap_around_the_cycle():
    far = {**CORRIDOR, "intersections": [{"id": "A"}, {"id": "B", "distanceFromPreviousM": 1400}]}
    assert coordination.compute_offsets(far)[1]["offsetSeconds"] == 10.0   # 100 s into a 90 s cycle


def test_TC_Sig_05_a_platoon_crosses_three_coordinated_intersections_without_stopping():
    offsets = [o["offsetSeconds"] for o in coordination.compute_offsets(CORRIDOR)]
    assert coordination.platoon_stops(CORRIDOR, offsets) == 0
    assert coordination.platoon_stops(CORRIDOR, [0, 0, 0]) >= 1             # uncoordinated signals do stop it


@pytest.mark.parametrize("change", [
    {"intersections": [{"id": "S1"}]}, {"targetSpeedMps": 0}, {"cycleSeconds": 10}, {"greenSeconds": 90},
    {"intersections": [{"id": "S1"}, {"id": "S2"}]}, {"intersections": [{"id": "S1"}, {"id": "S2", "distanceFromPreviousM": 5}]},
])
def test_bad_corridors_are_rejected(change):
    with pytest.raises(ValidationFailure):
        coordination.compute_offsets({**CORRIDOR, **change})


def test_offsets_can_be_applied_to_a_simulation_network_and_it_still_runs():
    network = json.loads(SAMPLE.read_text())
    signals = [n["id"] for n in network["nodes"] if n["type"] == "signal"]
    corridor = {"targetSpeedMps": 13.9, "cycleSeconds": 90, "greenSeconds": 40,
                "intersections": [{"id": signals[0]}] + [{"id": s, "distanceFromPreviousM": 300} for s in signals[1:]]}
    offsets = coordination.compute_offsets(corridor)
    coordinated = coordination.apply_to_network(network, offsets)
    assert [n["signal"]["offset"] for n in coordinated["nodes"] if n["type"] == "signal"][0] == 0
    metrics = compute_metrics(run_simulation(coordinated, {"duration_seconds": 900}))
    assert metrics["vehiclesCompleted"] > 0
    assert network["nodes"][0] == json.loads(SAMPLE.read_text())["nodes"][0]   # the original was not changed


def test_api(client, operator_h, analyst_h):
    response = client.post("/api/v1/intersections/corridors/green-wave", json=CORRIDOR, headers=operator_h)
    assert response.status_code == 200
    body = response.json()
    assert body["stopsWithOffsets"] == 0 and body["stopsWithoutOffsets"] >= 1
    assert client.post("/api/v1/intersections/corridors/green-wave", json=CORRIDOR, headers=analyst_h).status_code == 403
    bad = client.post("/api/v1/intersections/corridors/green-wave", json={**CORRIDOR, "greenSeconds": 500}, headers=operator_h)
    assert bad.status_code == 422
