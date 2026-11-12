"""Same build, two environments, no code changes (Roshini): TMS-NF-008, test case TC-Port-01."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tms.common.config import Settings, get_settings, load_env_file
from tms.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_TC_Port_01_the_same_code_runs_in_two_environments_chosen_only_by_settings(tmp_path):
    dev = write(tmp_path / "dev.env", f"TMS_DATABASE_URL=sqlite:///{tmp_path}/dev.db\nTMS_SEED_DEMO=1\nTMS_AUTOTICK=0\n"
                                      "TMS_SENSOR_API_KEY=dev-key\nTMS_PORT=8000\n")
    prod = write(tmp_path / "prod.env", f"TMS_DATABASE_URL=sqlite:///{tmp_path}/prod.db\nTMS_SEED_DEMO=0\nTMS_AUTOTICK=0\n"
                                        "TMS_SENSOR_API_KEY=prod-key\nTMS_PORT=8443\nTMS_REQUIRE_MFA=1\n")
    dev_settings, prod_settings = get_settings(dev), get_settings(prod)
    assert (dev_settings.port, prod_settings.port) == (8000, 8443)
    assert (dev_settings.sensor_api_key, prod_settings.sensor_api_key) == ("dev-key", "prod-key")

    event = {"intersectionId": "INT-001", "timestamp": "2026-10-19T08:59:50Z", "sourceId": "c", "detectionType": "pedestrian",
             "confidence": 0.9}
    with TestClient(create_app(dev_settings)) as dev_app:
        assert dev_app.get("/api/v1/health").status_code == 200
        token = dev_app.post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst123"}).json()["token"]
        assert dev_app.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        assert dev_app.post("/api/v1/detections", json=event, headers={"X-API-Key": "dev-key"}).status_code == 201
        assert dev_app.post("/api/v1/detections", json=event, headers={"X-API-Key": "prod-key"}).status_code == 403
    with TestClient(create_app(prod_settings)) as prod_app:
        assert prod_app.get("/api/v1/health").status_code == 200
        assert prod_app.post("/api/v1/auth/login", json={"username": "analyst", "password": "analyst123"}).status_code == 401   # no demo users
    assert (tmp_path / "dev.db").exists() and (tmp_path / "prod.db").exists()


def test_environment_variables_win_over_the_settings_file(tmp_path, monkeypatch):
    file = write(tmp_path / "x.env", "TMS_PORT=1111\nTMS_HOST=1.2.3.4\n")
    monkeypatch.setenv("TMS_PORT", "2222")
    settings = get_settings(file)
    assert (settings.port, settings.host) == (2222, "1.2.3.4")


def test_the_settings_file_may_name_it_through_tms_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TMS_ENV_FILE", str(write(tmp_path / "e.env", "TMS_BACKUP_KEEP=3\n")))
    assert get_settings().backup_keep == 3


def test_file_format_comments_quotes_and_blank_lines(tmp_path):
    file = write(tmp_path / "x.env", '# comment\n\nTMS_PLUGINS="a.b,c.d"  # trailing\nTMS_HOST = 0.0.0.0\nnot a setting line\n')
    assert load_env_file(file) == {"TMS_PLUGINS": "a.b,c.d", "TMS_HOST": "0.0.0.0"}


@pytest.mark.parametrize("field", [f.name for f in fields(Settings)])
def test_every_setting_can_be_changed_from_outside_the_code(field, monkeypatch):
    default = getattr(Settings(), field)
    if isinstance(default, bool):
        sample = "0" if default else "1"
    elif isinstance(default, int):
        sample = str(default + 1)
    else:
        sample = "changed"
    monkeypatch.setenv("TMS_" + field.upper(), sample)
    assert getattr(get_settings(), field) != default


def test_the_shipped_environment_files_load_and_differ():
    dev, prod = get_settings(ROOT / "config" / "dev.env"), get_settings(ROOT / "config" / "prod.env")
    assert dev.database_url != prod.database_url and dev.seed_demo is True and prod.seed_demo is False
    assert prod.host == "0.0.0.0" and prod.backup_keep == 30


def test_no_environment_specific_paths_are_written_in_the_modules():
    offenders = []
    for path in (ROOT / "src" / "tms").rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text()
        if any(token in text for token in ("sqlite:///./", "sqlite:////", "/data/", "127.0.0.1", "C:\\")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
