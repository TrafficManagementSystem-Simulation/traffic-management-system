"""Multi-factor sign-in for actions that change signal state (Roshini): PRJ-SR-002, test case TC-Sec-03."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tms.admin import mfa
from tms.admin.models import SecurityLog
from tms.common import clock
from tms.common.seed import DEMO_MFA_SECRETS

from tests.conftest import sign_in

SECRET = DEMO_MFA_SECRETS["operator"]
LOGIN = "/api/v1/auth/login"
COMMAND = "/api/v1/intersections/INT-001/signal-command"
OVERRIDE = {"mode": "manual", "phase": "EW", "duration": 30}


def login(client, otp=None, user="operator", password="operator123"):
    body = {"username": user, "password": password}
    if otp is not None:
        body["otp"] = otp
    return client.post(LOGIN, json=body)


def events(session):
    return [row.event for row in session.scalars(select(SecurityLog).order_by(SecurityLog.id))]


def test_the_totp_code_matches_the_rfc_6238_test_vectors():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"                    # ASCII "12345678901234567890" in base32
    for moment, expected in ((59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")):
        assert mfa.totp(secret, datetime.utcfromtimestamp(moment)) == expected


def test_TC_Sec_03_login_without_the_second_factor_is_rejected(client, session):
    response = login(client)
    assert response.status_code == 401 and response.json()["error"] == "mfa_required"
    assert "login_mfa_missing" in events(session) and "login_ok" not in events(session)


def test_a_wrong_code_is_rejected_and_logged(client, session):
    response = login(client, "000000")
    assert response.status_code == 401 and response.json()["error"] == "mfa_invalid"
    assert "login_mfa_failed" in events(session)
    assert login(client, "12ab56").status_code == 401 and login(client, "").status_code == 401


def test_the_right_code_signs_in_a_multi_factor_session(client):
    response = login(client, mfa.totp(SECRET, clock.now()))
    assert response.status_code == 200 and response.json()["mfa"] is True
    token = response.json()["token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["mfaVerified"] is True


def test_a_code_cannot_be_used_twice(client):
    code = mfa.totp(SECRET, clock.now())
    assert login(client, code).status_code == 200
    assert login(client, code).json()["error"] == "mfa_invalid"
    clock.advance(30)                                              # the next code works
    assert login(client, mfa.totp(SECRET, clock.now())).status_code == 200


def test_the_neighbouring_codes_cover_a_small_clock_difference(client):
    assert login(client, mfa.code_for(SECRET, mfa.step_of(clock.now()) - 1)).status_code == 200
    clock.advance(60)
    assert login(client, mfa.code_for(SECRET, mfa.step_of(clock.now()) + 1)).status_code == 200
    clock.advance(300)
    assert login(client, mfa.code_for(SECRET, mfa.step_of(clock.now()) - 5)).status_code == 401


def test_a_wrong_password_never_reaches_the_second_factor(client):
    response = login(client, mfa.totp(SECRET, clock.now()), password="wrong-password")
    assert response.json()["error"] == "invalid_credentials"


def test_an_operator_session_without_mfa_cannot_change_signal_state(client, app):
    from tms.admin import rbac
    from tms.common import db

    with db.session_scope() as session:
        rbac.create_user(session, "newop", "newop-pass1", rbac.OPERATOR)       # not enrolled yet
    headers = sign_in(client, "newop", "newop-pass1")
    denied = client.post(COMMAND, json=OVERRIDE, headers=headers)
    assert denied.status_code == 403 and denied.json()["error"] == "mfa_required"
    assert client.get("/api/v1/intersections/INT-001/signal-state", headers=headers).status_code == 200   # viewing is fine
    assert client.post("/api/v1/intersections/INT-001/adaptive/recompute", headers=headers).status_code == 403


def test_enrolling_upgrades_the_session_and_later_logins_need_a_code(client, session):
    from tms.admin import rbac
    from tms.common import db

    with db.session_scope() as s:
        rbac.create_user(s, "newop", "newop-pass1", rbac.OPERATOR)
    headers = sign_in(client, "newop", "newop-pass1")
    started = client.post("/api/v1/auth/mfa/enroll", headers=headers).json()
    assert started["secret"] and started["otpauthUri"].startswith("otpauth://totp/")
    assert client.post("/api/v1/auth/mfa/confirm", json={"otp": "000000"}, headers=headers).status_code == 400
    assert client.post("/api/v1/auth/mfa/confirm", json={"otp": mfa.totp(started["secret"], clock.now())}, headers=headers).status_code == 200
    assert client.post(COMMAND, json=OVERRIDE, headers=headers).status_code == 200              # this session now counts
    assert login(client, user="newop", password="newop-pass1").json()["error"] == "mfa_required"
    clock.advance(30)
    assert login(client, mfa.totp(started["secret"], clock.now()), "newop", "newop-pass1").status_code == 200


def test_confirm_without_enrolling_first_is_refused(client, analyst_h):
    assert client.post("/api/v1/auth/mfa/confirm", json={"otp": "123456"}, headers=analyst_h).json()["error"] == "mfa_not_started"


def test_an_administrator_can_reset_a_lost_authenticator(client, admin_h, analyst_h):
    assert client.post("/api/v1/admin/users/operator/mfa/reset", headers=analyst_h).status_code == 403
    assert client.post("/api/v1/admin/users/operator/mfa/reset", headers=admin_h).status_code == 200
    assert login(client).status_code == 200                                                      # no code needed until re-enrolled
    assert client.post("/api/v1/admin/users/nobody/mfa/reset", headers=admin_h).status_code == 404


def test_the_requirement_can_be_switched_off_for_local_development():
    from fastapi.testclient import TestClient
    from tms.common.config import Settings
    from tms.main import create_app

    with TestClient(create_app(Settings(database_url="sqlite://", autotick=False, require_mfa=False))) as c:
        headers = {"Authorization": "Bearer " + c.post(LOGIN, json={"username": "analyst", "password": "analyst123"}).json()["token"]}
        assert c.post("/api/v1/intersections/INT-001/adaptive/recompute", headers=headers).status_code == 403   # role still checked


def test_the_overrides_made_in_other_tests_use_a_multi_factor_session(client, operator_h):
    assert client.post(COMMAND, json=OVERRIDE, headers=operator_h).status_code == 200