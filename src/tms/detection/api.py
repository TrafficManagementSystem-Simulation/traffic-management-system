"""Detection endpoints (Likhita). POST /api/v1/detections follows SAD section 4.3.

Deviation recorded in docs/deviations.md: the SAD body has no lane or approach, but the SRS needs
counts per lane, so ``approach`` and ``lane`` (and optional ``features``) were added.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

import base64
import binascii

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.common import clock
from tms.common.db import get_db
from tms.common.errors import AuthError, ForbiddenError, ValidationFailure
from tms.detection import counter, evidence, pedestrian
from tms.detection.classifier import VehicleFeatures, classify_vehicle
from tms.detection.models import Detection

router = APIRouter(prefix="/api/v1", tags=["detection"])


class VehicleFeaturesIn(BaseModel):
    length_m: float = Field(gt=0, le=30)
    width_m: float = Field(gt=0, le=5)
    height_m: float = Field(gt=0, le=6)
    has_windows: bool = False


class DetectionIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    intersectionId: str = Field(min_length=1, max_length=40)
    timestamp: datetime
    sourceId: str = Field(min_length=1, max_length=60)
    detectionType: Literal["vehicle", "pedestrian", "collision"]
    vehicle_class: Optional[Literal["car", "bus", "truck", "two_wheeler"]] = Field(default=None, alias="class")
    count: int = Field(default=1, ge=1, le=500)
    confidence: float = Field(ge=0.0, le=1.0)
    approach: Optional[str] = Field(default=None, max_length=10)
    lane: Optional[int] = Field(default=None, ge=1, le=8)
    features: Optional[VehicleFeaturesIn] = None
    speedKmh: Optional[float] = Field(default=None, ge=0, le=250)   # 0 = stationary, used for stalled-vehicle detection

    @model_validator(mode="after")
    def _vehicle_needs_location_and_class(self):
        if self.detectionType == "vehicle":
            if not self.approach or self.lane is None:
                raise ValueError("vehicle detections need approach and lane")
            if self.vehicle_class is None and self.features is None:
                raise ValueError("vehicle detections need class or features")
        return self


def require_sensor_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Sensors authenticate with a shared key (401 missing, 403 wrong)."""
    expected = request.app.state.settings.sensor_api_key
    if not x_api_key:
        raise AuthError("Missing X-API-Key header")
    if x_api_key != expected:
        raise ForbiddenError("Invalid sensor key")


def ingest_detection(db: Session, body: DetectionIn) -> str:
    cfg = config_service.get_intersection_config(db, body.intersectionId)  # 404 if unknown
    stamp = clock.to_naive_utc(body.timestamp)
    event_id = "EVT-" + uuid.uuid4().hex[:12]
    vehicle_class = body.vehicle_class
    if body.detectionType == "vehicle":
        if body.approach not in cfg["approaches"]:
            raise ValidationFailure(f"approach must be one of {sorted(cfg['approaches'])}")
        if vehicle_class is None:
            f = body.features
            vehicle_class = classify_vehicle(VehicleFeatures(f.length_m, f.width_m, f.height_m, f.has_windows))
        counter.record_count(db, body.intersectionId, body.approach, body.lane, stamp, vehicle_class, body.count)
    elif body.detectionType == "pedestrian":
        pedestrian.request_crossing(db, body.intersectionId, stamp, crosswalk=body.approach)
    else:  # collision flagged by the camera analytics: kept as a detection row, the incident module reads it
        if body.approach is not None and body.approach not in cfg["approaches"]:
            raise ValidationFailure(f"approach must be one of {sorted(cfg['approaches'])}")
    db.add(Detection(event_id=event_id, intersection_id=body.intersectionId, timestamp=stamp,
                     source_id=body.sourceId, detection_type=body.detectionType, vehicle_class=vehicle_class,
                     count=body.count, confidence=body.confidence, approach=body.approach, lane=body.lane, speed_kmh=body.speedKmh))
    db.commit()
    return event_id


@router.post("/detections", status_code=201)
def post_detection(body: DetectionIn, db: Session = Depends(get_db), _: None = Depends(require_sensor_key)):
    event_id = ingest_detection(db, body)
    return {"status": "accepted", "eventId": event_id}


@router.get("/detections/counts")
def counts(intersectionId: str, approach: str | None = None, lane: int | None = None,
           limit: int = Query(200, ge=1, le=2000), db: Session = Depends(get_db),
           _: rbac.CurrentUser = Depends(rbac.require_role())):
    config_service.get_intersection_config(db, intersectionId)
    rows = counter.get_counts(db, intersectionId, approach=approach, lane=lane)
    return rows[-limit:]


@router.get("/intersections/{intersection_id}/density")
def density(intersection_id: str, db: Session = Depends(get_db),
            _: rbac.CurrentUser = Depends(rbac.require_role())):
    config_service.get_intersection_config(db, intersection_id)
    return {"intersectionId": intersection_id, "vehiclesPerMinute": counter.approach_densities(db, intersection_id)}


@router.get("/intersections/{intersection_id}/pedestrian-requests")
def pedestrian_requests(intersection_id: str, db: Session = Depends(get_db),
                        _: rbac.CurrentUser = Depends(rbac.require_role())):
    config_service.get_intersection_config(db, intersection_id)
    return pedestrian.get_pedestrian_requests(db, intersection_id)


# ---------- encrypted evidence (PRJ-SR-003) ----------

class EvidenceIn(BaseModel):
    intersectionId: str = Field(min_length=1, max_length=40)
    sourceId: str = Field(min_length=1, max_length=60)
    capturedAt: datetime
    contentType: str
    dataBase64: str = Field(min_length=4)
    plateText: Optional[str] = Field(default=None, max_length=20)


@router.post("/evidence", status_code=201)
def store_evidence(body: EvidenceIn, request: Request, db: Session = Depends(get_db), _: None = Depends(require_sensor_key)):
    config_service.get_intersection_config(db, body.intersectionId)
    try:
        data = base64.b64decode(body.dataBase64, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationFailure("dataBase64 is not valid base64") from None
    evidence_id = evidence.store(db, request.app.state.settings.evidence_key, body.intersectionId, body.sourceId,
                                 clock.to_naive_utc(body.capturedAt), body.contentType, data, body.plateText,
                                 actor=f"sensor:{body.sourceId}")
    return {"status": "stored", "evidenceId": evidence_id}


EVIDENCE_ROLES = (rbac.OPERATOR, rbac.ADMINISTRATOR)


@router.get("/evidence")
def list_evidence(intersectionId: str | None = None, db: Session = Depends(get_db),
                  user: rbac.CurrentUser = Depends(rbac.require_role(*EVIDENCE_ROLES))):
    return evidence.list_metadata(db, user.username, intersectionId)


@router.get("/evidence-access-log")
def evidence_access_log(evidenceId: str | None = None, db: Session = Depends(get_db),
                        _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return evidence.access_log(db, evidenceId)


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str, request: Request, db: Session = Depends(get_db),
                 user: rbac.CurrentUser = Depends(rbac.require_role(*EVIDENCE_ROLES))):
    return evidence.retrieve(db, request.app.state.settings.evidence_key, evidence_id, user.username)
