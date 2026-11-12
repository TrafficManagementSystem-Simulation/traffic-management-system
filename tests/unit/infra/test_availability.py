"""Availability of the signal-control service (Roshini): TMS-NF-002 (99.5% a month, maintenance excluded)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tms.common.errors import CommandError
from tms.infra import uptime

MONTH_START, MONTH_END = datetime(2026, 9, 1), datetime(2026, 10, 1)
NOW = datetime(2026, 10, 2)


def beats(session, outages=(), unhealthy=(), start=MONTH_START, end=MONTH_END, step=30):
    """Heartbeats every ``step`` seconds, except inside ``outages`` (a list of (from, to) datetimes)."""
    moment = start
    while moment < end:
        if not any(a <= moment < b for a, b in outages):
            session.add(uptime.Heartbeat(timestamp=moment, healthy=not any(a <= moment < a + timedelta(seconds=step) for a in unhealthy)))
        moment += timedelta(seconds=step)
    session.commit()


def at(day, hour, minute=0):
    return datetime(2026, 9, day, hour, minute)


def measure(session):
    return uptime.availability(session, MONTH_START, MONTH_END, NOW)


def test_a_period_without_problems_is_100_percent(session):
    beats(session, start=at(29, 0), step=30)                       # the last two days of the month
    result = uptime.availability(session, at(29, 0), MONTH_END, NOW)
    assert result["availabilityPercent"] == 100.0 and result["meetsTarget"] is True and result["outages"] == []


def test_three_hours_down_in_a_30_day_month_meets_the_target(session):
    beats(session, outages=[(at(10, 2), at(10, 5))])
    result = measure(session)
    assert result["downtimeSeconds"] == pytest.approx(3 * 3600, abs=60)
    assert result["availabilityPercent"] == pytest.approx(99.583, abs=0.01) and result["meetsTarget"] is True


def test_four_hours_down_misses_the_target(session):
    beats(session, outages=[(at(10, 2), at(10, 6))])
    result = measure(session)
    assert result["availabilityPercent"] == pytest.approx(99.444, abs=0.01) and result["meetsTarget"] is False
    assert len(result["outages"]) == 1 and result["outages"][0]["from"].startswith("2026-09-10T02:00")


def test_planned_maintenance_is_not_counted_against_the_service(session):
    beats(session, outages=[(at(10, 2), at(10, 6))])
    uptime.add_maintenance_window(session, at(10, 2), at(10, 6), "database upgrade")
    result = measure(session)
    assert result["downtimeSeconds"] == pytest.approx(0, abs=60) and result["meetsTarget"] is True
    assert result["maintenanceSeconds"] == 4 * 3600


def test_only_the_part_of_an_outage_outside_maintenance_counts(session):
    beats(session, outages=[(at(10, 2), at(10, 8))])
    uptime.add_maintenance_window(session, at(10, 2), at(10, 4))                                # covers the first two hours
    assert measure(session)["downtimeSeconds"] == pytest.approx(4 * 3600, abs=60)


def test_unhealthy_heartbeats_count_as_downtime(session):
    beats(session, unhealthy=[at(5, 12) + timedelta(seconds=30 * i) for i in range(120)])        # one hour of failures
    assert measure(session)["downtimeSeconds"] == pytest.approx(3600, abs=60)


def test_a_service_that_started_mid_month_is_judged_from_its_first_heartbeat(session):
    beats(session, start=at(16, 0))
    result = measure(session)
    assert result["availabilityPercent"] == 100.0 and result["observedSeconds"] == pytest.approx(15 * 86400, abs=60)


def test_no_heartbeats_means_unknown_not_100(session):
    assert uptime.availability(session, MONTH_START, MONTH_END, NOW)["availabilityPercent"] is None


def test_the_current_month_is_measured_up_to_now(session):
    beats(session, start=datetime(2026, 10, 1), end=datetime(2026, 10, 3), step=30)
    result = uptime.availability(session, datetime(2026, 10, 1), datetime(2026, 11, 1), datetime(2026, 10, 3))
    assert result["observedSeconds"] == 2 * 86400 and result["availabilityPercent"] == 100.0


def test_heartbeats_are_written_about_every_30_seconds(session):
    start = datetime(2026, 10, 1, 12, 0, 0)
    written = [uptime.record_heartbeat(session, start + timedelta(seconds=s)) for s in range(0, 95)]
    assert sum(written) == 4                                                                    # at 0, 30, 60, 90
    assert uptime.record_heartbeat(session, start + timedelta(seconds=96), healthy=False) is True   # a failure is always recorded


def test_maintenance_window_validation(session):
    with pytest.raises(CommandError):
        uptime.add_maintenance_window(session, at(2, 5), at(2, 4))
    assert uptime.month_bounds("2026-12") == (datetime(2026, 12, 1), datetime(2027, 1, 1))
    with pytest.raises(CommandError):
        uptime.month_bounds("december")


def test_api(client, admin_h, operator_h, session):
    assert client.get("/api/v1/health").json()["status"] == "ok"                                 # public probe
    assert client.post("/api/v1/admin/maintenance-windows", headers=operator_h,
                       json={"startsAt": "2026-10-20T01:00:00Z", "endsAt": "2026-10-20T03:00:00Z"}).status_code == 403
    assert client.post("/api/v1/admin/maintenance-windows", headers=admin_h,
                       json={"startsAt": "2026-10-20T01:00:00Z", "endsAt": "2026-10-20T03:00:00Z", "reason": "patching"}).status_code == 201
    assert client.post("/api/v1/admin/maintenance-windows", headers=admin_h,
                       json={"startsAt": "2026-10-20T03:00:00Z", "endsAt": "2026-10-20T01:00:00Z"}).status_code == 400
    assert client.get("/api/v1/admin/maintenance-windows", headers=admin_h).json()[0]["reason"] == "patching"
    assert client.get("/api/v1/admin/availability", params={"month": "2026-10"}, headers=admin_h).json()["availabilityPercent"] is None
    uptime.record_heartbeat(session, datetime(2026, 10, 19, 8, 0, 0), force=True)
    for s in range(30, 3600, 30):
        uptime.record_heartbeat(session, datetime(2026, 10, 19, 8, 0, 0) + timedelta(seconds=s))
    body = client.get("/api/v1/admin/availability", params={"month": "2026-10"}, headers=admin_h).json()
    assert body["availabilityPercent"] == 100.0 and body["month"] == "2026-10"
    assert client.get("/api/v1/admin/availability", params={"month": "bad"}, headers=admin_h).status_code == 400
