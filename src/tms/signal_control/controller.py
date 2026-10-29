"""Signal controller (TMS-F-001, TMS-F-003): adaptive timing and the signal state machine.

A signal moves through stages: GREEN -> YELLOW -> ALL_RED -> (PED if a pedestrian is waiting)
-> GREEN of the next phase. At the start of every cycle the controller reads the vehicle density
from the Detection module, computes new green times, checks them against the safety limits of
the intersection configuration, and applies them at the next green (the next safe transition).
If validation fails the previous plan is kept and the rejection is logged (UC-01).

All time comes from the ``now`` argument, so tests can run a whole cycle in milliseconds.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.common import clock
from tms.common.errors import TMSError
from tms.detection import counter, pedestrian
from tms.signal_control import audit
from tms.signal_control.models import SignalPlanRecord, SignalState

ADAPTIVE = "adaptive"
MANUAL = "manual"
GREEN, YELLOW, ALL_RED, PED = "GREEN", "YELLOW", "ALL_RED", "PED"
MAX_CYCLE_SECONDS = 180


class PlanValidationError(TMSError):
    status_code = 422
    code = "plan_invalid"


# ---------- plan calculation ----------

def compute_green_times(densities: dict[str, float], cfg: dict) -> dict[str, int]:
    """Split the usable cycle time between phases in proportion to their traffic density.

    Each green stays between ``min_green`` and ``max_green``. With no traffic data the time is
    split equally.
    """
    phases = cfg["phases"]
    low, high = cfg["min_green"], cfg["max_green"]
    available = cfg["cycle_seconds"] - len(phases) * (cfg["yellow"] + cfg["all_red"])
    total = sum(max(0.0, densities.get(p, 0.0)) for p in phases)
    if total <= 0:
        raw = {p: available / len(phases) for p in phases}
    else:
        raw = {p: available * max(0.0, densities.get(p, 0.0)) / total for p in phases}
    green = {p: min(high, max(low, raw[p])) for p in phases}
    for _ in range(12):  # hand the time clamping removed to phases that can still take it
        diff = available - sum(green.values())
        if abs(diff) < 0.5:
            break
        free = [p for p in phases if (diff > 0 and green[p] < high) or (diff < 0 and green[p] > low)]
        if not free:
            break
        share = diff / len(free)
        for p in free:
            green[p] = min(high, max(low, green[p] + share))
    return {p: int(round(green[p])) for p in phases}


def build_plan(cfg: dict, green: dict[str, int]) -> dict:
    return {"green": dict(green), "yellow": cfg["yellow"], "all_red": cfg["all_red"]}


def validate_plan(plan: dict, cfg: dict) -> None:
    """Raise PlanValidationError if the plan breaks the safety minimums or maximums."""
    problems: list[str] = []
    green = plan.get("green") if isinstance(plan, dict) else None
    if not isinstance(green, dict) or set(green) != set(cfg["phases"]):
        problems.append("plan must give a green time for every phase and nothing else")
    else:
        for phase, seconds in green.items():
            if not isinstance(seconds, int) or isinstance(seconds, bool):
                problems.append(f"green for {phase} must be a whole number of seconds")
            elif not cfg["min_green"] <= seconds <= cfg["max_green"]:
                problems.append(f"green for {phase} must be between {cfg['min_green']} and {cfg['max_green']} seconds")
    if not isinstance(plan, dict) or plan.get("yellow", 0) < cfg["yellow"]:
        problems.append(f"yellow must be at least {cfg['yellow']} seconds")
    if not isinstance(plan, dict) or plan.get("all_red", 0) < cfg["all_red"]:
        problems.append(f"all-red must be at least {cfg['all_red']} seconds")
    if not problems:
        cycle = sum(green.values()) + len(green) * (plan["yellow"] + plan["all_red"])
        if cycle > MAX_CYCLE_SECONDS:
            problems.append(f"cycle of {cycle} seconds is longer than {MAX_CYCLE_SECONDS}")
    if problems:
        raise PlanValidationError(problems)


def phase_densities(db: Session, intersection_id: str, cfg: dict) -> dict[str, float]:
    """Vehicles per minute per phase (sum of the approaches that belong to the phase)."""
    result = {p: 0.0 for p in cfg["phases"]}
    for approach, phase in cfg["approaches"].items():
        result[phase] += counter.get_density(db, intersection_id, approach)
    return {p: round(v, 3) for p, v in result.items()}


# ---------- state helpers ----------

def _next_phase(cfg: dict, last: str) -> str:
    phases = cfg["phases"]
    if last not in phases:
        return phases[0]
    return phases[(phases.index(last) + 1) % len(phases)]


def elapsed_seconds(state: SignalState, at: datetime) -> float:
    return (at - state.stage_started_at).total_seconds()


def _stage_end(state: SignalState) -> datetime:
    return state.stage_started_at + timedelta(seconds=state.stage_duration)


def _set_stage(db: Session, state: SignalState, phase: str, stage: str, duration: float, at: datetime,
               source: str, cfg: dict, actor: str | None = None) -> None:
    old = f"{state.phase}/{state.stage}"
    state.phase = phase
    state.stage = stage
    state.stage_started_at = at
    state.stage_duration = max(1, int(math.ceil(duration)))
    if phase in cfg["phases"]:
        state.last_vehicle_phase = phase
    audit.log_event(db, state.intersection_id, "phase_change", source, actor,
                    {"from": old, "to": f"{phase}/{stage}", "durationSeconds": state.stage_duration}, timestamp=at)


def get_or_create_state(db: Session, intersection_id: str, now: datetime, cfg: dict | None = None) -> SignalState:
    state = db.get(SignalState, intersection_id)
    if state is not None:
        return state
    cfg = cfg or config_service.get_intersection_config(db, intersection_id)
    plan = build_plan(cfg, compute_green_times({}, cfg))
    first = cfg["phases"][0]
    state = SignalState(intersection_id=intersection_id, mode=ADAPTIVE, phase="-", stage="-", stage_started_at=now,
                        stage_duration=1, last_vehicle_phase=first, plan=json.dumps(plan), plan_version=1)
    db.add(state)
    _set_stage(db, state, first, GREEN, plan["green"][first], now, "auto", cfg)
    db.flush()
    return state


def _activate_plan(db: Session, state: SignalState, plan: dict, source: str, at: datetime,
                   actor: str | None = None) -> None:
    state.plan = json.dumps(plan)
    state.plan_version += 1
    state.next_plan = None
    db.add(SignalPlanRecord(intersection_id=state.intersection_id, plan=json.dumps(plan), source=source,
                            version=state.plan_version, applied_at=at))
    audit.log_event(db, state.intersection_id, "plan_applied", source, actor,
                    {"plan": plan, "version": state.plan_version}, timestamp=at)


def _compute_and_store(db: Session, state: SignalState, cfg: dict, at: datetime) -> dict | None:
    """Compute a plan from current densities. It waits in ``next_plan`` until the next green starts
    (or until manual override ends)."""
    densities = phase_densities(db, state.intersection_id, cfg)
    plan = build_plan(cfg, compute_green_times(densities, cfg))
    try:
        validate_plan(plan, cfg)
    except PlanValidationError as exc:
        audit.log_event(db, state.intersection_id, "plan_rejected", "auto", None,
                        {"reason": exc.detail, "plan": plan}, timestamp=at)
        return None
    if plan == json.loads(state.plan):
        state.next_plan = None
        return plan
    state.next_plan = json.dumps(plan)
    event = "plan_stored" if state.mode == MANUAL else "plan_computed"
    audit.log_event(db, state.intersection_id, event, "auto", None,
                    {"densities": densities, "plan": plan}, timestamp=at)
    return plan


def _start_green(db: Session, state: SignalState, cfg: dict, phase: str, at: datetime, source: str) -> None:
    if state.mode == ADAPTIVE:
        if phase == cfg["phases"][0]:
            _compute_and_store(db, state, cfg, at)
        if state.next_plan:
            _activate_plan(db, state, json.loads(state.next_plan), "auto", at)
    plan = json.loads(state.plan)
    green = plan["green"].get(phase, cfg["min_green"])
    _set_stage(db, state, phase, GREEN, green, at, source, cfg)


def end_override_state(db: Session, state: SignalState, at: datetime, reason: str, actor: str | None = None,
                       truncate: bool = False) -> None:
    """Leave manual mode. With ``truncate`` the held stage ends now (operator pressed Return to auto)."""
    audit.log_event(db, state.intersection_id, "override_cleared", "manual" if actor else "auto", actor,
                    {"reason": reason, "phase": state.manual_phase}, timestamp=at)
    state.mode = ADAPTIVE
    state.manual_phase = None
    state.manual_until = None
    state.manual_by = None
    if truncate and (state.stage == GREEN or (state.stage == ALL_RED and state.phase == ALL_RED)):
        state.stage_duration = max(1, int(math.ceil(elapsed_seconds(state, at))))


def _transition(db: Session, state: SignalState, cfg: dict, at: datetime) -> None:
    plan = json.loads(state.plan)
    if state.mode == MANUAL and state.manual_until is not None and at >= state.manual_until:
        end_override_state(db, state, at, reason="expired")
    manual = state.mode == MANUAL
    source = "manual" if manual else "auto"
    iid = state.intersection_id

    if state.stage == GREEN:
        _set_stage(db, state, state.phase, YELLOW, plan["yellow"], at, source, cfg)
    elif state.stage == YELLOW:
        _set_stage(db, state, state.phase, ALL_RED, plan["all_red"], at, source, cfg)
    elif state.stage == PED:
        _start_green(db, state, cfg, _next_phase(cfg, state.last_vehicle_phase), at, source)
    else:  # ALL_RED
        if manual:
            remaining = max(1, math.ceil((state.manual_until - at).total_seconds()))
            if state.manual_phase == ALL_RED:
                _set_stage(db, state, ALL_RED, ALL_RED, remaining, at, source, cfg)
            else:
                _set_stage(db, state, state.manual_phase, GREEN, remaining, at, source, cfg)
        elif pedestrian.has_pending(db, iid):
            served = pedestrian.mark_served(db, iid, at)
            _set_stage(db, state, PED, PED, cfg["pedestrian_walk"] + cfg["pedestrian_clearance"], at, source, cfg)
            audit.log_event(db, iid, "pedestrian_served", source, None, {"requests": served}, timestamp=at)
        else:
            _start_green(db, state, cfg, _next_phase(cfg, state.last_vehicle_phase), at, source)


def advance_state(db: Session, state: SignalState, cfg: dict, now: datetime) -> int:
    """Run every stage change that is due up to ``now``. Returns how many happened."""
    changes = 0
    for _ in range(5000):
        if _stage_end(state) > now:
            break
        _transition(db, state, cfg, _stage_end(state))
        changes += 1
    return changes


# ---------- public functions used by other modules and the API ----------

def tick(db: Session, intersection_id: str, now: datetime | None = None) -> SignalState:
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    state = get_or_create_state(db, intersection_id, now, cfg)
    advance_state(db, state, cfg, now)
    db.commit()
    return state


def apply_plan(db: Session, intersection_id: str, plan: dict, source: str = "auto", actor: str | None = None,
               now: datetime | None = None) -> datetime:
    """Validate ``plan`` and make it the active plan. Returns the time it was applied."""
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    validate_plan(plan, cfg)
    state = get_or_create_state(db, intersection_id, now, cfg)
    _activate_plan(db, state, plan, source, now, actor)
    db.commit()
    return now


def recompute_plan(db: Session, intersection_id: str, now: datetime | None = None) -> dict:
    """Compute a plan from the latest densities now (the normal cycle also does this)."""
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    state = get_or_create_state(db, intersection_id, now, cfg)
    densities = phase_densities(db, intersection_id, cfg)
    plan = _compute_and_store(db, state, cfg, now)
    db.commit()
    return {"mode": state.mode, "densities": densities, "plan": plan,
            "appliedAt": "next green" if state.mode == ADAPTIVE else "when manual override ends"}


def view_state(db: Session, intersection_id: str, now: datetime | None = None) -> dict:
    now = now or clock.now()
    state = tick(db, intersection_id, now)
    remaining = max(0.0, (_stage_end(state) - now).total_seconds())
    return {
        "intersectionId": intersection_id,
        "mode": state.mode,
        "phase": state.phase,
        "stage": state.stage,
        "stageStartedAt": state.stage_started_at.isoformat(),
        "stageDurationSeconds": state.stage_duration,
        "secondsRemaining": round(remaining, 1),
        "plan": json.loads(state.plan),
        "planVersion": state.plan_version,
        "nextPlan": json.loads(state.next_plan) if state.next_plan else None,
        "manual": None if state.mode != MANUAL else {
            "phase": state.manual_phase, "until": state.manual_until.isoformat(), "by": state.manual_by},
        "pedestriansWaiting": len(pedestrian.get_pedestrian_requests(db, intersection_id)),
    }
