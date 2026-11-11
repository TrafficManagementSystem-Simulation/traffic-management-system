"""Anomalous command patterns (PRJ-SR-005): rapid repeated overrides, off-hours administrator access
and repeated failed sign-ins raise a ``security_alert`` in the security log.

``scan`` runs about once a second (see main.py), so an alert appears well inside the 60 second limit.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import rbac
from tms.admin.models import SecurityLog
from tms.common import clock
from tms.signal_control.models import AuditLog

OVERRIDE_LIMIT, OVERRIDE_WINDOW = 5, 60          # this many overrides by one person in 60 seconds
FAILED_LOGIN_LIMIT, FAILED_LOGIN_WINDOW = 5, 60
QUIET_PERIOD = timedelta(minutes=5)              # the same alert is not repeated within this time


def _hours(spec: str) -> tuple[int, int]:
    start, end = spec.split("-")
    return int(start.split(":")[0]) * 60 + int(start.split(":")[1]), int(end.split(":")[0]) * 60 + int(end.split(":")[1])


def is_off_hours(moment: datetime, spec: str) -> bool:
    start, end = _hours(spec)
    minute = moment.hour * 60 + moment.minute
    return not (start <= minute < end) if start < end else not (minute >= start or minute < end)


def _already_alerted(db: Session, kind: str, who: str | None, now: datetime) -> bool:
    for row in db.scalars(select(SecurityLog).where(SecurityLog.event == "security_alert",
                                                     SecurityLog.timestamp >= now - QUIET_PERIOD)):
        info = json.loads(row.details)
        if info.get("type") == kind and info.get("user") == who:
            return True
    return False


def _alert(db: Session, kind: str, who: str | None, now: datetime, text: str, **extra) -> dict:
    rbac.log_security(db, who, "security_alert", json.dumps({"type": kind, "user": who, "message": text, **extra}))
    return {"type": kind, "user": who, "message": text}


def scan(db: Session, now: datetime | None = None, admin_hours: str = "06:00-22:00") -> list[dict]:
    now = now or clock.now()
    raised: list[dict] = []

    since = now - timedelta(seconds=OVERRIDE_WINDOW)
    overrides = Counter(r.actor for r in db.scalars(select(AuditLog).where(
        AuditLog.event == "override_applied", AuditLog.timestamp >= since, AuditLog.timestamp <= now)))
    for who, count in overrides.items():
        if count >= OVERRIDE_LIMIT and not _already_alerted(db, "rapid_overrides", who, now):
            raised.append(_alert(db, "rapid_overrides", who, now,
                                 f"{count} signal overrides by {who} in {OVERRIDE_WINDOW} seconds", count=count))

    since = now - timedelta(seconds=FAILED_LOGIN_WINDOW)
    failures = Counter(r.username for r in db.scalars(select(SecurityLog).where(
        SecurityLog.event == "login_failed", SecurityLog.timestamp >= since, SecurityLog.timestamp <= now)))
    for who, count in failures.items():
        if count >= FAILED_LOGIN_LIMIT and not _already_alerted(db, "repeated_failed_logins", who, now):
            raised.append(_alert(db, "repeated_failed_logins", who, now,
                                 f"{count} failed sign-ins for {who} in {FAILED_LOGIN_WINDOW} seconds", count=count))

    window = now - timedelta(minutes=5)
    for row in db.scalars(select(SecurityLog).where(SecurityLog.event == "login_ok", SecurityLog.timestamp >= window,
                                                     SecurityLog.timestamp <= now)):
        if "role=Administrator" in row.details and is_off_hours(row.timestamp, admin_hours) \
                and not _already_alerted(db, "off_hours_admin_access", row.username, now):
            raised.append(_alert(db, "off_hours_admin_access", row.username, now,
                                 f"Administrator {row.username} signed in at {row.timestamp:%H:%M} UTC, outside {admin_hours}"))
    return raised


def list_alerts(db: Session, limit: int = 100) -> list[dict]:
    rows = db.scalars(select(SecurityLog).where(SecurityLog.event == "security_alert")
                      .order_by(SecurityLog.id.desc()).limit(limit)).all()
    return [{"id": r.id, "timestamp": r.timestamp.isoformat(), **json.loads(r.details)} for r in rows]
