"""Intersection configuration (TMS-F-019): validated, versioned, applied without a restart.

Other modules call ``get_intersection_config(db, intersection_id)`` every time they need a
setting, so a saved change is used on the very next control step.
"""
from __future__ import annotations

import copy
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin.models import IntersectionConfigHistory
from tms.common import clock
from tms.common.config import DEFAULT_INTERSECTION_CONFIG
from tms.common.db import Intersection
from tms.common.errors import CommandError, NotFoundError, ValidationFailure

# key -> (minimum, maximum) for plain integer settings
INT_LIMITS: dict[str, tuple[int, int]] = {
    "cycle_seconds": (40, 180),
    "min_green": (5, 30),
    "max_green": (10, 120),
    "yellow": (3, 6),
    "all_red": (1, 5),
    "pedestrian_walk": (4, 20),
    "pedestrian_clearance": (5, 40),
    "count_interval_seconds": (10, 900),
    "density_window_minutes": (1, 30),
}

# latitude/longitude bounds
LAT_LIMITS = (-90.0, 90.0)
LON_LIMITS = (-180.0, 180.0)


def validate_config(config: dict) -> dict:
    """Return a cleaned copy of ``config`` or raise ValidationFailure listing every problem."""
    problems: list[str] = []
    unknown = sorted(set(config) - set(DEFAULT_INTERSECTION_CONFIG))
    if unknown:
        problems.append(f"Unknown settings: {', '.join(unknown)}")
    cfg = copy.deepcopy(config)

    for key, (low, high) in INT_LIMITS.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append(f"{key} must be a whole number")
        elif not low <= value <= high:
            problems.append(f"{key} must be between {low} and {high}")

    # latitude/longitude validation
    lat = cfg.get("latitude")
    if lat is not None:
        if isinstance(lat, bool) or not isinstance(lat, (int, float)):
            problems.append("latitude must be a number")
        elif not LAT_LIMITS[0] <= lat <= LAT_LIMITS[1]:
            problems.append(f"latitude must be between {LAT_LIMITS[0]} and {LAT_LIMITS[1]}")

    lon = cfg.get("longitude")
    if lon is not None:
        if isinstance(lon, bool) or not isinstance(lon, (int, float)):
            problems.append("longitude must be a number")
        elif not LON_LIMITS[0] <= lon <= LON_LIMITS[1]:
            problems.append(f"longitude must be between {LON_LIMITS[0]} and {LON_LIMITS[1]}")

    phases = cfg.get("phases")
    if not isinstance(phases, list) or len(phases) < 2 or len(set(phases)) != len(phases) \
            or not all(isinstance(p, str) and p for p in phases):
        problems.append("phases must be a list of at least two different names")
        phases = []
    approaches = cfg.get("approaches")
    if not isinstance(approaches, dict) or not approaches:
        problems.append("approaches must map each approach (for example N) to a phase")
    elif phases:
        bad = [a for a, p in approaches.items() if p not in phases]
        if bad:
            problems.append(f"approaches {bad} point to a phase that is not in phases")
        missing = [p for p in phases if p not in approaches.values()]
        if missing:
            problems.append(f"phases {missing} have no approach")

    if not problems and phases:
        n = len(phases)
        lost = n * (cfg["yellow"] + cfg["all_red"])
        if cfg["max_green"] < cfg["min_green"]:
            problems.append("max_green must not be smaller than min_green")
        elif cfg["cycle_seconds"] < n * cfg["min_green"] + lost:
            problems.append("cycle_seconds is too short for the minimum greens, yellow and all-red")
        elif cfg["cycle_seconds"] > n * cfg["max_green"] + lost:
            problems.append("cycle_seconds is longer than the maximum greens allow")

    if problems:
        raise ValidationFailure(problems)
    return cfg


def _row(db: Session, intersection_id: str) -> Intersection:
    row = db.get(Intersection, intersection_id)
    if row is None:
        raise NotFoundError(f"Intersection '{intersection_id}' does not exist", code="intersection_not_found")
    return row


def _merged(row: Intersection) -> dict:
    cfg = copy.deepcopy(DEFAULT_INTERSECTION_CONFIG)
    cfg.update(json.loads(row.config or "{}"))
    return cfg


def get_intersection_config(db: Session, intersection_id: str) -> dict:
    """Current configuration (defaults filled in), plus its ``version``."""
    row = _row(db, intersection_id)
    cfg = _merged(row)
    cfg["version"] = row.version
    return cfg


def list_intersections(db: Session) -> list[dict]:
    rows = db.scalars(select(Intersection).order_by(Intersection.id)).all()
    return [{"id": r.id, "name": r.name, "version": r.version} for r in rows]


def create_intersection(db: Session, intersection_id: str, name: str, config: dict | None = None,
                        actor: str | None = None) -> dict:
    intersection_id = intersection_id.strip()
    if not intersection_id or len(intersection_id) > 40 or " " in intersection_id:
        raise CommandError("Intersection id must be 1 to 40 characters with no spaces", code="invalid_intersection")
    if db.get(Intersection, intersection_id) is not None:
        raise CommandError(f"Intersection '{intersection_id}' already exists", code="intersection_exists", status_code=409)
    merged = copy.deepcopy(DEFAULT_INTERSECTION_CONFIG)
    merged.update(config or {})
    cleaned = validate_config(merged)
    db.add(Intersection(id=intersection_id, name=name.strip() or intersection_id, config=json.dumps(cleaned), version=1))
    db.add(IntersectionConfigHistory(intersection_id=intersection_id, version=1, config=json.dumps(cleaned),
                                     changed_by=actor, changed_at=clock.now()))
    db.commit()
    return get_intersection_config(db, intersection_id)


def update_intersection_config(db: Session, intersection_id: str, changes: dict,
                               actor: str | None = None) -> dict:
    """Validate, bump the version, keep history. Takes effect on the next control step."""
    row = _row(db, intersection_id)
    merged = _merged(row)
    merged.update(changes)
    cleaned = validate_config(merged)
    row.config = json.dumps(cleaned)
    row.version += 1
    db.add(IntersectionConfigHistory(intersection_id=intersection_id, version=row.version,
                                     config=json.dumps(cleaned), changed_by=actor, changed_at=clock.now()))
    db.commit()
    return get_intersection_config(db, intersection_id)


def config_history(db: Session, intersection_id: str) -> list[dict]:
    _row(db, intersection_id)
    rows = db.scalars(
        select(IntersectionConfigHistory)
        .where(IntersectionConfigHistory.intersection_id == intersection_id)
        .order_by(IntersectionConfigHistory.version.desc())
    ).all()
    return [{"version": r.version, "changedBy": r.changed_by, "changedAt": r.changed_at.isoformat(),
             "config": json.loads(r.config)} for r in rows]
