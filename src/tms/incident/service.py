"""Stores incidents and raises operator alerts (TMS-F-014, TMS-F-015)."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.common import clock
from tms.common.db import Intersection
from tms.common.errors import CommandError, NotFoundError
from tms.incident import detector
from tms.incident.models import Alert, Dispatch, Incident


def _where(incident: Incident, name: str) -> str:
    place = f"{name} ({incident.intersection_id})"
    if incident.approach:
        place += f", {incident.approach} approach"
    if incident.lane:
        place += f", lane {incident.lane}"
    return place


def scan(db: Session, intersection_id: str, now: datetime | None = None) -> list[Incident]:
    """Look for incidents; each new one gets an alert at once. Returns the new incidents."""
    now = now or clock.now()
    name = db.get(Intersection, intersection_id).name
    open_keys = {(i.kind, i.approach, i.lane) for i in db.scalars(select(Incident).where(
        Incident.intersection_id == intersection_id, Incident.status != "resolved"))}
    created = []
    for finding in detector.find_incidents(db, intersection_id, now):
        if finding.key in open_keys:
            continue
        incident = Incident(intersection_id=intersection_id, kind=finding.kind, severity=finding.severity,
                            approach=finding.approach, lane=finding.lane, detected_at=now,
                            details=json.dumps(finding.details))
        db.add(incident)
        db.flush()
        db.add(Alert(incident_id=incident.id, created_at=now,
                     message=f"{finding.severity.upper()} {finding.kind.replace('_', ' ')} at {_where(incident, name)}"))
        created.append(incident)
        open_keys.add(finding.key)
    db.commit()
    return created


def incident_view(db: Session, incident: Incident) -> dict:
    dispatches = db.scalars(select(Dispatch).where(Dispatch.incident_id == incident.id).order_by(Dispatch.id)).all()
    return {"id": incident.id, "intersectionId": incident.intersection_id, "type": incident.kind,
            "severity": incident.severity, "approach": incident.approach, "lane": incident.lane,
            "detectedAt": incident.detected_at.isoformat(), "status": incident.status,
            "details": json.loads(incident.details),
            "resolvedAt": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "dispatches": [{"id": d.id, "service": d.service, "status": d.status, "reference": d.reference,
                            "requestedBy": d.requested_by, "requestedAt": d.requested_at.isoformat()} for d in dispatches]}


def list_incidents(db: Session, status: str | None = None, intersection_id: str | None = None,
                   limit: int = 100) -> list[dict]:
    query = select(Incident)
    if status:
        query = query.where(Incident.status == status)
    if intersection_id:
        query = query.where(Incident.intersection_id == intersection_id)
    return [incident_view(db, i) for i in db.scalars(query.order_by(Incident.id.desc()).limit(limit))]


def list_alerts(db: Session, since_id: int = 0, unacknowledged_only: bool = False) -> list[dict]:
    query = select(Alert).where(Alert.id > since_id)
    if unacknowledged_only:
        query = query.where(Alert.acknowledged_at.is_(None))
    rows = []
    for alert in db.scalars(query.order_by(Alert.id)):
        incident = db.get(Incident, alert.incident_id)
        rows.append({"id": alert.id, "incidentId": alert.incident_id, "createdAt": alert.created_at.isoformat(),
                     "message": alert.message, "type": incident.kind, "severity": incident.severity,
                     "intersectionId": incident.intersection_id, "approach": incident.approach,
                     "acknowledgedBy": alert.acknowledged_by})
    return rows


def _incident(db: Session, incident_id: int) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise NotFoundError(f"Incident {incident_id} does not exist", code="incident_not_found")
    return incident


def acknowledge(db: Session, incident_id: int, actor: str, now: datetime | None = None) -> dict:
    now = now or clock.now()
    incident = _incident(db, incident_id)
    if incident.status == "resolved":
        raise CommandError("Incident is already resolved", code="already_resolved", status_code=409)
    incident.status = "acknowledged"
    for alert in db.scalars(select(Alert).where(Alert.incident_id == incident_id)):
        alert.acknowledged_by, alert.acknowledged_at = alert.acknowledged_by or actor, alert.acknowledged_at or now
    db.commit()
    return incident_view(db, incident)


def resolve(db: Session, incident_id: int, now: datetime | None = None) -> dict:
    incident = _incident(db, incident_id)
    incident.status, incident.resolved_at = "resolved", now or clock.now()
    db.commit()
    return incident_view(db, incident)
