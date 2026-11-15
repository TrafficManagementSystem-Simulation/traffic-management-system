"""Time-based one-time passwords (RFC 6238) for multi-factor sign-in (PRJ-SR-002). Standard library only,
so any authenticator app (Google Authenticator, Authy, 1Password ...) works with the secret."""
from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import secrets
import struct
from datetime import datetime

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1          # also accept the code just before and just after, for clocks that differ slightly


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def step_of(at: datetime) -> int:
    return calendar.timegm(at.timetuple()) // STEP_SECONDS


def code_for(secret: str, step: int) -> str:
    key = base64.b32decode(secret.replace(" ", "").upper())
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10 ** DIGITS
    return str(number).zfill(DIGITS)


def totp(secret: str, at: datetime) -> str:
    return code_for(secret, step_of(at))


def verify(secret: str, code: str, at: datetime, last_used_step: int | None = None) -> int | None:
    """Return the step that matched, or None. A step at or before ``last_used_step`` is refused so a code
    that was already used (or shoulder-surfed) cannot be replayed."""
    if not isinstance(code, str) or len(code) != DIGITS or not code.isdigit():
        return None
    now_step = step_of(at)
    for step in range(now_step - WINDOW, now_step + WINDOW + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(code_for(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, username: str, issuer: str = "Traffic Management System") -> str:
    from urllib.parse import quote

    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP_SECONDS}"
