"""Availability of the signal-control service (TMS-NF-002): at least 99.5% a month, not counting
scheduled maintenance windows.

The running service writes a heartbeat about every ``HEARTBEAT_SECONDS``. A heartbeat vouches for the next
interval. Time with no heartbeat (the service was stopped), and time after an unhealthy heartbeat, is downtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.common import clock
from tms.common.errors import CommandError
from tms.infra.models import Heartbeat, MaintenanceWindow

HEARTBEAT_SECONDS = 30
TARGET_PERCENT = 99.5

Interval = tuple[datetime, datetime]


def record_heartbeat(db: Session, now: datetime | None = None, healthy: bool = True, force: bool = False) -> bool:
    """Write a heartbeat unless one was written less than an interval ago. Returns True if one was written."""
    now = now or clock.now()
    last = db.scalar(select(Heartbeat.timestamp).order_by(Heartbeat.id.desc()).limit(1))
    if last is not None and not force and (now - last).total_seconds() < HEARTBEAT_SECONDS - 1 and healthy:
        return False
    db.add(Heartbeat(timestamp=now, healthy=healthy))
    db.commit()
    return True


def add_maintenance_window(db: Session, starts_at: datetime, ends_at: datetime, reason: str = "") -> MaintenanceWindow:
    if ends_at <= starts_at:
        raise CommandError("A maintenance window must end after it starts", code="invalid_window")
    row = MaintenanceWindow(starts_at=starts_at, ends_at=ends_at, reason=reason[:200])
    db.add(row)
    db.commit()
    return row


def _subtract(intervals: list[Interval], holes: list[Interval]) -> list[Interval]:
    result = []
    for start, end in intervals:
        pieces = [(start, end)]
        for hole_start, hole_end in holes:
            next_pieces = []
            for a, b in pieces:
                if hole_end <= a or hole_start >= b:
                    next_pieces.append((a, b))
                    continue
                if hole_start > a:
                    next_pieces.append((a, hole_start))
                if hole_end < b:
                    next_pieces.append((hole_end, b))
            pieces = next_pieces
        result += pieces
    return result


def _clip(start: datetime, end: datetime, low: datetime, high: datetime) -> Interval | None:
    start, end = max(start, low), min(end, high)
    return (start, end) if end > start else None


def availability(db: Session, start: datetime, end: datetime, now: datetime | None = None) -> dict:
    """Availability between ``start`` and ``end`` (capped at ``now``). Observation begins at the first heartbeat."""
    now = now or clock.now()
    end = min(end, now)
    beats = db.scalars(select(Heartbeat).where(Heartbeat.timestamp <= end).order_by(Heartbeat.timestamp)).all()
    if not beats or end <= start:
        return {"availabilityPercent": None, "meetsTarget": None, "note": "no heartbeats recorded for this period"}
    observed_from = max(start, beats[0].timestamp)
    interval = timedelta(seconds=HEARTBEAT_SECONDS)
    down: list[Interval] = []
    for index, beat in enumerate(beats):
        next_time = beats[index + 1].timestamp if index + 1 < len(beats) else end
        covered_until = beat.timestamp + interval if beat.healthy else beat.timestamp
        if next_time > covered_until:
            piece = _clip(covered_until, next_time, observed_from, end)
            if piece:
                down.append(piece)
    maintenance = [p for w in db.scalars(select(MaintenanceWindow)) if (p := _clip(w.starts_at, w.ends_at, observed_from, end))]
    maintenance_seconds = sum((b - a).total_seconds() for a, b in _subtract(maintenance, [])) if maintenance else 0.0
    counted_down = _subtract(down, maintenance)
    downtime = sum((b - a).total_seconds() for a, b in counted_down)
    observed = (end - observed_from).total_seconds()
    in_scope = max(1.0, observed - maintenance_seconds)
    percent = round(100.0 * (1 - downtime / in_scope), 3)
    return {"availabilityPercent": percent, "targetPercent": TARGET_PERCENT, "meetsTarget": percent >= TARGET_PERCENT,
            "observedSeconds": round(observed), "maintenanceSeconds": round(maintenance_seconds),
            "downtimeSeconds": round(downtime),
            "outages": [{"from": a.isoformat(), "to": b.isoformat(), "seconds": round((b - a).total_seconds())}
                        for a, b in counted_down if (b - a).total_seconds() >= 1]}


def month_bounds(month: str) -> Interval:
    try:
        first = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise CommandError("month must look like 2026-10", code="invalid_month") from None
    following = datetime(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return first, following
