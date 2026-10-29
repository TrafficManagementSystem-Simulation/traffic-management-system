"""Audit log (TMS-F-003). Every signal state change is written here with time, intersection,
and what triggered it (auto, manual or preemption)."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.common import clock
from tms.signal_control.models import AuditLog

SOURCES = ("auto", "manual", "preemption")


def log_event(db: Session, intersection_id: str, event: str, source: str = "auto", actor: str | None = None,
              details: dict | None = None, timestamp: datetime | None = None, commit: bool = False) -> AuditLog:
    """Add one audit line. Callers inside a control step leave ``commit`` False and commit once."""
    row = AuditLog(timestamp=timestamp or clock.now(), intersection_id=intersection_id, event=event,
                   source=source, actor=actor, details=json.dumps(details or {}, default=str))
    db.add(row)
    if commit:
        db.commit()
    return row


def list_events(db: Session, intersection_id: str | None = None, event: str | None = None,
                limit: int = 200) -> list[dict]:
    db.flush()
    query = select(AuditLog)
    if intersection_id:
        query = query.where(AuditLog.intersection_id == intersection_id)
    if event:
        query = query.where(AuditLog.event == event)
    rows = db.scalars(query.order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"id": r.id, "timestamp": r.timestamp.isoformat(), "intersectionId": r.intersection_id,
             "event": r.event, "source": r.source, "actor": r.actor, "details": json.loads(r.details)}
            for r in rows]


def count_events(db: Session, intersection_id: str, event: str) -> int:
    db.flush()
    return len([1 for _ in db.scalars(select(AuditLog.id).where(
        AuditLog.intersection_id == intersection_id, AuditLog.event == event))])
