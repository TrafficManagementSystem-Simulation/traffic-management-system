"""Health, availability and backup endpoints (Roshini)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tms.admin import rbac
from tms.common import clock
from tms.common.db import get_db
from tms.infra import backup, uptime
from tms.infra.models import MaintenanceWindow

router = APIRouter(prefix="/api/v1", tags=["platform"])


class WindowIn(BaseModel):
    startsAt: datetime
    endsAt: datetime
    reason: str = Field(default="", max_length=200)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Public probe for load balancers and uptime monitors."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "time": clock.now().isoformat()}


@router.get("/admin/availability")
def availability(month: str = Query(..., description="for example 2026-10"), db: Session = Depends(get_db),
                 _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    start, end = uptime.month_bounds(month)
    return {"month": month, **uptime.availability(db, start, end, clock.now())}


@router.post("/admin/maintenance-windows", status_code=201)
def add_window(body: WindowIn, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    row = uptime.add_maintenance_window(db, clock.to_naive_utc(body.startsAt), clock.to_naive_utc(body.endsAt), body.reason)
    return {"id": row.id}


@router.get("/admin/maintenance-windows")
def windows(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return [{"id": w.id, "startsAt": w.starts_at.isoformat(), "endsAt": w.ends_at.isoformat(), "reason": w.reason}
            for w in db.scalars(select(MaintenanceWindow).order_by(MaintenanceWindow.starts_at))]


@router.get("/admin/backups")
def backups(request: Request, _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    folder = request.app.state.settings.backup_dir
    return {**backup.status(folder, clock.now()), "files": [b["file"] for b in backup.list_backups(folder)]}


@router.post("/admin/backups", status_code=201)
def run_backup(request: Request, admin: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR)),
               db: Session = Depends(get_db)):
    settings = request.app.state.settings
    manifest = backup.backup_now(settings.backup_dir, clock.now())
    backup.prune(settings.backup_dir, settings.backup_keep)
    rbac.log_security(db, admin.username, "backup_made", manifest["file"])
    return manifest
