"""Demo data: three users and one intersection. Demo passwords are for local use only."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.admin.models import User
from tms.common.db import Intersection

DEMO_USERS = (
    ("operator", "operator123", rbac.OPERATOR),
    ("analyst", "analyst123", rbac.ANALYST),
    ("admin", "admin12345", rbac.ADMINISTRATOR),
)
DEMO_INTERSECTION = ("INT-001", "Main Street and 1st Avenue")
DEMO_MFA_SECRETS = {"operator": "JBSWY3DPEHPK3PXP"}


def seed_demo(db: Session) -> None:
    for username, password, role in DEMO_USERS:
        if db.scalar(select(User).where(User.username == username)) is None:
            rbac.create_user(db, username, password, role)
    if db.get(Intersection, DEMO_INTERSECTION[0]) is None:
        config_service.create_intersection(db, DEMO_INTERSECTION[0], DEMO_INTERSECTION[1], actor="seed")
    # Set the operator's MFA secret so the demo user can log in with TOTP
    operator = db.scalar(select(User).where(User.username == "operator"))
    if operator and operator.mfa_secret is None:
        operator.mfa_secret = DEMO_MFA_SECRETS["operator"]
        db.commit()
