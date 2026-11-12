"""Control loop latency (Manoj): TMS-NF-001, test case TC-Perf-01.

Sensor input to phase update must take 1 second or less for 95% of control cycles.
"""
from __future__ import annotations

import time

from tms.detection.api import DetectionIn, ingest_detection
from tms.signal_control import controller

from tests.conftest import after

CYCLES = 200


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * share))]


def test_TC_Perf_01_95th_percentile_of_sensor_to_phase_update_is_within_one_second(session):
    controller.get_or_create_state(session, "INT-001", after(0))
    session.commit()
    durations = []
    for index in range(CYCLES):
        started = time.perf_counter()
        ingest_detection(session, DetectionIn(intersectionId="INT-001", timestamp=after(index * 10).isoformat() + "Z",
                                              sourceId="cam", detectionType="vehicle", count=3, confidence=0.9,
                                              approach="NE"[index % 2], lane=1,
                                              **{"class": "car"}))
        controller.recompute_plan(session, "INT-001", after(index * 10))
        controller.tick(session, "INT-001", after(index * 10))
        durations.append(time.perf_counter() - started)
    assert percentile(durations, 0.95) <= 1.0
    assert max(durations) < 5.0


def test_the_api_path_is_also_fast(client, sensor_h, operator_h):
    durations = []
    for index in range(60):
        started = time.perf_counter()
        event = {"intersectionId": "INT-001", "timestamp": "2026-10-19T09:00:05Z", "sourceId": "cam",
                 "detectionType": "vehicle", "class": "car", "count": 1, "confidence": 0.9, "approach": "N", "lane": 1}
        assert client.post("/api/v1/detections", json=event, headers=sensor_h).status_code == 201
        assert client.get("/api/v1/intersections/INT-001/signal-state", headers=operator_h).status_code == 200
        durations.append(time.perf_counter() - started)
    assert percentile(durations, 0.95) <= 1.0
