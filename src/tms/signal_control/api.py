"""Signal control endpoints (Manoj). POST .../signal-command follows SAD section 4.3."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.common import clock
from tms.common.db import get_db
from tms.common.errors import AuthError, CommandError, ForbiddenError
from tms.signal_control import audit, controller, coordination, override, preemption

router = APIRouter(prefix="/api/v1/intersections", tags=["signal-control"])


class SignalCommand(BaseModel):
    mode: str                              # "manual" or "auto"
    phase: Optional[str] = None            # required for manual: a phase name or ALL_RED
    duration: Optional[int] = None         # seconds to hold, required for manual
    commandSource: str = "operator-console"


@router.get("/{intersection_id}/signal-state")
def signal_state(intersection_id: str, db: Session = Depends(get_db),
                 _: rbac.CurrentUser = Depends(rbac.require_role())):
    config_service.get_intersection_config(db, intersection_id)
    return controller.view_state(db, intersection_id, clock.now())


@router.post("/{intersection_id}/signal-command")
def signal_command(intersection_id: str, body: SignalCommand, db: Session = Depends(get_db),
                   user: rbac.CurrentUser = Depends(rbac.require_mfa)):
    config_service.get_intersection_config(db, intersection_id)
    if body.mode == "manual":
        if not body.phase or body.duration is None:
            raise CommandError("manual mode needs phase and duration", code="invalid_command")
        return override.request_override(db, intersection_id, body.phase, body.duration, user.username,
                                         clock.now(), body.commandSource)
    if body.mode == "auto":
        return override.clear_override(db, intersection_id, user.username, clock.now(), body.commandSource)
    raise CommandError("mode must be 'manual' or 'auto'", code="invalid_command")


@router.post("/{intersection_id}/signal-control/tick")
def tick(intersection_id: str, db: Session = Depends(get_db),
         _: rbac.CurrentUser = Depends(rbac.require_mfa)):
    config_service.get_intersection_config(db, intersection_id)
    return controller.view_state(db, intersection_id, clock.now())


@router.post("/{intersection_id}/adaptive/recompute")
def recompute(intersection_id: str, db: Session = Depends(get_db),
              _: rbac.CurrentUser = Depends(rbac.require_mfa)):
    config_service.get_intersection_config(db, intersection_id)
    return controller.recompute_plan(db, intersection_id, clock.now())


@router.get("/{intersection_id}/audit-log")
def audit_log(intersection_id: str, event: str | None = None, limit: int = Query(100, ge=1, le=1000),
              db: Session = Depends(get_db),
              _: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR, rbac.ADMINISTRATOR))):
    config_service.get_intersection_config(db, intersection_id)
    return audit.list_events(db, intersection_id, event=event, limit=limit)


# ---------- emergency-vehicle preemption (TMS-F-004) ----------

class PreemptionIn(BaseModel):
    approach: str
    vehicleId: str
    holdSeconds: int = preemption.DEFAULT_HOLD


def require_preemption_key(request: Request, x_preemption_key: str | None = Header(default=None)) -> None:
    """The preemption channel is secured with its own key (401 missing, 403 wrong)."""
    if not x_preemption_key:
        raise AuthError("Missing X-Preemption-Key header")
    if x_preemption_key != request.app.state.settings.preemption_key:
        raise ForbiddenError("Invalid preemption key")


@router.post("/{intersection_id}/preemption", status_code=201)
def preempt(intersection_id: str, body: PreemptionIn, db: Session = Depends(get_db),
            _: None = Depends(require_preemption_key)):
    config_service.get_intersection_config(db, intersection_id)
    return preemption.request_preemption(db, intersection_id, body.approach, body.vehicleId, body.holdSeconds,
                                         clock.now())


@router.post("/{intersection_id}/preemption/clear")
def preempt_clear(intersection_id: str, vehicleId: str, db: Session = Depends(get_db),
                  _: None = Depends(require_preemption_key)):
    config_service.get_intersection_config(db, intersection_id)
    return preemption.clear_preemption(db, intersection_id, vehicleId, clock.now())


# ---------- green-wave coordination (TMS-F-005) ----------

@router.post("/corridors/green-wave")
def green_wave(corridor: dict, _: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR, rbac.ADMINISTRATOR))):
    offsets = coordination.compute_offsets(corridor)
    return {"offsets": offsets, "stopsWithOffsets": coordination.platoon_stops(corridor, [o["offsetSeconds"] for o in offsets]),
            "stopsWithoutOffsets": coordination.platoon_stops(corridor, [0.0] * len(offsets))}
