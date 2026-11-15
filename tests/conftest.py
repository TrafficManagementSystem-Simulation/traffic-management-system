"""Shared test setup (Naveen).

Every test gets its own in-memory database, a frozen clock (so signal timing is deterministic and
a one-hour scenario does not take an hour), and the demo users. Test names carry the SRS test
case ID, for example ``test_TC_Sig_01_...``, so docs/test-cases.md and the RTM can be filled in.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tms.common import clock, db
from tms.common.config import Settings
from tms.main import available, create_app

START = datetime(2026, 10, 19, 9, 0, 0)   # the clock is frozen here at the start of every test
SENSOR_KEY = "sensor-demo-key"

if available("tms.admin.rbac"):
    from tms.admin import rbac

    rbac._PBKDF2_ROUNDS = 1_000  # faster hashing in tests only; production keeps 100,000


def after(seconds: float) -> datetime:
    """The frozen start time plus ``seconds``."""
    return START + timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def frozen_clock():
    clock.freeze(START)
    yield START
    clock.unfreeze()


@pytest.fixture
def app():
    return create_app(Settings(database_url="sqlite://", autotick=False, seed_demo=True))


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(app):
    """A database session on the same in-memory database the app uses (for unit tests)."""
    database = db.new_session()
    yield database
    database.close()


def sign_in(client: TestClient, username: str, password: str, otp: str | None = None) -> dict:
    body = {"username": username, "password": password}
    if otp is not None:
        body["otp"] = otp
    response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def operator_h(client):
    from tms.admin import mfa
    from tms.common import clock
    from tms.common.seed import DEMO_MFA_SECRETS
    return sign_in(client, "operator", "operator123", otp=mfa.totp(DEMO_MFA_SECRETS["operator"], clock.now()))


@pytest.fixture
def analyst_h(client):
    return sign_in(client, "analyst", "analyst123")


@pytest.fixture
def admin_h(client):
    return sign_in(client, "admin", "admin12345")


@pytest.fixture
def sensor_h():
    return {"X-API-Key": SENSOR_KEY}
