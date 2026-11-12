"""Daily backups and restore within the RPO and RTO (Roshini): TMS-NF-009, test case TC-BCP-01."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from tms.admin import config_service
from tms.admin.models import User
from tms.common.errors import CommandError, NotFoundError
from tms.detection.api import DetectionIn, ingest_detection
from tms.detection.models import TrafficCount
from tms.infra import backup

IID = "INT-001"
T0 = datetime(2026, 10, 19, 2, 0, 0)


def add_traffic(session, n=30):
    for i in range(n):
        ingest_detection(session, DetectionIn(intersectionId=IID, timestamp=f"2026-10-19T08:{i:02d}:00Z", sourceId="c",
                                              detectionType="vehicle", count=2, confidence=0.9, approach="N", lane=1,
                                              **{"class": "car"}))


def totals(session):
    return (session.scalar(select(func.sum(TrafficCount.count))), session.scalar(select(func.count(User.id))),
            config_service.get_intersection_config(session, IID)["min_green"])


def test_TC_BCP_01_restore_returns_configuration_and_traffic_history_within_the_rto(session, tmp_path):
    add_traffic(session)
    config_service.update_intersection_config(session, IID, {"min_green": 14}, actor="admin")
    before = totals(session)
    assert before == (60, 3, 14)
    manifest = backup.backup_now(tmp_path, T0)

    # the disaster: data is lost and configuration is damaged
    session.query(TrafficCount).delete()
    session.query(User).delete()
    config_service.update_intersection_config(session, IID, {"min_green": 8}, actor="oops")
    session.commit()
    assert totals(session)[:2] == (None, 0)

    started = time.perf_counter()
    result = backup.restore(tmp_path)
    elapsed = time.perf_counter() - started
    session.expire_all()
    assert totals(session) == before
    assert result["restoredFrom"] == manifest["file"] and elapsed < 4 * 3600 and elapsed < 30   # RTO is 4 hours; this takes seconds


def test_the_backup_is_a_consistent_copy_with_a_manifest(session, tmp_path):
    add_traffic(session, 5)
    manifest = backup.backup_now(tmp_path, T0)
    assert manifest["tables"]["users"] == 3 and manifest["tables"]["traffic_counts"] == 5
    assert (tmp_path / manifest["file"]).stat().st_mode & 0o777 == 0o600                          # only the owner can read it
    assert json.loads((tmp_path / (manifest["file"] + ".json")).read_text())["sha256"] == manifest["sha256"]
    assert not list(tmp_path.glob("*.part"))


def test_TC_BCP_01_the_daily_run_keeps_the_backup_no_older_than_the_rpo(session, tmp_path):
    assert backup.status(tmp_path, T0)["rpoMet"] is False                                           # nothing yet
    first = backup.run_due(tmp_path, 14, T0)
    assert first and backup.status(tmp_path, T0 + timedelta(hours=23))["rpoMet"] is True
    assert backup.run_due(tmp_path, 14, T0 + timedelta(hours=5)) is None                            # not due again yet
    assert backup.status(tmp_path, T0 + timedelta(hours=25))["rpoMet"] is False                     # a day old: overdue
    assert backup.run_due(tmp_path, 14, T0 + timedelta(hours=23, minutes=30)) is not None           # due, an hour of margin
    assert backup.status(tmp_path, T0 + timedelta(hours=25))["ageHours"] < 24


def test_old_backups_are_pruned(session, tmp_path):
    for day in range(6):
        backup.backup_now(tmp_path, T0 + timedelta(days=day))
    removed = backup.prune(tmp_path, 3)
    assert len(removed) == 3 and len(backup.list_backups(tmp_path)) == 3
    assert backup.list_backups(tmp_path)[0]["createdAt"].startswith("2026-10-24")
    assert not list(tmp_path.glob(f"{removed[0]}*"))


def test_a_damaged_backup_is_refused_and_the_live_data_is_left_alone(session, tmp_path):
    add_traffic(session, 5)
    manifest = backup.backup_now(tmp_path, T0)
    add_traffic(session, 3)
    session.commit()
    (tmp_path / manifest["file"]).write_bytes(b"corrupted")
    with pytest.raises(CommandError) as caught:
        backup.restore(tmp_path)
    assert caught.value.code == "backup_damaged"
    session.expire_all()
    assert session.scalar(select(func.sum(TrafficCount.count))) == 16           # the 3 later events are still there


def test_restore_errors(session, tmp_path):
    with pytest.raises(NotFoundError):
        backup.restore(tmp_path)
    with pytest.raises(NotFoundError):
        backup.restore(tmp_path, "tms-backup-nope.db")


def test_a_named_older_backup_can_be_restored(session, tmp_path):
    add_traffic(session, 2)
    old = backup.backup_now(tmp_path, T0)
    add_traffic(session, 6)
    session.commit()
    backup.backup_now(tmp_path, T0 + timedelta(days=1))
    backup.restore(tmp_path, old["file"])
    session.expire_all()
    assert session.scalar(select(func.sum(TrafficCount.count))) == 4


def test_admin_api(client, admin_h, operator_h, tmp_path, app):
    object.__setattr__(app.state.settings, "backup_dir", str(tmp_path))
    assert client.get("/api/v1/admin/backups", headers=operator_h).status_code == 403
    assert client.get("/api/v1/admin/backups", headers=admin_h).json()["rpoMet"] is False
    made = client.post("/api/v1/admin/backups", headers=admin_h)
    assert made.status_code == 201 and made.json()["tables"]["users"] == 3
    listed = client.get("/api/v1/admin/backups", headers=admin_h).json()
    assert listed["rpoMet"] is True and listed["files"] == [made.json()["file"]]
    log = client.get("/api/v1/admin/security-log", headers=admin_h).json()
    assert any(row["event"] == "backup_made" for row in log)
