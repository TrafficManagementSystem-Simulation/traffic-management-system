"""Settings come from environment variables so the same build runs anywhere (TMS-NF-008).

A settings file (``KEY=VALUE`` lines) can be named with ``TMS_ENV_FILE``; real environment variables
win over the file. Nothing environment-specific is written in the code: switching from a laptop to a
server means switching the file, not the build.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path


def load_env_file(path: str | os.PathLike) -> dict[str, str]:
    """Read ``KEY=VALUE`` lines. Blank lines and ``#`` comments are ignored; quotes around values are removed."""
    values: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        line = line.split(" #", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./tms.db"
    sensor_api_key: str = "sensor-demo-key"
    autotick: bool = True          # background loop that advances signals once a second
    seed_demo: bool = True         # create demo users and one intersection when the DB is empty
    token_hours: int = 8
    tls_cert: str = "certs/tms-cert.pem"
    tls_key: str = "certs/tms-key.pem"
    timing_algorithm: str = "proportional"      # which signal-timing plugin is active (TMS-NF-007)
    plugins: str = ""                           # comma separated modules to import at start (extra plugins)
    require_mfa: bool = True                    # signal-state changes need a multi-factor session (PRJ-SR-002)
    evidence_key: str = "ZGVtby1vbmx5LWtleS1jaGFuZ2UtbWUtaW4tcHJvZCE="   # Fernet key; set TMS_EVIDENCE_KEY in production
    admin_hours: str = "06:00-22:00"            # UTC window for normal administrator access (PRJ-SR-005)
    preemption_key: str = "preempt-demo-key"   # secure channel for emergency-vehicle requests (TMS-F-004)
    host: str = "127.0.0.1"
    port: int = 8000
    backup_dir: str = "backups"                 # daily backups go here (TMS-NF-009)
    backup_keep: int = 14                       # how many backups to keep
    backups_enabled: bool = True


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings(env_file: str | os.PathLike | None = None) -> Settings:
    """Environment first, then the settings file (``env_file`` or ``TMS_ENV_FILE``), then the defaults above."""
    source: dict[str, str] = {}
    chosen = env_file or os.getenv("TMS_ENV_FILE")
    if chosen:
        source.update(load_env_file(chosen))
    source.update({k: v for k, v in os.environ.items() if k.startswith("TMS_")})
    defaults, values = Settings(), {}
    for field in fields(Settings):
        raw = source.get("TMS_" + field.name.upper())
        if raw is None:
            continue
        current = getattr(defaults, field.name)
        values[field.name] = _flag(raw) if isinstance(current, bool) else int(raw) if isinstance(current, int) else raw
    return Settings(**values)


# Default configuration of one intersection (see SAD 4.4 and SRS TMS-F-019).
DEFAULT_INTERSECTION_CONFIG: dict = {
    "approaches": {"N": "NS", "S": "NS", "E": "EW", "W": "EW"},  # approach -> signal phase
    "phases": ["NS", "EW"],
    "cycle_seconds": 90,
    "min_green": 10,
    "max_green": 60,
    "yellow": 3,
    "all_red": 2,
    "pedestrian_walk": 7,
    "pedestrian_clearance": 15,
    "count_interval_seconds": 60,
    "density_window_minutes": 5,
    "latitude": 12.9716,       # location, used by the GIS interface (TMS-NF-010)
    "longitude": 77.5946,
}
