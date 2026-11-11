"""Emergency dispatch from an incident (TMS-F-016).

The external service sits behind a small interface so the real police, ambulance and fire systems can
be plugged in. The default ``LoopbackEmergencyService`` acknowledges at once (used for the demo).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from tms.common import clock
from tms.common.errors import CommandError, NotFoundError, TMSError
from tms.incident.models import Dispatch, Incident

SERVICES = ("police", "ambulance", "fire")


class ServiceUnavailable(TMSError):
    status_code = 502
    code = "service_unavailable"


class EmergencyService(Protocol):
    def notify(self, service: str, message: str) -> str:
        """Send the notice. Returns the reference the service acknowledged with; raises if it did not."""


class LoopbackEmergencyService:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def notify(self, service: str, message: str) -> str:
        self.sent.append((service, message))
        return "ACK-" + uuid.uuid4().hex[:8].upper()


def dispatch(db: Session, incident_id: int, service: str, actor: str, client: EmergencyService,
             notes: str = "", now: datetime | None = None) -> Dispatch:
    now = now or clock.now()
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise NotFoundError(f"Incident {incident_id} does not exist", code="incident_not_found")
    if service not in SERVICES:
        raise CommandError(f"service must be one of {list(SERVICES)}", code="invalid_service")
    if len(notes) > 300:
        raise CommandError("notes can be at most 300 characters", code="invalid_notes")
    message = (f"{incident.kind} ({incident.severity}) at {incident.intersection_id}"
               f"{' approach ' + incident.approach if incident.approach else ''}; {notes}".strip("; "))
    try:
        reference = client.notify(service, message)
        row = Dispatch(incident_id=incident_id, service=service, requested_by=actor, requested_at=now,
                       status="acknowledged", reference=reference, notes=notes)
    except Exception as exc:  # noqa: BLE001 - any failure of the outside system is recorded, then reported
        row = Dispatch(incident_id=incident_id, service=service, requested_by=actor, requested_at=now,
                       status="failed", reference=None, notes=notes)
        db.add(row)
        _log(db, actor, row, incident, f"failed: {exc}")
        db.commit()
        raise ServiceUnavailable(f"The {service} service did not acknowledge the notice; it was logged") from exc
    db.add(row)
    _log(db, actor, row, incident, f"acknowledged {reference}")
    db.commit()
    return row


def _log(db: Session, actor: str, row: Dispatch, incident: Incident, outcome: str) -> None:
    from tms.admin import rbac

    rbac.log_security(db, actor, "emergency_dispatch", f"incident={incident.id} service={row.service} {outcome}")
