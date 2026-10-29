"""Tables owned by the Signal Control module (Manoj): live signal state, applied plans, audit log."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class SignalState(Base):
    __tablename__ = "signal_state"

    intersection_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), default="adaptive")      # adaptive | manual
    phase: Mapped[str] = mapped_column(String(20))                          # NS, EW, PED or ALL_RED
    stage: Mapped[str] = mapped_column(String(10))                          # GREEN, YELLOW, ALL_RED, PED
    stage_started_at: Mapped[datetime] = mapped_column(DateTime)
    stage_duration: Mapped[int] = mapped_column(Integer)                    # seconds
    last_vehicle_phase: Mapped[str] = mapped_column(String(20))
    plan: Mapped[str] = mapped_column(Text)                                 # JSON of the active plan
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)      # computed, waits for next green
    manual_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manual_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    manual_by: Mapped[str | None] = mapped_column(String(60), nullable=True)


class SignalPlanRecord(Base):
    """Every plan that was applied (table ``signal_plans`` in the team doc)."""

    __tablename__ = "signal_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    plan: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    intersection_id: Mapped[str] = mapped_column(String(40), index=True)
    event: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(20))                         # auto | manual | preemption
    actor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="{}")
