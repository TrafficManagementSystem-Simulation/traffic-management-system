"""Field controller keeps running without the central platform (Manoj): TMS-NF-006, test case TC-Rel-01."""
from __future__ import annotations

from datetime import timedelta

from tms.admin import config_service
from tms.signal_control import controller
from tms.signal_control.failsafe import FieldController, safe_default_plan

from tests.conftest import START

HOURS_4 = 4 * 3600


def cfg(session):
    return config_service.get_intersection_config(session, "INT-001")


def run(field, seconds, step=1):
    seen = []
    for t in range(0, seconds, step):
        seen.append(field.signal_at(START + timedelta(seconds=t)))
    return seen


def test_TC_Rel_01_signals_stay_safe_for_four_hours_without_the_central_platform(session, tmp_path):
    config = cfg(session)
    plan = controller.build_plan(config, {"NS": 45, "EW": 25})
    field = FieldController(config, START, tmp_path / "plan.json", plan)
    field.link_up = False                                   # total loss of connectivity
    assert field.receive_plan(controller.build_plan(config, {"NS": 20, "EW": 50})) is False

    signals = run(field, HOURS_4)
    assert len(signals) == HOURS_4
    greens = [s for s in signals if s.stage == "GREEN"]
    assert {s.phase for s in greens} == {"NS", "EW"}
    # the last known-good plan is still the one in use after four hours
    assert field.plan == plan and field.source == "central"
    ns_seconds = len([s for s in greens if s.phase == "NS"])
    assert ns_seconds == (HOURS_4 // field.cycle_seconds) * 45


def test_a_green_is_always_followed_by_yellow_then_all_red_never_straight_to_the_other_green(session):
    field = FieldController(cfg(session), START)
    previous = field.signal_at(START)
    for signal in run(field, 3600)[1:]:
        if (signal.phase, signal.stage) != (previous.phase, previous.stage):
            allowed = {("GREEN", "YELLOW"), ("YELLOW", "ALL_RED"), ("ALL_RED", "GREEN")}
            assert (previous.stage, signal.stage) in allowed
            if previous.stage == "YELLOW" or previous.stage == "GREEN":
                assert signal.phase == previous.phase
        previous = signal


def test_with_no_plan_ever_received_the_safe_default_is_used(session):
    config = cfg(session)
    field = FieldController(config, START)
    assert field.plan == safe_default_plan(config) and field.source == "default"
    assert field.signal_at(START).stage == "GREEN"


def test_after_a_restart_the_plan_comes_back_from_local_storage(session, tmp_path):
    config, store = cfg(session), tmp_path / "plan.json"
    plan = controller.build_plan(config, {"NS": 45, "EW": 25})
    FieldController(config, START, store, plan)
    restarted = FieldController(config, START, store)
    assert restarted.plan == plan and restarted.source == "local-store"


def test_a_damaged_store_falls_back_to_the_safe_default(session, tmp_path):
    store = tmp_path / "plan.json"
    store.write_text("{not json")
    assert FieldController(cfg(session), START, store).source == "default"
    store.write_text('{"green": {"NS": 1, "EW": 1}, "yellow": 3, "all_red": 2}')       # parses but unsafe
    assert FieldController(cfg(session), START, store).source == "default"


def test_when_the_link_returns_the_new_plan_starts_at_the_next_cycle(session):
    config = cfg(session)
    field = FieldController(config, START)
    new_plan = controller.build_plan(config, {"NS": 50, "EW": 20})
    assert field.receive_plan(new_plan) is True
    first_cycle = field.cycle_seconds
    assert field.signal_at(START + timedelta(seconds=5)).stage == "GREEN" and field.plan != new_plan
    field.signal_at(START + timedelta(seconds=first_cycle + 1))
    assert field.plan == new_plan and field.source == "central"


def test_unsafe_plans_from_the_centre_are_refused(session):
    config = cfg(session)
    field = FieldController(config, START)
    assert field.receive_plan(controller.build_plan(config, {"NS": 1, "EW": 1})) is False
    assert field.pending is None
