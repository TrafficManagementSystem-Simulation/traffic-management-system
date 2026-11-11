"""Encrypted evidence storage (PRJ-SR-003, TMS-NF-003).

Image or video bytes, and any plate text, are encrypted with Fernet (AES-128-CBC with HMAC) before they reach
the database. Every store, retrieval and refused attempt is written to the access log.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.common import clock
from tms.common.errors import CommandError, NotFoundError, TMSError
from tms.detection.models import Evidence, EvidenceAccess

MAX_BYTES = 5_000_000
TYPES = ("image/jpeg", "image/png", "video/mp4")


class EvidenceKeyError(TMSError):
    status_code = 500
    code = "evidence_key_invalid"


def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise EvidenceKeyError("TMS_EVIDENCE_KEY is not a valid Fernet key") from exc


def log_access(db: Session, username: str, action: str, evidence_id: str | None, now: datetime | None = None) -> None:
    db.add(EvidenceAccess(timestamp=now or clock.now(), evidence_id=evidence_id, username=username, action=action))
    db.commit()


def store(db: Session, key: str, intersection_id: str, source_id: str, captured_at: datetime, content_type: str,
          data: bytes, plate_text: str | None, actor: str, now: datetime | None = None) -> str:
    if content_type not in TYPES:
        raise CommandError(f"contentType must be one of {list(TYPES)}", code="invalid_content_type")
    if not data or len(data) > MAX_BYTES:
        raise CommandError(f"evidence must be 1 to {MAX_BYTES} bytes", code="invalid_size")
    payload = json.dumps({"data": base64.b64encode(data).decode(), "plate": plate_text})
    evidence_id = "EV-" + uuid.uuid4().hex[:12]
    db.add(Evidence(id=evidence_id, intersection_id=intersection_id, captured_at=captured_at, content_type=content_type,
                    source_id=source_id, ciphertext=_fernet(key).encrypt(payload.encode()), stored_at=now or clock.now()))
    db.commit()
    log_access(db, actor, "stored", evidence_id, now)
    return evidence_id


def retrieve(db: Session, key: str, evidence_id: str, username: str, now: datetime | None = None) -> dict:
    row = db.get(Evidence, evidence_id)
    if row is None:
        log_access(db, username, "denied", evidence_id, now)
        raise NotFoundError(f"Evidence {evidence_id} does not exist", code="evidence_not_found")
    log_access(db, username, "retrieved", evidence_id, now)          # logged before the content is released
    try:
        payload = json.loads(_fernet(key).decrypt(row.ciphertext))
    except InvalidToken as exc:
        raise EvidenceKeyError("Stored evidence could not be decrypted with the configured key") from exc
    return {"id": row.id, "intersectionId": row.intersection_id, "capturedAt": row.captured_at.isoformat(),
            "contentType": row.content_type, "sourceId": row.source_id, "dataBase64": payload["data"],
            "plateText": payload["plate"]}


def list_metadata(db: Session, username: str, intersection_id: str | None = None) -> list[dict]:
    query = select(Evidence).order_by(Evidence.stored_at.desc())
    if intersection_id:
        query = query.where(Evidence.intersection_id == intersection_id)
    log_access(db, username, "listed", None)
    return [{"id": r.id, "intersectionId": r.intersection_id, "capturedAt": r.captured_at.isoformat(),
             "contentType": r.content_type, "sourceId": r.source_id} for r in db.scalars(query)]


def access_log(db: Session, evidence_id: str | None = None, limit: int = 200) -> list[dict]:
    query = select(EvidenceAccess).order_by(EvidenceAccess.id.desc()).limit(limit)
    if evidence_id:
        query = query.where(EvidenceAccess.evidence_id == evidence_id)
    return [{"id": r.id, "timestamp": r.timestamp.isoformat(), "evidenceId": r.evidence_id, "username": r.username,
             "action": r.action} for r in db.scalars(query)]
