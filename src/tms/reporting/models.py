"""Tables owned by the Reporting module (Roshini)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tms.common import clock
from tms.common.db import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("period", "period_start", name="uq_report_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(10), index=True)          # daily | weekly | monthly
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    generated_by: Mapped[str] = mapped_column(String(60))                # scheduler or a user name
    content: Mapped[str] = mapped_column(Text)                           # JSON
