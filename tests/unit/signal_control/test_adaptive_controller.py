"""Adaptive timing, the signal state machine and pedestrian stage (Manoj): TMS-F-001, TMS-F-008 (phase)."""
from __future__ import annotations

import json

import pytest

from tms.admin import config_service
from tms.common.errors import TMSError
from tms.detection import pedestrian
from tms.detection.api import DetectionIn, ingest_detection
from tms.detection.synthetic import generate_events
from tms.signal_control import audit, controller, override
from tms.signal_control.models import SignalState

from tests.conftest import START, after

IID = "INT-001"


def heavy_north_south(session, ns=20, ew=3, minutes=5):
    for event in generate_events(IID, seed=2, minutes=minutes, start=START,
                                 vehicles_per_minute={"N": ns, "S": ns, "E": ew, "W": ew}):
        ingest_detection(session, DetectionIn(**event))
    session.commit()


def plan_of(session) -> dict:
    return json.loads(session.get(SignalState, IID).plan)


def transitions(session) -> list[str]:
    rows = audit.list_events(session, IID, event="phase_change")
    return [row["details"]["to"] for row in reversed(rows)]


def test_green_times_follow_the_traffic_but_stay_inside_the_limits():
    cfg = config_service.validate_config(dict(__import__("tms.common.config", fromlist=["x"]).DEFAULT_INTERSECTION_CONFIG))
    equal = controller.compute_green_times({}, cfg)
    assert equal == {"NS": 40, "EW": 40}
    busy_ns = controller.compute_green_times({"NS": 40.0, "EW": 6.0}, cfg)
    assert busy_ns["NS"] > busy_ns["EW"] and busy_ns["NS"] <= cfg["max_green"] and busy_ns["EW"] >= cfg["min_green"]
    assert sum(busy_ns.values()) == 80                      # the whole usable cycle is handed out
    extreme = controller.compute_green_times({"NS": 100.0, "EW": 0.0}, cfg)
    assert extreme == {"NS": 60, "EW": 20}                  # EW is not starved below min_green; NS capped


def test_TC_Sig_01_green_time_changes_within_one_control_cycle(session):
    controller.get_or_create_state(session, IID, START)
    session.commit()
    before = plan_of(session)
    heavy_north_south(session)
    cycle = config_service.get_intersection_config(session, IID)["cycle_seconds"]

    controller.tick(session, IID, after(cycle + 5))

    changed = plan_of(session)
    assert changed["green"]["NS"] > before["green"]["NS"]
    assert changed["green"]["EW"] < before["green"]["EW"]
    assert session.get(SignalState, IID).plan_version == 2
    assert audit.count_events(session, IID, "plan_applied") == 1


def test_a_full_cycle_runs_green_yellow_all_red_then_the_next_phase(session):
    controller.tick(session, IID, after(0))
    controller.tick(session, IID, after(95))
    assert transitions(session) == ["NS/GREEN", "NS/YELLOW", "NS/ALL_RED", "EW/GREEN", "EW/YELLOW", "EW/ALL_RED",
                                    "NS/GREEN"]


def test_invalid_plan_is_rejected_and_the_old_plan_is_kept(session, monkeypatch):
    controller.tick(session, IID, after(0))
    heavy_north_south(session)
    kept = plan_of(session)
    monkeypatch.setattr(controller, "compute_green_times", lambda densities, cfg: {"NS": 1, "EW": 79})
    controller.tick(session, IID, after(95))
    assert plan_of(session) == kept
    assert audit.count_events(session, IID, "plan_rejected") >= 1


def test_validate_plan_rejects_unsafe_plans(session):
    cfg = config_service.get_intersection_config(session, IID)
    good = controller.build_plan(cfg, {"NS": 30, "EW": 30})
    controller.validate_plan(good, cfg)
    bad_plans = [
        controller.build_plan(cfg, {"NS": 5, "EW": 30}),                        # below min_green
        controller.build_plan(cfg, {"NS": 61, "EW": 30}),                       # above max_green
        controller.build_plan(cfg, {"NS": 30}),                                 # missing phase
        {**good, "yellow": 1},                                                  # yellow too short
        {**good, "all_red": 0},                                                 # all-red too short
        {"green": {"NS": 60, "EW": 60}, "yellow": 20, "all_red": 12},          # cycle 184 s, over the 180 s limit
    ]
    for plan in bad_plans:
        with pytest.raises(TMSError):
            controller.validate_plan(plan, cfg)


def test_apply_plan_records_the_plan_and_the_source(session):
    cfg = config_service.get_intersection_config(session, IID)
    plan = controller.build_plan(cfg, {"NS": 45, "EW": 25})
    applied_at = controller.apply_plan(session, IID, plan, source="auto", actor="tester", now=after(3))
    assert applied_at == after(3)
    assert plan_of(session) == plan
    event = audit.list_events(session, IID, event="plan_applied")[0]
    assert event["actor"] == "tester" and event["source"] == "auto"
    with pytest.raises(TMSError):
        controller.apply_plan(session, IID, controller.build_plan(cfg, {"NS": 1, "EW": 1}))


def test_while_an_override_is_active_the_computed_plan_is_stored_not_applied(session):
    controller.tick(session, IID, after(0))
    heavy_north_south(session)
    override.request_override(session, IID, "EW", 120, "op1", now=after(5))
    version = session.get(SignalState, IID).plan_version
    result = controller.recompute_plan(session, IID, after(20))
    assert result["mode"] == "manual" and result["plan"]["green"]["NS"] > result["plan"]["green"]["EW"]
    assert session.get(SignalState, IID).plan_version == version
    assert session.get(SignalState, IID).next_plan is not None
    assert audit.count_events(session, IID, "plan_stored") == 1


def test_TC_VDC_03_pedestrian_phase_runs_within_one_cycle_of_the_request(session):
    controller.tick(session, IID, after(0))
    pedestrian.request_crossing(session, IID, after(10))
    session.commit()

    state = controller.tick(session, IID, after(50))        # NS clears at 45, then the pedestrian stage
    assert (state.phase, state.stage) == ("PED", "PED")
    assert state.stage_duration == 22                       # walk 7 + clearance 15
    assert not pedestrian.has_pending(session, IID)
    assert audit.count_events(session, IID, "pedestrian_served") == 1
    assert (after(45) - after(10)).total_seconds() < 90     # served well inside one 90-second cycle


def test_a_request_just_after_the_all_red_waits_for_the_next_one_but_still_inside_a_cycle(session):
    controller.tick(session, IID, after(0))
    controller.tick(session, IID, after(46))                # all-red at 45 passed with nobody waiting
    pedestrian.request_crossing(session, IID, after(46))
    session.commit()
    state = controller.tick(session, IID, after(95))        # EW clears at 90, pedestrian stage follows
    assert state.stage == "PED"
    assert (after(90) - after(46)).total_seconds() <= 90


def test_after_the_pedestrian_stage_the_next_vehicle_phase_gets_its_green(session):
    controller.tick(session, IID, after(0))
    pedestrian.request_crossing(session, IID, after(10))
    session.commit()
    controller.tick(session, IID, after(70))                # PED ended at 67
    assert transitions(session)[-2:] == ["PED/PED", "EW/GREEN"]


def test_view_state_describes_the_signal(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()
    state = controller.view_state(session, IID, after(5))
    assert state["mode"] == "adaptive" and state["phase"] == "NS" and state["stage"] == "GREEN"
    assert state["secondsRemaining"] == 35.0 and state["pedestriansWaiting"] == 0
    assert state["plan"]["green"] == {"NS": 40, "EW": 40}
