"""Tables owned by the Incident module (Likhita): incidents, operator alerts, emergency dispatches."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(30))                 # congestion | stalled_vehicle | collision
    severity: Mapped[str] = mapped_column(String(10))             # low | medium | high
    approach: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lane: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(15), default="open", index=True)   # open | acknowledged | resolved
    details: Mapped[str] = mapped_column(Text, default="{}")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Alert(Base):
    """What the operator console shows (TMS-F-015)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    message: Mapped[str] = mapped_column(String(300))
    acknowledged_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Dispatch(Base):
    """A request to an emergency service sent from an incident (TMS-F-016)."""

    __tablename__ = "dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    service: Mapped[str] = mapped_column(String(20))              # police | ambulance | fire
    requested_by: Mapped[str] = mapped_column(String(60))
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    status: Mapped[str] = mapped_column(String(15))               # acknowledged | failed
    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str] = mapped_column(String(300), default="")
