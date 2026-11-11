"""Tables owned by the Detection module (Likhita)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_id: Mapped[str] = mapped_column(String(60))
    detection_type: Mapped[str] = mapped_column(String(20))        # vehicle | pedestrian
    vehicle_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float)
    approach: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)   # 0 means stationary (stalled vehicle)


class TrafficCount(Base):
    """Vehicles per approach, lane, class and time interval (TMS-F-007)."""

    __tablename__ = "traffic_counts"
    __table_args__ = (
        UniqueConstraint("intersection_id", "approach", "lane", "interval_start", "vehicle_class",
                         name="uq_traffic_counts_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    approach: Mapped[str] = mapped_column(String(10))
    lane: Mapped[int] = mapped_column(Integer)
    interval_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    vehicle_class: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer, default=0)


class PedestrianRequest(Base):
    __tablename__ = "pedestrian_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    crosswalk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | served
    served_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Evidence(Base):
    """Camera images and video that may show number plates (PRJ-SR-003). The content and the plate text
    are stored only as ciphertext; the columns that stay readable are not identifying."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    content_type: Mapped[str] = mapped_column(String(60))
    source_id: Mapped[str] = mapped_column(String(60))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    stored_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


class EvidenceAccess(Base):
    """One row for every store, retrieval and refused attempt."""

    __tablename__ = "evidence_access_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(20))        # stored | retrieved | listed | denied
