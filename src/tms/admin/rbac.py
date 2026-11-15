"""Role-based access control (TMS-F-018, PRJ-SR-004), logins and the security log.

Every other module protects its endpoints with ``Depends(require_role(...))``.
Denied and failed attempts are written to ``security_log``.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import mfa
from tms.admin.models import AuthToken, SecurityLog, User
from tms.common import clock
from tms.common.config import get_settings
from tms.common.db import get_db
from tms.common.errors import AuthError, CommandError, ForbiddenError

OPERATOR = "Operator"
ADMINISTRATOR = "Administrator"
ANALYST = "Analyst"
ALL_ROLES = (OPERATOR, ADMINISTRATOR, ANALYST)

# What each role may do (shown on the admin page and returned by /auth/me).
ROLE_PERMISSIONS: dict[str, list[str]] = {
    OPERATOR: ["view signals", "override signals", "view detections", "tick and recompute signals", "view audit log"],
    ADMINISTRATOR: ["manage users", "configure intersections", "view security log", "view signals",
                    "view detections", "tick and recompute signals", "view audit log", "run simulations"],
    ANALYST: ["run simulations", "view signals", "view detections"],
}

TOKEN_HOURS = 8
_PBKDF2_ROUNDS = 100_000


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    role: str
    mfa_verified: bool = False


# ---------- passwords and tokens ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS).hex()
    return hmac.compare_digest(candidate, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- security log ----------

def log_security(db: Session, username: str | None, event: str, details: str = "") -> None:
    db.add(SecurityLog(timestamp=clock.now(), username=username, event=event, details=details))
    db.commit()


# ---------- users ----------

def create_user(db: Session, username: str, password: str, role: str) -> User:
    username = username.strip()
    if not username or len(username) > 60:
        raise CommandError("Username must be 1 to 60 characters", code="invalid_user")
    if role not in ALL_ROLES:
        raise CommandError(f"Role must be one of {', '.join(ALL_ROLES)}", code="invalid_role")
    if len(password) < 8:
        raise CommandError("Password must be at least 8 characters", code="weak_password")
    if db.scalar(select(User).where(User.username == username)):
        raise CommandError(f"User '{username}' already exists", code="user_exists", status_code=409)
    user = User(username=username, password_hash=hash_password(password), role=role, active=True)
    db.add(user)
    db.commit()
    return user


def set_user_role(db: Session, username: str, role: str) -> User:
    if role not in ALL_ROLES:
        raise CommandError(f"Role must be one of {', '.join(ALL_ROLES)}", code="invalid_role")
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise CommandError(f"User '{username}' not found", code="user_not_found", status_code=404)
    user.role = role
    db.commit()
    return user


def login(db: Session, username: str, password: str, otp: str | None = None, hours: int = TOKEN_HOURS) -> tuple[str, User, bool]:
    """Return (token, user, mfa_verified). If user has MFA enrolled and no OTP provided, raises AuthError with code 'mfa_required'.
    If OTP provided but invalid, raises AuthError with code 'mfa_invalid'."""
    settings = get_settings()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.active or not verify_password(password, user.password_hash):
        log_security(db, username or None, "login_failed", "Invalid username or password")
        raise AuthError("Invalid username or password", code="invalid_credentials")

    # Check if MFA is required for this user
    mfa_verified = False
    if settings.require_mfa and user.mfa_secret:
        if otp is None:
            log_security(db, user.username, "login_mfa_missing", "MFA code required")
            raise AuthError("Multi-factor authentication required", code="mfa_required")
        step = mfa.verify(user.mfa_secret, otp, clock.now(), user.mfa_last_step)
        if step is None:
            log_security(db, user.username, "login_mfa_failed", "Invalid MFA code")
            raise AuthError("Invalid MFA code", code="mfa_invalid")
        mfa_verified = True
        user.mfa_last_step = step
        db.commit()

    token = secrets.token_urlsafe(32)
    db.add(AuthToken(token_hash=_token_hash(token), user_id=user.id, expires_at=clock.now() + timedelta(hours=hours), mfa_verified=mfa_verified))
    db.commit()
    log_security(db, user.username, "login_ok", f"role={user.role}, mfa={mfa_verified}")
    return token, user, mfa_verified


def authenticate_token(db: Session, token: str | None) -> CurrentUser | None:
    if not token:
        return None
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == _token_hash(token)))
    if row is None or row.expires_at < clock.now():
        return None
    user = db.get(User, row.user_id)
    if user is None or not user.active:
        return None
    return CurrentUser(id=user.id, username=user.username, role=user.role, mfa_verified=row.mfa_verified)


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def require_role(*roles: str):
    """FastAPI dependency. ``require_role()`` with no arguments means any signed-in user."""
    allowed = set(roles) if roles else set(ALL_ROLES)

    def dependency(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
        user = authenticate_token(db, _bearer(request))
        where = f"{request.method} {request.url.path}"
        if user is None:
            log_security(db, None, "auth_failed", where)
            raise AuthError("Sign in first (missing or invalid token)")
        if user.role not in allowed:
            log_security(db, user.username, "access_denied", f"{where} role={user.role} needs {sorted(allowed)}")
            raise ForbiddenError(f"Role {user.role} may not do this")
        return user

    return dependency


def require_mfa(request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require_role())) -> CurrentUser:
    """Dependency that requires the session to have MFA verified (for signal-state changes)."""
    settings = get_settings()
    if settings.require_mfa and not user.mfa_verified:
        log_security(db, user.username, "access_denied", f"{request.method} {request.url.path} needs MFA")
        raise ForbiddenError("Multi-factor authentication required for this action", code="mfa_required")
    return user
