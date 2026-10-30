"""Traffic reports (TMS-F-017): volume, incidents and signal performance for each intersection."""
from __future__ import annotations

import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import config_service
from tms.common import clock
from tms.common.db import Intersection
from tms.common.errors import CommandError
from tms.detection.models import TrafficCount
from tms.signal_control.models import AuditLog, SignalPlanRecord

PERIODS = ("daily", "weekly", "monthly")


def period_containing(period: str, day: datetime) -> tuple[datetime, datetime]:
    """The whole day, week (Monday to Sunday) or month that contains ``day``."""
    midnight = datetime(day.year, day.month, day.day)
    if period == "daily":
        return midnight, midnight + timedelta(days=1)
    if period == "weekly":
        start = midnight - timedelta(days=midnight.weekday())
        return start, start + timedelta(days=7)
    if period == "monthly":
        start = datetime(day.year, day.month, 1)
        return start, datetime(day.year + (day.month == 12), day.month % 12 + 1, 1)
    raise CommandError(f"period must be one of {list(PERIODS)}", code="invalid_period")


def last_completed(period: str, now: datetime) -> tuple[datetime, datetime]:
    start, _ = period_containing(period, now)                 # the current period began here
    return period_containing(period, start - timedelta(days=1))


def _volume(db: Session, iid: str, start: datetime, end: datetime) -> dict:
    rows = db.scalars(select(TrafficCount).where(TrafficCount.intersection_id == iid,
                                                 TrafficCount.interval_start >= start,
                                                 TrafficCount.interval_start < end)).all()
    by_approach, by_class, by_interval = Counter(), Counter(), Counter()
    for r in rows:
        by_approach[r.approach] += r.count
        by_class[r.vehicle_class] += r.count
        by_interval[r.interval_start] += r.count
    peak = max(by_interval.items(), key=lambda item: item[1], default=None)
    return {"totalVehicles": sum(by_approach.values()), "byApproach": dict(sorted(by_approach.items())),
            "byClass": dict(sorted(by_class.items())),
            "peakInterval": {"start": peak[0].isoformat(), "vehicles": peak[1]} if peak else None}


def _incidents(db: Session, iid: str, start: datetime, end: datetime) -> dict:
    try:
        from tms.incident.models import Dispatch, Incident
    except ModuleNotFoundError:                                # the incident module is not part of this build
        return {"total": 0, "byType": {}, "bySeverity": {}, "dispatches": 0}
    rows = db.scalars(select(Incident).where(Incident.intersection_id == iid, Incident.detected_at >= start,
                                             Incident.detected_at < end)).all()
    ids = [r.id for r in rows]
    dispatches = db.scalars(select(Dispatch).where(Dispatch.incident_id.in_(ids))).all() if ids else []
    return {"total": len(rows), "byType": dict(sorted(Counter(r.kind for r in rows).items())),
            "bySeverity": dict(sorted(Counter(r.severity for r in rows).items())), "dispatches": len(dispatches)}


def _signals(db: Session, iid: str, start: datetime, end: datetime) -> dict:
    events = Counter(e for e in db.scalars(select(AuditLog.event).where(
        AuditLog.intersection_id == iid, AuditLog.timestamp >= start, AuditLog.timestamp < end)))
    plans = db.scalars(select(SignalPlanRecord).where(SignalPlanRecord.intersection_id == iid,
                                                      SignalPlanRecord.applied_at >= start,
                                                      SignalPlanRecord.applied_at < end)).all()
    green_total, green_count, cycles = Counter(), Counter(), []
    for record in plans:
        plan = json.loads(record.plan)
        for phase, seconds in plan["green"].items():
            green_total[phase] += seconds
            green_count[phase] += 1
        cycles.append(sum(plan["green"].values()) + len(plan["green"]) * (plan["yellow"] + plan["all_red"]))
    return {"phaseChanges": events["phase_change"], "plansApplied": events["plan_applied"],
            "plansRejected": events["plan_rejected"], "overrides": events["override_applied"],
            "preemptions": events["preemption_applied"], "pedestriansServed": events["pedestrian_served"],
            "averageGreenSeconds": {p: round(green_total[p] / green_count[p], 1) for p in sorted(green_total)},
            "averageCycleSeconds": round(sum(cycles) / len(cycles), 1) if cycles else None}


def build(db: Session, period: str, start: datetime, end: datetime, now: datetime | None = None) -> dict:
    sections = []
    for row in db.scalars(select(Intersection).order_by(Intersection.id)):
        sections.append({"id": row.id, "name": row.name, "volume": _volume(db, row.id, start, end),
                         "incidents": _incidents(db, row.id, start, end), "signalPerformance": _signals(db, row.id, start, end)})
    return {"period": period, "periodStart": start.isoformat(), "periodEnd": end.isoformat(),
            "generatedAt": (now or clock.now()).isoformat(), "intersections": sections,
            "totals": {"vehicles": sum(s["volume"]["totalVehicles"] for s in sections),
                       "incidents": sum(s["incidents"]["total"] for s in sections)}}


def to_csv(report: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["period", "periodStart", "periodEnd", "intersection", "section", "metric", "value"])

    def flatten(prefix: str, value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield from flatten(f"{prefix}.{key}" if prefix else key, item)
        else:
            yield prefix, "" if value is None else value

    for item in report["intersections"]:
        for section in ("volume", "incidents", "signalPerformance"):
            for metric, value in flatten("", item[section]):
                writer.writerow([report["period"], report["periodStart"], report["periodEnd"], item["id"], section, metric, value])
    return out.getvalue()
