"""Incident detection, alerts and dispatch (Likhita): TMS-F-014 (TC-Inc-01), F-015 (TC-Inc-02), F-016 (TC-Inc-03)."""
from __future__ import annotations

import pytest

from tms.detection.api import DetectionIn, ingest_detection
from tms.incident import dispatch as dispatch_mod
from tms.incident import service
from tms.incident.dispatch import LoopbackEmergencyService, ServiceUnavailable
from tms.common.errors import CommandError, NotFoundError

from tests.conftest import after

IID = "INT-001"


def vehicle(session, at, approach="N", lane=1, count=1, speed=None):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=after(at).isoformat() + "Z", sourceId="cam",
                                          detectionType="vehicle", count=count, confidence=0.9, approach=approach, lane=lane,
                                          speedKmh=speed, **{"class": "car"}))


def normal_traffic(session, until=900, per_minute=2):
    for minute in range(until // 60):
        for k in range(per_minute):
            vehicle(session, minute * 60 + 10 + k * 20, "N")
    session.commit()


def test_TC_Inc_01_an_injected_congestion_is_detected_within_60_seconds(session):
    normal_traffic(session)
    start = 900
    found_at = None
    for second in range(0, 120):                    # a vehicle every 2 s on N = 30 per minute, scanned every 5 s
        t = start + second
        if second % 2 == 0:
            vehicle(session, t, "N")
        if second % 5 == 0:
            session.commit()
            if service.scan(session, IID, after(t)):
                found_at = second
                break
    assert found_at is not None and found_at <= 60
    incident = service.list_incidents(session)[0]
    assert incident["type"] == "congestion" and incident["approach"] == "N" and incident["severity"] == "medium"
    assert incident["details"]["vehiclesPerMinute"] >= 20


def test_normal_busy_traffic_is_not_an_incident(session):
    normal_traffic(session, per_minute=12)                      # a steady 12 vehicles a minute
    for second in range(900, 960, 5):
        vehicle(session, second, "N")                           # ... and it carries on at 12 a minute
    session.commit()
    assert service.scan(session, IID, after(959)) == []


def test_a_steady_heavy_flow_is_normal_but_a_sudden_jump_is_not(session):
    normal_traffic(session, per_minute=22)                      # always busy, so 22 a minute is the norm
    session.commit()
    assert service.scan(session, IID, after(900)) == []
    for k in range(60):
        vehicle(session, 905 + k, "N")                          # 60 a minute: high severity
    session.commit()
    created = service.scan(session, IID, after(965))
    assert [(i.kind, i.severity) for i in created] == [("congestion", "high")]


def test_a_stalled_vehicle_is_found_once_it_has_been_stopped_for_30_seconds(session):
    for second in (0, 10, 20):
        vehicle(session, second, "E", lane=2, speed=0)
    session.commit()
    assert service.scan(session, IID, after(20)) == []          # only 20 seconds so far
    vehicle(session, 35, "E", lane=2, speed=0)
    session.commit()
    created = service.scan(session, IID, after(35))
    assert [(i.kind, i.approach, i.lane) for i in created] == [("stalled_vehicle", "E", 2)]


def test_a_vehicle_that_moves_again_is_not_stalled(session):
    for second in (0, 15, 40):
        vehicle(session, second, "E", lane=2, speed=0)
    vehicle(session, 50, "E", lane=2, speed=30)
    session.commit()
    assert service.scan(session, IID, after(55)) == []


def test_a_collision_report_becomes_a_high_severity_incident(session):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=after(5).isoformat() + "Z", sourceId="cam",
                                          detectionType="collision", confidence=0.8, approach="S", lane=1))
    created = service.scan(session, IID, after(6))
    assert [(i.kind, i.severity, i.approach) for i in created] == [("collision", "high", "S")]


def test_TC_Inc_02_the_alert_has_location_type_and_severity_and_is_ready_within_5_seconds(session):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=after(5).isoformat() + "Z", sourceId="cam",
                                          detectionType="collision", confidence=0.8, approach="S", lane=1))
    service.scan(session, IID, after(6))
    alert = service.list_alerts(session)[0]
    incident = service.list_incidents(session)[0]
    assert "Main Street and 1st Avenue" in alert["message"] and "S approach" in alert["message"]
    assert alert["type"] == "collision" and alert["severity"] == "high" and alert["intersectionId"] == IID
    from datetime import datetime
    assert (datetime.fromisoformat(alert["createdAt"]) - datetime.fromisoformat(incident["detectedAt"])).total_seconds() <= 5


def test_the_same_incident_is_not_alerted_twice_until_it_is_resolved(session):
    for second in (0, 10, 20, 35):
        vehicle(session, second, "E", lane=2, speed=0)
    session.commit()
    first = service.scan(session, IID, after(35))
    assert len(first) == 1 and service.scan(session, IID, after(40)) == []
    assert len(service.list_alerts(session)) == 1
    service.resolve(session, first[0].id, after(50))
    assert len(service.scan(session, IID, after(55))) == 1       # still stationary: a new incident is raised


