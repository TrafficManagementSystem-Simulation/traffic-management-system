"""Admin and sign-in endpoints (Roshini)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import config_service, mfa, rbac
from tms.admin.models import SecurityLog, User
from tms.common import clock
from tms.common.config import get_settings
from tms.common.db import get_db

router = APIRouter(prefix="/api/v1", tags=["admin"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)
    otp: str | None = Field(default=None, max_length=6)


class UserIn(BaseModel):
    username: str
    password: str
    role: str


class RoleIn(BaseModel):
    role: str


class IntersectionIn(BaseModel):
    id: str
    name: str = ""
    config: dict | None = None


class ConfigIn(BaseModel):
    changes: dict


# ---------- sign in ----------

@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    token, user, mfa_verified = rbac.login(db, body.username, body.password, body.otp)
    return {"token": token, "username": user.username, "role": user.role, "mfa": mfa_verified}


@router.get("/auth/me")
def me(user: rbac.CurrentUser = Depends(rbac.require_role())):
    return {"username": user.username, "role": user.role, "permissions": rbac.ROLE_PERMISSIONS[user.role], "mfaVerified": user.mfa_verified}


# ---------- MFA enrollment and confirmation ----------

class MfaConfirmIn(BaseModel):
    otp: str = Field(min_length=6, max_length=6)


@router.post("/auth/mfa/enroll")
def mfa_enroll(request: Request, user: rbac.CurrentUser = Depends(rbac.require_role()), db: Session = Depends(get_db)):
    """Start MFA enrollment for the current user. Returns a secret and otpauth URI for the authenticator app."""
    db_user = db.get(User, user.id)
    if db_user.mfa_secret or db_user.mfa_pending:
        return {"secret": db_user.mfa_secret or db_user.mfa_pending, "otpauthUri": mfa.provisioning_uri(db_user.mfa_secret or db_user.mfa_pending, db_user.username)}
    secret = mfa.generate_secret()
    db_user.mfa_pending = secret
    db.commit()
    return {"secret": secret, "otpauthUri": mfa.provisioning_uri(secret, db_user.username)}


@router.post("/auth/mfa/confirm")
def mfa_confirm(body: MfaConfirmIn, request: Request, user: rbac.CurrentUser = Depends(rbac.require_role()), db: Session = Depends(get_db)):
    """Confirm MFA enrollment by providing a valid TOTP code."""
    db_user = db.get(User, user.id)
    if not db_user.mfa_pending:
        from tms.common.errors import CommandError
        raise CommandError("MFA enrollment not started", code="mfa_not_started", status_code=400)
    step = mfa.verify(db_user.mfa_pending, body.otp, clock.now())
    if step is None:
        from tms.common.errors import CommandError
        raise CommandError("Invalid OTP", code="invalid_otp", status_code=400)
    db_user.mfa_secret = db_user.mfa_pending
    db_user.mfa_pending = None
    db_user.mfa_last_step = step
    db.commit()
    # Also mark the current token as MFA verified
    from tms.admin.rbac import _token_hash, _bearer
    token_str = _bearer(request)
    if token_str:
        from tms.admin.models import AuthToken
        token_row = db.scalar(select(AuthToken).where(AuthToken.token_hash == _token_hash(token_str)))
        if token_row:
            token_row.mfa_verified = True
            db.commit()
    return {"status": "enrolled"}


@router.post("/admin/users/{username}/mfa/reset")
def mfa_reset(username: str, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    """Admin-only: reset a user's MFA enrollment (clears secret and pending)."""
    db_user = db.scalar(select(User).where(User.username == username))
    if db_user is None:
        from tms.common.errors import NotFoundError
        raise NotFoundError(f"User '{username}' not found", code="user_not_found")
    db_user.mfa_secret = None
    db_user.mfa_pending = None
    db_user.mfa_last_step = None
    db.commit()
    return {"status": "reset"}


# ---------- intersections ----------

@router.get("/intersections")
def intersections(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role())):
    return config_service.list_intersections(db)


@router.get("/admin/intersections/{intersection_id}/config")
def get_config(intersection_id: str, db: Session = Depends(get_db),
               _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.get_intersection_config(db, intersection_id)


@router.post("/admin/intersections", status_code=201)
def create_intersection(body: IntersectionIn, db: Session = Depends(get_db),
                        user: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.create_intersection(db, body.id, body.name, body.config, actor=user.username)


@router.put("/admin/intersections/{intersection_id}/config")
def update_config(intersection_id: str, body: ConfigIn, db: Session = Depends(get_db),
                  user: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.update_intersection_config(db, intersection_id, body.changes, actor=user.username)


@router.get("/admin/intersections/{intersection_id}/config/history")
def config_history(intersection_id: str, db: Session = Depends(get_db),
                   _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return config_service.config_history(db, intersection_id)


# ---------- users and roles ----------

@router.get("/admin/users")
def list_users(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    rows = db.scalars(select(User).order_by(User.username)).all()
    return [{"username": u.username, "role": u.role, "active": u.active} for u in rows]


@router.post("/admin/users", status_code=201)
def add_user(body: UserIn, db: Session = Depends(get_db),
             _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    user = rbac.create_user(db, body.username, body.password, body.role)
    return {"username": user.username, "role": user.role}


@router.put("/admin/users/{username}/role")
def change_role(username: str, body: RoleIn, db: Session = Depends(get_db),
                _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    user = rbac.set_user_role(db, username, body.role)
    return {"username": user.username, "role": user.role}


@router.get("/admin/roles")
def roles(_: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    return rbac.ROLE_PERMISSIONS


@router.get("/admin/security-log")
def security_log(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db),
                 _: rbac.CurrentUser = Depends(rbac.require_role(rbac.ADMINISTRATOR))):
    rows = db.scalars(select(SecurityLog).order_by(SecurityLog.id.desc()).limit(limit)).all()
    return [{"timestamp": r.timestamp.isoformat(), "user": r.username, "event": r.event, "details": r.details}
            for r in rows]
