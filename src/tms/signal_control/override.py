"""Manual override (TMS-F-002).

An operator holds one phase (or an all-red hold) for a set time. The request is accepted and the
current green is cut short at once (within a second), then the signal clears through yellow and
all-red before the requested phase turns green. Requests that break a safety interlock are
rejected with a reason. While in manual mode adaptive plans are stored, not applied.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.common import clock
from tms.common.errors import CommandError, InterlockError
from tms.signal_control import audit
from tms.signal_control.controller import (ADAPTIVE, ALL_RED, GREEN, MANUAL, PED, advance_state,
                                           elapsed_seconds, end_override_state, get_or_create_state)

MIN_PHASE_HOLD = 15       # seconds; long enough to clear the old phase and show the new one
MIN_ALL_RED_HOLD = 5
MAX_HOLD = 300


def request_override(db: Session, intersection_id: str, phase: str, duration: int, actor: str,
                     now: datetime | None = None, command_source: str = "operator-console") -> dict:
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    if phase not in cfg["phases"] and phase != ALL_RED:
        raise CommandError(f"phase must be one of {cfg['phases'] + [ALL_RED]}", code="invalid_phase")
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise CommandError("duration must be a whole number of seconds", code="invalid_duration")
    low = MIN_ALL_RED_HOLD if phase == ALL_RED else MIN_PHASE_HOLD
    if not low <= duration <= MAX_HOLD:
        raise CommandError(f"duration must be between {low} and {MAX_HOLD} seconds", code="invalid_duration")

    state = get_or_create_state(db, intersection_id, now, cfg)
    advance_state(db, state, cfg, now)

    if state.stage == PED:  # safety interlock: minimum pedestrian clearance
        audit.log_event(db, intersection_id, "override_rejected", "manual", actor,
                        {"reason": "pedestrian crossing in progress", "phase": phase}, timestamp=now)
        db.commit()
        raise InterlockError("Pedestrian crossing in progress: minimum pedestrian clearance must finish first")

    state.mode = MANUAL
    state.manual_phase = phase
    state.manual_by = actor
    state.manual_until = now + timedelta(seconds=duration)
    if state.stage == GREEN and state.phase == phase:
        state.stage_duration = max(1, math.ceil((state.manual_until - state.stage_started_at).total_seconds()))
    elif state.stage == GREEN or (state.stage == ALL_RED and state.phase == ALL_RED):
        # cut the current green (or previous hold) short: it ends within one second
        state.stage_duration = max(1, math.ceil(elapsed_seconds(state, now)))
    audit.log_event(db, intersection_id, "override_applied", "manual", actor,
                    {"phase": phase, "durationSeconds": duration, "commandSource": command_source}, timestamp=now)
    advance_state(db, state, cfg, now)
    db.commit()
    return {"status": "applied", "commandId": "CMD-" + uuid.uuid4().hex[:10], "appliedAt": now.isoformat(),
            "mode": MANUAL, "phase": phase, "until": state.manual_until.isoformat()}


def clear_override(db: Session, intersection_id: str, actor: str, now: datetime | None = None,
                   command_source: str = "operator-console") -> dict:
    """Return the intersection to adaptive (automatic) control."""
    now = now or clock.now()
    cfg = config_service.get_intersection_config(db, intersection_id)
    state = get_or_create_state(db, intersection_id, now, cfg)
    advance_state(db, state, cfg, now)
    if state.mode == MANUAL:
        end_override_state(db, state, now, reason=f"cleared by operator via {command_source}", actor=actor,
                           truncate=True)
        advance_state(db, state, cfg, now)
    db.commit()
    return {"status": "applied", "commandId": "CMD-" + uuid.uuid4().hex[:10], "appliedAt": now.isoformat(),
            "mode": ADAPTIVE}
