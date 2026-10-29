"""Manual override and the audit log (Manoj): TMS-F-002, TMS-F-003."""
from __future__ import annotations

from datetime import datetime

import pytest

from tms.common.errors import CommandError, InterlockError
from tms.detection import pedestrian
from tms.signal_control import audit, controller, override
from tms.signal_control.models import SignalState

from tests.conftest import after

IID = "INT-001"


def start(session):
    controller.get_or_create_state(session, IID, after(0))
    session.commit()


def test_TC_Sig_02_override_is_applied_within_2_seconds_and_reverts_on_command(session):
    start(session)
    requested = after(5)                                   # NS green until second 40
    result = override.request_override(session, IID, "EW", 30, "op1", now=requested)
    assert result["status"] == "applied" and result["mode"] == "manual"
    assert (datetime.fromisoformat(result["appliedAt"]) - requested).total_seconds() <= 2
    state = session.get(SignalState, IID)
    assert state.stage == "YELLOW"                         # the NS green was cut short at once

    state = controller.tick(session, IID, after(10))       # yellow 3s + all-red 2s, then the held phase
    assert (state.phase, state.stage, state.mode) == ("EW", "GREEN", "manual")

    cleared = override.clear_override(session, IID, "op1", now=after(20))
    assert cleared["mode"] == "adaptive"
    assert controller.tick(session, IID, after(21)).mode == "adaptive"
    assert audit.count_events(session, IID, "override_cleared") == 1


def test_the_override_ends_by_itself_when_the_time_is_up(session):
    start(session)
    override.request_override(session, IID, "EW", 30, "op1", now=after(5))
    state = controller.tick(session, IID, after(60))
    assert state.mode == "adaptive"
    reasons = [e["details"]["reason"] for e in audit.list_events(session, IID, event="override_cleared")]
    assert reasons == ["expired"]


def test_holding_the_current_phase_extends_its_green(session):
    start(session)
    override.request_override(session, IID, "NS", 60, "op1", now=after(5))
    state = controller.tick(session, IID, after(41))       # without the hold NS would be yellow from second 40
    assert (state.phase, state.stage) == ("NS", "GREEN")


def test_all_red_hold(session):
    start(session)
    override.request_override(session, IID, "ALL_RED", 20, "op1", now=after(5))
    state = controller.tick(session, IID, after(15))
    assert (state.phase, state.stage) == ("ALL_RED", "ALL_RED")


def test_interlock_blocks_an_override_during_the_pedestrian_stage(session):
    start(session)
    pedestrian.request_crossing(session, IID, after(10))
    session.commit()
    with pytest.raises(InterlockError):
        override.request_override(session, IID, "EW", 30, "op1", now=after(50))   # PED runs 45 to 67
    assert audit.count_events(session, IID, "override_rejected") == 1
    assert session.get(SignalState, IID).mode == "adaptive"


@pytest.mark.parametrize("phase,duration,code", [
    ("XX", 30, "invalid_phase"),
    ("EW", 5, "invalid_duration"),          # shorter than the 15 second minimum hold
    ("EW", 999, "invalid_duration"),
    ("EW", "30", "invalid_duration"),
    ("ALL_RED", 2, "invalid_duration"),
])
def test_bad_commands_are_rejected_with_a_reason(session, phase, duration, code):
    start(session)
    with pytest.raises(CommandError) as caught:
        override.request_override(session, IID, phase, duration, "op1", now=after(5))
    assert caught.value.code == code


def test_clearing_when_nothing_is_overridden_is_harmless(session):
    start(session)
    assert override.clear_override(session, IID, "op1", now=after(5))["mode"] == "adaptive"


def test_TC_Sig_03_every_state_change_is_in_the_audit_log(session):
    start(session)
    controller.tick(session, IID, after(100))
    override.request_override(session, IID, "EW", 40, "op1", now=after(100))
    controller.tick(session, IID, after(300))
    override.request_override(session, IID, "ALL_RED", 20, "op1", now=after(300))
    override.clear_override(session, IID, "op1", now=after(310))
    controller.tick(session, IID, after(600))

    changes = list(reversed(audit.list_events(session, IID, event="phase_change", limit=1000)))
    assert len(changes) > 20
    assert changes[0]["details"]["from"] == "-/-"
    for previous, current in zip(changes, changes[1:]):    # no gaps: each change starts where the last ended
        assert current["details"]["from"] == previous["details"]["to"]
        assert current["timestamp"] >= previous["timestamp"]
    for row in changes:
        assert row["timestamp"] and row["intersectionId"] == IID
        assert row["source"] in audit.SOURCES
    sources = {row["source"] for row in changes}
    assert {"auto", "manual"} <= sources
    final = session.get(SignalState, IID)
    assert changes[-1]["details"]["to"] == f"{final.phase}/{final.stage}"


def test_audit_entries_name_the_actor_and_the_command(session):
    start(session)
    override.request_override(session, IID, "EW", 30, "op1", now=after(5), command_source="tablet")
    entry = audit.list_events(session, IID, event="override_applied")[0]
    assert entry["actor"] == "op1" and entry["source"] == "manual"
    assert entry["details"] == {"phase": "EW", "durationSeconds": 30, "commandSource": "tablet"}


def test_audit_can_be_filtered_and_limited(session):
    start(session)
    controller.tick(session, IID, after(200))
    assert len(audit.list_events(session, IID, limit=3)) == 3
    assert {e["event"] for e in audit.list_events(session, IID, event="phase_change")} == {"phase_change"}
    assert audit.list_events(session, "OTHER") == []
