"""Encrypted evidence and access logging (Likhita): PRJ-SR-003, TMS-NF-003, test case TC-Sec-04."""
from __future__ import annotations

import base64

import pytest
from sqlalchemy import text

from tms.common.errors import CommandError, NotFoundError
from tms.detection import evidence
from tms.detection.models import Evidence

KEY = "ZGVtby1vbmx5LWtleS1jaGFuZ2UtbWUtaW4tcHJvZCE="
SECRET = b"JPEG-BYTES-SHOWING-A-PLATE-KA05MN1234"
URL = "/api/v1/evidence"


def body(**changes):
    data = {"intersectionId": "INT-001", "sourceId": "cam-N1", "capturedAt": "2026-10-19T08:59:00Z",
            "contentType": "image/jpeg", "dataBase64": base64.b64encode(SECRET).decode(), "plateText": "KA05MN1234"}
    data.update(changes)
    return data


def test_TC_Sec_04_nothing_identifiable_is_stored_in_plain_text(client, sensor_h, session):
    stored = client.post(URL, json=body(), headers=sensor_h)
    assert stored.status_code == 201
    raw = bytes(session.execute(text("SELECT ciphertext FROM evidence")).scalar_one())
    assert SECRET not in raw and b"KA05MN1234" not in raw and base64.b64encode(SECRET) not in raw
    # nothing identifiable in any other column either
    columns = session.execute(text("SELECT id, intersection_id, content_type, source_id FROM evidence")).one()
    assert "KA05" not in " ".join(str(c) for c in columns)


def test_TC_Sec_04_every_retrieval_creates_an_access_log_entry(client, sensor_h, operator_h, admin_h):
    evidence_id = client.post(URL, json=body(), headers=sensor_h).json()["evidenceId"]
    for headers in (operator_h, admin_h, operator_h):
        got = client.get(f"{URL}/{evidence_id}", headers=headers)
        assert got.status_code == 200
        assert base64.b64decode(got.json()["dataBase64"]) == SECRET and got.json()["plateText"] == "KA05MN1234"
    log = client.get("/api/v1/evidence-access-log", params={"evidenceId": evidence_id}, headers=admin_h).json()
    actions = [row["action"] for row in reversed(log)]
    assert actions == ["stored", "retrieved", "retrieved", "retrieved"]
    assert [row["username"] for row in log if row["action"] == "retrieved"] == ["operator", "admin", "operator"][::-1]
    assert log[-1]["username"] == "sensor:cam-N1"


def test_least_privilege_for_viewing(client, sensor_h, analyst_h, operator_h):
    evidence_id = client.post(URL, json=body(), headers=sensor_h).json()["evidenceId"]
    assert client.get(f"{URL}/{evidence_id}", headers=analyst_h).status_code == 403
    assert client.get(f"{URL}/{evidence_id}").status_code == 401
    assert client.get(f"{URL}/{evidence_id}", headers=sensor_h).status_code == 401       # a sensor can write, not read
    assert client.get("/api/v1/evidence-access-log", headers=operator_h).status_code == 403
    listed = client.get(URL, headers=operator_h).json()
    assert listed[0]["id"] == evidence_id and "dataBase64" not in listed[0] and "plateText" not in listed[0]


def test_storing_needs_the_sensor_key_and_a_known_intersection(client, sensor_h):
    assert client.post(URL, json=body()).status_code == 401
    assert client.post(URL, json=body(), headers={"X-API-Key": "nope"}).status_code == 403
    assert client.post(URL, json=body(intersectionId="NOPE"), headers=sensor_h).status_code == 404


@pytest.mark.parametrize("change", [{"contentType": "text/html"}, {"dataBase64": "!!notbase64!!"},
                                    {"dataBase64": ""}, {"plateText": "X" * 40}])
def test_bad_uploads_are_rejected(client, sensor_h, change):
    assert client.post(URL, json=body(**change), headers=sensor_h).status_code in (400, 422)


def test_unknown_evidence_is_404_and_the_attempt_is_logged(client, operator_h, admin_h):
    assert client.get(f"{URL}/EV-nope", headers=operator_h).status_code == 404
    log = client.get("/api/v1/evidence-access-log", headers=admin_h).json()
    assert log[0]["action"] == "denied" and log[0]["username"] == "operator"


def test_a_wrong_key_cannot_read_the_data_and_a_bad_key_is_reported(session):
    other = "b3RoZXItZGVtby1rZXktZm9yLXRlc3Rpbmctb25seSE="
    evidence_id = evidence.store(session, KEY, "INT-001", "cam", __import__("datetime").datetime(2026, 10, 19), "image/png",
                                 b"abc", None, "sensor:cam")
    with pytest.raises(evidence.EvidenceKeyError):
        evidence.retrieve(session, other, evidence_id, "admin")
    with pytest.raises(evidence.EvidenceKeyError):
        evidence.retrieve(session, "not-a-key", evidence_id, "admin")
    assert session.get(Evidence, evidence_id).ciphertext != b"abc"


def test_size_and_type_limits(session):
    from datetime import datetime

    with pytest.raises(CommandError):
        evidence.store(session, KEY, "INT-001", "cam", datetime(2026, 10, 19), "image/png", b"", None, "x")
    with pytest.raises(CommandError):
        evidence.store(session, KEY, "INT-001", "cam", datetime(2026, 10, 19), "image/png", b"x" * (evidence.MAX_BYTES + 1), None, "x")
