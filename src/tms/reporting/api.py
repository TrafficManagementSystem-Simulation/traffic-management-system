"""Report endpoints (Roshini): analysts and administrators generate and download reports."""
from __future__ import annotations

import datetime as dt
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tms.admin import rbac
from tms.common import clock
from tms.common.db import get_db
from tms.common.errors import CommandError
from tms.reporting import generator, scheduler

router = APIRouter(prefix="/api/v1/reports", tags=["reporting"])
ROLES = (rbac.ANALYST, rbac.ADMINISTRATOR)


class GenerateIn(BaseModel):
    period: str
    date: Optional[dt.date] = None        # any day inside the period wanted; defaults to the latest finished period


@router.get("")
def list_reports(period: Optional[str] = None, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*ROLES))):
    return scheduler.list_reports(db, period)


@router.post("/generate", status_code=201)
def generate(body: GenerateIn, db: Session = Depends(get_db), user: rbac.CurrentUser = Depends(rbac.require_role(*ROLES))):
    now = clock.now()
    if body.period not in generator.PERIODS:
        raise CommandError(f"period must be one of {list(generator.PERIODS)}", code="invalid_period")
    if body.date:
        start, end = generator.period_containing(body.period, dt.datetime(body.date.year, body.date.month, body.date.day))
    else:
        start, end = generator.last_completed(body.period, now)
    return scheduler.meta(scheduler.generate(db, body.period, start, end, user.username, now))


@router.get("/{report_id}")
def download(report_id: int, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db),
             _: rbac.CurrentUser = Depends(rbac.require_role(*ROLES))):
    report = scheduler.get(db, report_id)
    name = f"tms-{report.period}-report-{report.period_start:%Y-%m-%d}"
    if format == "csv":
        return Response(generator.to_csv(json.loads(report.content)), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    return Response(report.content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
