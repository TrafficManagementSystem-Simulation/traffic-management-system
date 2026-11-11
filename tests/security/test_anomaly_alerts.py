"""Alerts on anomalous command patterns (Likhita): PRJ-SR-005, test case TC-Sec-06."""
from __future__ import annotations

from datetime import datetime, timedelta

from tms.admin import rbac
from tms.common import clock
from tms.incident import security_monitor as monitor
from tms.signal_control import controller, override

from tests.conftest import START, after

IID = "INT-001"


def alerts(session):
    return monitor.list_alerts(session)


def test_TC_Sec_06_rapid_repeated_overrides_raise_an_alert_within_60_seconds(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()
    phases = ["EW", "NS", "EW", "NS", "EW", "NS"]
    for index, phase in enumerate(phases):                       # six overrides in 30 seconds
        override.request_override(session, IID, phase, 15, "mallory", now=after(index * 5))
    raised_at = None
    for second in range(30, 91):                                 # the monitor runs every second
        if monitor.scan(session, after(second)):
            raised_at = second
            break
    assert raised_at is not None and raised_at - 0 <= 60
    found = alerts(session)
    assert found[0]["type"] == "rapid_overrides" and found[0]["user"] == "mallory" and found[0]["count"] >= 5


def test_a_few_overrides_are_normal(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()
    for index in range(4):
        override.request_override(session, IID, ["EW", "NS"][index % 2], 15, "operator", now=after(index * 20))
    assert monitor.scan(session, after(80)) == []


def test_the_same_alert_is_not_repeated_every_second(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()
    for index in range(6):
        override.request_override(session, IID, ["EW", "NS"][index % 2], 15, "mallory", now=after(index * 5))
    first = monitor.scan(session, after(30))
    again = [monitor.scan(session, after(30 + s)) for s in range(1, 20)]
    assert len(first) == 1 and all(a == [] for a in again)
    assert len(alerts(session)) == 1


def test_off_hours_administrator_access_raises_an_alert(session):
    clock.freeze(datetime(2026, 10, 19, 23, 30))
    rbac.login(session, "admin", "admin12345")
    raised = monitor.scan(session, clock.now(), "06:00-22:00")
    assert [a["type"] for a in raised] == ["off_hours_admin_access"] and raised[0]["user"] == "admin"


def test_administrator_access_in_working_hours_and_operator_access_at_night_are_normal(session):
    rbac.login(session, "admin", "admin12345")
    assert monitor.scan(session, clock.now()) == []                                  # 09:00
    clock.freeze(datetime(2026, 10, 19, 23, 30))
    rbac.login(session, "operator", "operator123")
    assert monitor.scan(session, clock.now()) == []


def test_repeated_failed_logins_raise_an_alert(session):
    for _ in range(5):
        try:
            rbac.login(session, "admin", "wrong-password")
        except Exception:  # noqa: BLE001
            pass
    raised = monitor.scan(session, after(10))
    assert [a["type"] for a in raised] == ["repeated_failed_logins"]


def test_hours_that_cross_midnight_work():
    assert monitor.is_off_hours(datetime(2026, 1, 1, 12, 0), "22:00-06:00") is True
    assert monitor.is_off_hours(datetime(2026, 1, 1, 23, 0), "22:00-06:00") is False
    assert monitor.is_off_hours(datetime(2026, 1, 1, 5, 59), "22:00-06:00") is False
    assert monitor.is_off_hours(datetime(2026, 1, 1, 6, 0), "06:00-22:00") is False
    assert monitor.is_off_hours(datetime(2026, 1, 1, 22, 0), "06:00-22:00") is True


def test_only_administrators_read_security_alerts(client, operator_h, analyst_h, admin_h, session):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    monitor.scan(session, clock.now())
    assert client.get("/api/v1/security/alerts", headers=operator_h).status_code == 403
    assert client.get("/api/v1/security/alerts", headers=analyst_h).status_code == 403
    assert client.get("/api/v1/security/alerts", headers=admin_h).json()[0]["type"] == "repeated_failed_logins"
