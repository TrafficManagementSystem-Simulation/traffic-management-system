"""Incident detection (TMS-F-014): congestion build-up, stalled vehicles and collisions.

``find_incidents`` only reads data and returns what it sees; ``service.scan`` stores new incidents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.detection.models import Detection

RECENT_SECONDS = 60            # window that is checked for a build-up
BASELINE_MINUTES = 15          # what "normal" looked like just before
CONGESTION_MIN_VPM = 20.0      # never call it congestion below this many vehicles per minute
CONGESTION_FACTOR = 2.0        # ... and only when it is this many times the normal rate
HIGH_VPM = 40.0
STALL_SECONDS = 30             # stationary at least this long
STALL_LOOKBACK = 120
COLLISION_LOOKBACK = 60


@dataclass
class Finding:
    kind: str
    severity: str
    approach: str | None = None
    lane: int | None = None
    details: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.kind, self.approach, self.lane)


def _vehicles(db: Session, iid: str, approach: str, start: datetime, end: datetime) -> int:
    """Vehicles seen on ``approach`` in (start, end], from the individual detection events."""
    return int(db.scalar(select(func.coalesce(func.sum(Detection.count), 0)).where(
        Detection.intersection_id == iid, Detection.detection_type == "vehicle", Detection.approach == approach,
        Detection.timestamp > start, Detection.timestamp <= end)) or 0)


def find_incidents(db: Session, iid: str, now: datetime) -> list[Finding]:
    cfg = config_service.get_intersection_config(db, iid)
    found: list[Finding] = []

    # 1. congestion: the recent rate is high and well above the rate just before
    recent_start = now - timedelta(seconds=RECENT_SECONDS)
    base_start = recent_start - timedelta(minutes=BASELINE_MINUTES)
    for approach in sorted(cfg["approaches"]):
        recent = _vehicles(db, iid, approach, recent_start, now) * 60.0 / RECENT_SECONDS
        baseline = _vehicles(db, iid, approach, base_start, recent_start) / BASELINE_MINUTES
        if recent >= CONGESTION_MIN_VPM and (baseline == 0 or recent >= CONGESTION_FACTOR * baseline):
            found.append(Finding("congestion", "high" if recent >= HIGH_VPM else "medium", approach,
                                 details={"vehiclesPerMinute": round(recent, 1), "normalVehiclesPerMinute": round(baseline, 1)}))

    # 2. stalled vehicle: stationary reports spanning STALL_SECONDS in one lane, with nothing moving since
    since = now - timedelta(seconds=STALL_LOOKBACK)
    rows = db.scalars(select(Detection).where(
        Detection.intersection_id == iid, Detection.detection_type == "vehicle", Detection.timestamp >= since,
        Detection.timestamp <= now, Detection.speed_kmh.is_not(None)).order_by(Detection.timestamp)).all()
    lanes: dict[tuple, list[Detection]] = {}
    for row in rows:
        lanes.setdefault((row.approach, row.lane), []).append(row)
    for (approach, lane), events in lanes.items():
        stopped = [e for e in events if e.speed_kmh <= 1]
        if not stopped:
            continue
        first = stopped[0].timestamp
        moving_after = [e for e in events if e.timestamp >= first and e.speed_kmh > 5]
        if stopped[-1].timestamp - first >= timedelta(seconds=STALL_SECONDS) and not moving_after:
            found.append(Finding("stalled_vehicle", "medium", approach, lane,
                                 {"stationarySeconds": int((stopped[-1].timestamp - first).total_seconds())}))

    # 3. collision flagged by the camera analytics
    for row in db.scalars(select(Detection).where(
            Detection.intersection_id == iid, Detection.detection_type == "collision",
            Detection.timestamp >= now - timedelta(seconds=COLLISION_LOOKBACK), Detection.timestamp <= now)):
        found.append(Finding("collision", "high", row.approach, row.lane, {"confidence": row.confidence}))
    return found
