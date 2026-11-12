"""Daily backups and restore (TMS-NF-009): RPO 24 hours, RTO 4 hours.

A backup is a consistent copy of the whole database (configuration, users, traffic history, audit logs),
made with SQLite's online backup so the service keeps running. Each comes with a manifest holding its
SHA-256 so a damaged file is refused at restore time.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from tms.common import clock, db
from tms.common.errors import CommandError, NotFoundError

RPO_HOURS = 24
RTO_HOURS = 4


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _row_counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(path)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    finally:
        conn.close()


def backup_now(directory: str | Path, now: datetime | None = None) -> dict:
    now = now or clock.now()
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"tms-backup-{now:%Y%m%d-%H%M%S}.db"
    part = folder / (name + ".part")
    raw = db.get_engine().raw_connection()
    try:
        target = sqlite3.connect(part)
        try:
            raw.driver_connection.backup(target)
        finally:
            target.close()
    finally:
        raw.close()
    final = folder / name
    os.replace(part, final)
    os.chmod(final, 0o600)                                         # it holds password hashes and encrypted evidence
    manifest = {"file": name, "createdAt": now.isoformat(), "sizeBytes": final.stat().st_size,
                "sha256": _sha256(final), "tables": _row_counts(final)}
    (folder / (name + ".json")).write_text(json.dumps(manifest, indent=2))
    return manifest


def list_backups(directory: str | Path) -> list[dict]:
    folder = Path(directory)
    if not folder.exists():
        return []
    items = []
    for path in folder.glob("tms-backup-*.db.json"):
        try:
            items.append(json.loads(path.read_text()))
        except ValueError:
            continue
    return sorted(items, key=lambda m: m["createdAt"], reverse=True)


def status(directory: str | Path, now: datetime | None = None) -> dict:
    now = now or clock.now()
    backups = list_backups(directory)
    if not backups:
        return {"backups": 0, "latest": None, "ageHours": None, "rpoHours": RPO_HOURS, "rpoMet": False,
                "rtoHours": RTO_HOURS}
    age = (now - datetime.fromisoformat(backups[0]["createdAt"])).total_seconds() / 3600
    return {"backups": len(backups), "latest": backups[0], "ageHours": round(age, 2), "rpoHours": RPO_HOURS,
            "rpoMet": age <= RPO_HOURS, "rtoHours": RTO_HOURS}


def prune(directory: str | Path, keep: int) -> list[str]:
    removed = []
    for manifest in list_backups(directory)[max(1, keep):]:
        for suffix in ("", ".json"):
            path = Path(directory) / (manifest["file"] + suffix)
            if path.exists():
                path.unlink()
        removed.append(manifest["file"])
    return removed


def run_due(directory: str | Path, keep: int = 14, now: datetime | None = None) -> dict | None:
    """Make the daily backup if the latest one is a day old or there is none. Returns the new manifest."""
    now = now or clock.now()
    current = status(directory, now)
    if current["latest"] is not None and current["ageHours"] < RPO_HOURS - 1:    # leaves an hour of margin
        return None
    manifest = backup_now(directory, now)
    prune(directory, keep)
    return manifest


def verify(directory: str | Path, file_name: str) -> Path:
    path = Path(directory) / Path(file_name).name
    manifest_path = Path(str(path) + ".json")
    if not path.exists() or not manifest_path.exists():
        raise NotFoundError(f"Backup {file_name} does not exist", code="backup_not_found")
    if _sha256(path) != json.loads(manifest_path.read_text())["sha256"]:
        raise CommandError("The backup file does not match its checksum; it is damaged", code="backup_damaged", status_code=409)
    check = sqlite3.connect(path)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise CommandError("The backup failed the database integrity check", code="backup_damaged", status_code=409)
    finally:
        check.close()
    return path


def restore(directory: str | Path, file_name: str | None = None) -> dict:
    """Replace the live database with a backup (the newest one unless ``file_name`` is given)."""
    started = time.perf_counter()
    if file_name is None:
        backups = list_backups(directory)
        if not backups:
            raise NotFoundError("There are no backups to restore", code="backup_not_found")
        file_name = backups[0]["file"]
    path = verify(directory, file_name)
    source = sqlite3.connect(path)
    raw = db.get_engine().raw_connection()
    try:
        source.backup(raw.driver_connection)
        raw.driver_connection.commit()
    finally:
        raw.close()
        source.close()
    return {"restoredFrom": file_name, "seconds": round(time.perf_counter() - started, 3), "rtoHours": RTO_HOURS}