def test_acknowledge_and_resolve_flow(session):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=after(5).isoformat() + "Z", sourceId="cam",
                                          detectionType="collision", confidence=0.8))
    incident_id = service.scan(session, IID, after(6))[0].id
    assert service.acknowledge(session, incident_id, "operator", after(8))["status"] == "acknowledged"
    assert service.list_alerts(session, unacknowledged_only=True) == []
    assert service.list_alerts(session, since_id=1) == []
    assert service.resolve(session, incident_id, after(9))["status"] == "resolved"
    with pytest.raises(CommandError):
        service.acknowledge(session, incident_id, "operator")
    with pytest.raises(NotFoundError):
        service.acknowledge(session, 999, "operator")


def raise_collision(session):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=after(5).isoformat() + "Z", sourceId="cam",
                                          detectionType="collision", confidence=0.8, approach="S", lane=1))
    return service.scan(session, IID, after(6))[0].id


def test_TC_Inc_03_dispatch_is_transmitted_acknowledged_and_logged(session):
    from tms.admin.models import SecurityLog
    from sqlalchemy import select

    incident_id = raise_collision(session)
    client = LoopbackEmergencyService()
    row = dispatch_mod.dispatch(session, incident_id, "ambulance", "operator", client, "two vehicles", after(10))
    assert row.status == "acknowledged" and row.reference.startswith("ACK-")
    assert client.sent[0][0] == "ambulance" and "collision" in client.sent[0][1] and "two vehicles" in client.sent[0][1]
    log = session.scalars(select(SecurityLog).where(SecurityLog.event == "emergency_dispatch")).all()
    assert len(log) == 1 and log[0].username == "operator" and f"incident={incident_id}" in log[0].details
    assert service.list_incidents(session)[0]["dispatches"][0]["service"] == "ambulance"


def test_a_service_that_does_not_answer_is_reported_and_logged(session):
    class Down:
        def notify(self, service, message):
            raise ConnectionError("no route")

    incident_id = raise_collision(session)
    with pytest.raises(ServiceUnavailable):
        dispatch_mod.dispatch(session, incident_id, "fire", "operator", Down(), now=after(10))
    assert service.list_incidents(session)[0]["dispatches"][0]["status"] == "failed"


def test_bad_dispatch_requests(session):
    incident_id = raise_collision(session)
    for args, error in (((incident_id, "taxi"), CommandError), ((999, "fire"), NotFoundError)):
        with pytest.raises(error):
            dispatch_mod.dispatch(session, *args, "operator", LoopbackEmergencyService())
    with pytest.raises(CommandError):
        dispatch_mod.dispatch(session, incident_id, "fire", "operator", LoopbackEmergencyService(), "x" * 301)


def test_api_end_to_end(client, sensor_h, operator_h, analyst_h, admin_h):
    event = {"intersectionId": IID, "timestamp": "2026-10-19T08:59:50Z", "sourceId": "cam", "detectionType": "collision",
             "confidence": 0.9, "approach": "N", "lane": 1}
    assert client.post("/api/v1/detections", json=event, headers=sensor_h).status_code == 201
    scanned = client.post(f"/api/v1/intersections/{IID}/incidents/scan", headers=operator_h).json()
    assert scanned[0]["type"] == "collision"
    alerts = client.get("/api/v1/alerts", headers=operator_h).json()
    assert alerts[0]["severity"] == "high"
    assert client.get("/api/v1/alerts", headers=analyst_h).status_code == 403           # alerts are for on-duty staff
    assert client.get("/api/v1/incidents", headers=analyst_h).json()[0]["id"] == scanned[0]["id"]
    incident_id = scanned[0]["id"]
    sent = client.post(f"/api/v1/incidents/{incident_id}/dispatch", json={"service": "police", "notes": "check"}, headers=operator_h)
    assert sent.status_code == 201 and sent.json()["status"] == "acknowledged"
    assert client.post(f"/api/v1/incidents/{incident_id}/dispatch", json={"service": "police"}, headers=admin_h).status_code == 403
    assert client.post(f"/api/v1/incidents/{incident_id}/dispatch", json={"service": "dog"}, headers=operator_h).status_code == 400
    assert client.post("/api/v1/incidents/99/dispatch", json={"service": "fire"}, headers=operator_h).status_code == 404
    assert client.post(f"/api/v1/incidents/{incident_id}/acknowledge", headers=operator_h).json()["status"] == "acknowledged"
    assert client.post(f"/api/v1/incidents/{incident_id}/resolve", headers=admin_h).json()["status"] == "resolved"
    assert client.get("/api/v1/incidents", params={"status": "open"}, headers=operator_h).json() == []


def test_the_api_reports_a_failing_service_as_502(client, sensor_h, operator_h, app):
    class Down:
        def notify(self, service, message):
            raise TimeoutError

    event = {"intersectionId": IID, "timestamp": "2026-10-19T08:59:50Z", "sourceId": "cam", "detectionType": "collision", "confidence": 0.9}
    client.post("/api/v1/detections", json=event, headers=sensor_h)
    incident_id = client.post(f"/api/v1/intersections/{IID}/incidents/scan", headers=operator_h).json()[0]["id"]
    app.state.emergency_service = Down()
    response = client.post(f"/api/v1/incidents/{incident_id}/dispatch", json={"service": "fire"}, headers=operator_h)
    assert response.status_code == 502 and response.json()["error"] == "service_unavailable"
