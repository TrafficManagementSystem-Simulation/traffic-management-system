"""Signal control endpoints (Manoj). POST .../signal-command follows SAD section 4.3."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.common import clock
from tms.common.db import get_db
from tms.common.errors import CommandError
from tms.signal_control import audit, controller, override

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
                   user: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR))):
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
         _: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR, rbac.ADMINISTRATOR))):
    config_service.get_intersection_config(db, intersection_id)
    return controller.view_state(db, intersection_id, clock.now())


@router.post("/{intersection_id}/adaptive/recompute")
def recompute(intersection_id: str, db: Session = Depends(get_db),
              _: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR, rbac.ADMINISTRATOR))):
    config_service.get_intersection_config(db, intersection_id)
    return controller.recompute_plan(db, intersection_id, clock.now())


@router.get("/{intersection_id}/audit-log")
def audit_log(intersection_id: str, event: str | None = None, limit: int = Query(100, ge=1, le=1000),
              db: Session = Depends(get_db),
              _: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR, rbac.ADMINISTRATOR))):
    config_service.get_intersection_config(db, intersection_id)
    return audit.list_events(db, intersection_id, event=event, limit=limit)
