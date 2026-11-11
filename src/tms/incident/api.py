"""Incident, alert, dispatch and security-alert endpoints (Likhita)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.common import clock
from tms.common.db import get_db
from tms.incident import dispatch as dispatch_mod
from tms.incident import security_monitor, service

router = APIRouter(prefix="/api/v1", tags=["incidents"])
STAFF = (rbac.OPERATOR, rbac.ADMINISTRATOR)


class DispatchIn(BaseModel):
    service: str
    notes: str = Field(default="", max_length=300)


@router.get("/incidents")
def incidents(status: Optional[str] = None, intersectionId: Optional[str] = None, limit: int = Query(100, ge=1, le=500),
              db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role())):
    return service.list_incidents(db, status, intersectionId, limit)


@router.get("/alerts")
def alerts(sinceId: int = Query(0, ge=0), openOnly: bool = False, db: Session = Depends(get_db),
           _: rbac.CurrentUser = Depends(rbac.require_role(*STAFF))):
    return service.list_alerts(db, sinceId, openOnly)


@router.post("/intersections/{intersection_id}/incidents/scan")
def scan(intersection_id: str, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*STAFF))):
    config_service.get_intersection_config(db, intersection_id)
    return [service.incident_view(db, i) for i in service.scan(db, intersection_id, clock.now())]


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge(incident_id: int, db: Session = Depends(get_db), user: rbac.CurrentUser = Depends(rbac.require_role(*STAFF))):
    return service.acknowledge(db, incident_id, user.username, clock.now())


@router.post("/incidents/{incident_id}/resolve")
def resolve(incident_id: int, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*STAFF))):
    return service.resolve(db, incident_id, clock.now())


@router.post("/incidents/{incident_id}/dispatch", status_code=201)
def dispatch(incident_id: int, body: DispatchIn, request: Request, db: Session = Depends(get_db),
             user: rbac.CurrentUser = Depends(rbac.require_role(rbac.OPERATOR))):
    row = dispatch_mod.dispatch(db, incident_id, body.service, user.username, request.app.state.emergency_service,
                                body.notes, clock.now())
    return {"dispatchId": row.id, "service": row.service, "status": row.status, "reference": row.reference}


@router.get("/security/alerts")
def security_alerts(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return security_monitor.list_alerts(db)
