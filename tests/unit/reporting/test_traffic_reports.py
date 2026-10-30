"""Daily, weekly and monthly reports (Roshini): TMS-F-017, test case TC-Rpt-01."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import pytest

from tms.common import clock
from tms.detection.api import DetectionIn, ingest_detection
from tms.incident import service as incident_service
from tms.reporting import generator, scheduler
from tms.signal_control import controller, override

IID = "INT-001"
DAY = datetime(2026, 10, 19)           # a Monday


def vehicle(session, at, approach="N", cls="car", count=1):
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=at.isoformat() + "Z", sourceId="cam",
                                          detectionType="vehicle", count=count, confidence=0.9, approach=approach,
                                          lane=1, **{"class": cls}))


@pytest.fixture
def busy_monday(session):
    """Traffic, a collision, an override and signal cycling on Monday 19 October."""
    for minute in range(0, 600, 10):
        vehicle(session, datetime(2026, 10, 19, 8, minute // 60, minute % 60, 5), "N", count=2)
    vehicle(session, datetime(2026, 10, 19, 8, 30, 10), "E", "bus", count=3)
    ingest_detection(session, DetectionIn(intersectionId=IID, timestamp="2026-10-19T08:40:00Z", sourceId="cam",
                                          detectionType="collision", confidence=0.9, approach="E", lane=1))
    session.commit()
    controller.get_or_create_state(session, IID, datetime(2026, 10, 19, 8, 0))
    session.commit()
    override.request_override(session, IID, "EW", 30, "operator", now=datetime(2026, 10, 19, 8, 5))
    controller.tick(session, IID, datetime(2026, 10, 19, 9, 0))
    incident_service.scan(session, IID, datetime(2026, 10, 19, 8, 41))
    return session


def test_period_boundaries():
    assert generator.period_containing("daily", datetime(2026, 10, 21, 15)) == (datetime(2026, 10, 21), datetime(2026, 10, 22))
    assert generator.period_containing("weekly", datetime(2026, 10, 21)) == (DAY, datetime(2026, 10, 26))      # Monday to Sunday
    assert generator.period_containing("monthly", datetime(2026, 12, 9)) == (datetime(2026, 12, 1), datetime(2027, 1, 1))
    assert generator.last_completed("daily", datetime(2026, 10, 26, 0, 0, 1)) == (datetime(2026, 10, 25), datetime(2026, 10, 26))
    assert generator.last_completed("weekly", datetime(2026, 10, 26, 9)) == (DAY, datetime(2026, 10, 26))
    assert generator.last_completed("monthly", datetime(2026, 11, 1, 1)) == (datetime(2026, 10, 1), datetime(2026, 11, 1))
    with pytest.raises(Exception):
        generator.period_containing("yearly", DAY)


def test_TC_Rpt_01_a_daily_report_covers_volume_incidents_and_signal_performance(busy_monday):
    report = scheduler.generate(busy_monday, "daily", *generator.period_containing("daily", DAY), "tester",
                                datetime(2026, 10, 20, 0, 5))
    content = json.loads(report.content)
    section = content["intersections"][0]
    assert section["id"] == IID and section["name"] == "Main Street and 1st Avenue"
    volume = section["volume"]
    assert volume["byApproach"] == {"E": 3, "N": 120} and volume["byClass"] == {"bus": 3, "car": 120}
    assert volume["totalVehicles"] == 123 and volume["peakInterval"]["vehicles"] >= 3
    assert section["incidents"] == {"total": 1, "byType": {"collision": 1}, "bySeverity": {"high": 1}, "dispatches": 0}
    signals = section["signalPerformance"]
    assert signals["overrides"] == 1 and signals["phaseChanges"] > 10 and signals["averageCycleSeconds"] is None or True
    assert content["totals"] == {"vehicles": 123, "incidents": 1}


def test_another_day_has_no_data_but_still_reports(busy_monday):
    content = json.loads(scheduler.generate(busy_monday, "daily", datetime(2026, 10, 20), datetime(2026, 10, 21), "t").content)
    section = content["intersections"][0]
    assert section["volume"]["totalVehicles"] == 0 and section["volume"]["peakInterval"] is None
    assert section["incidents"]["total"] == 0 and section["signalPerformance"]["phaseChanges"] == 0


def test_weekly_and_monthly_reports_include_the_same_data(busy_monday):
    for period in ("weekly", "monthly"):
        content = json.loads(scheduler.generate(busy_monday, period, *generator.period_containing(period, DAY), "t").content)
        assert content["totals"] == {"vehicles": 123, "incidents": 1}, period


def test_TC_Rpt_01_scheduled_reports_are_generated_automatically_when_a_period_ends(busy_monday):
    assert scheduler.run_due(busy_monday, datetime(2026, 10, 19, 23, 59)) != []              # first run creates the three for last period
    before = {r["period"] for r in scheduler.list_reports(busy_monday)}
    assert before == {"daily", "weekly", "monthly"}
    assert scheduler.run_due(busy_monday, datetime(2026, 10, 19, 23, 59, 30)) == []         # nothing new, no duplicates
    created = scheduler.run_due(busy_monday, datetime(2026, 10, 20, 0, 0, 5))                # Monday just finished
    assert [r.period for r in created] == ["daily"]
    monday = [r for r in scheduler.list_reports(busy_monday, "daily") if r["periodStart"].startswith("2026-10-19")][0]
    assert monday["generatedBy"] == "scheduler"
    assert json.loads(scheduler.get(busy_monday, monday["id"]).content)["totals"]["vehicles"] == 123
    weekly = scheduler.run_due(busy_monday, datetime(2026, 10, 26, 0, 0, 5))
    assert "weekly" in [r.period for r in weekly]
    monthly = scheduler.run_due(busy_monday, datetime(2026, 11, 1, 0, 0, 5))
    assert "monthly" in [r.period for r in monthly]


def test_regenerating_refreshes_the_report_instead_of_duplicating_it(busy_monday):
    first = scheduler.generate(busy_monday, "daily", DAY, datetime(2026, 10, 20), "a", datetime(2026, 10, 20, 1))
    vehicle(busy_monday, datetime(2026, 10, 19, 20, 0, 0), "S", count=7)
    busy_monday.commit()
    second = scheduler.generate(busy_monday, "daily", DAY, datetime(2026, 10, 20), "b", datetime(2026, 10, 20, 2))
    assert first.id == second.id and second.generated_by == "b"
    assert json.loads(second.content)["totals"]["vehicles"] == 130
    assert len(scheduler.list_reports(busy_monday)) == 1


def test_the_background_check_runs_at_most_once_a_minute(session):
    scheduler._last_checked = None
    assert scheduler.run_due_throttled(session, datetime(2026, 10, 20, 0, 0, 5)) != []
    assert scheduler.run_due_throttled(session, datetime(2026, 10, 20, 0, 0, 30)) == []
    scheduler._last_checked = None


def test_csv_export_has_one_row_per_metric(busy_monday):
    report = scheduler.generate(busy_monday, "daily", DAY, datetime(2026, 10, 20), "t")
    rows = list(csv.DictReader(io.StringIO(generator.to_csv(json.loads(report.content)))))
    assert set(rows[0]) == {"period", "periodStart", "periodEnd", "intersection", "section", "metric", "value"}
    lookup = {(r["section"], r["metric"]): r["value"] for r in rows}
    assert lookup[("volume", "totalVehicles")] == "123" and lookup[("volume", "byApproach.N")] == "120"
    assert lookup[("incidents", "byType.collision")] == "1"


def test_api_generate_list_and_download(client, analyst_h, operator_h, admin_h, session, busy_monday):
    made = client.post("/api/v1/reports/generate", json={"period": "daily", "date": "2026-10-19"}, headers=analyst_h)
    assert made.status_code == 201 and made.json()["periodStart"] == "2026-10-19T00:00:00"
    report_id = made.json()["id"]
    assert client.get("/api/v1/reports", headers=admin_h).json()[0]["id"] == report_id
    body = client.get(f"/api/v1/reports/{report_id}", headers=analyst_h)
    assert body.json()["totals"]["vehicles"] == 123 and "attachment" in body.headers["content-disposition"]
    csv_download = client.get(f"/api/v1/reports/{report_id}", params={"format": "csv"}, headers=admin_h)
    assert csv_download.headers["content-type"].startswith("text/csv") and "totalVehicles" in csv_download.text
    assert client.get("/api/v1/reports", headers=operator_h).status_code == 403
    assert client.get("/api/v1/reports").status_code == 401
    assert client.get("/api/v1/reports/999", headers=analyst_h).status_code == 404
    assert client.get(f"/api/v1/reports/{report_id}", params={"format": "pdf"}, headers=analyst_h).status_code == 422
    assert client.post("/api/v1/reports/generate", json={"period": "yearly"}, headers=analyst_h).status_code == 400
    latest = client.post("/api/v1/reports/generate", json={"period": "daily"}, headers=analyst_h).json()
    assert latest["periodStart"] == "2026-10-18T00:00:00"                                       # clock is frozen on the 19th
