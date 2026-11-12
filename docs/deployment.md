# Deployment and operations (TMS-NF-008, NF-009, NF-002)

## One build, many environments
The code never names a database, port or key. Choose the environment with a settings file:
```bash
TMS_ENV_FILE=config/dev.env  python scripts/run_server.py      # laptop: SQLite file, demo data
TMS_ENV_FILE=config/prod.env python scripts/run_server.py      # server: /data volume, no demo data, keys from the environment
docker compose up dev      |      docker compose up prod       # same image either way
```
Production must set `TMS_SENSOR_API_KEY`, `TMS_PREEMPTION_KEY` and `TMS_EVIDENCE_KEY` as environment variables.
Test: `tests/unit/infra/test_portability.py` (TC-Port-01) starts the app from two different settings files.
(The Docker files are included for the second environment; they were not built in the cloud workspace used to write them.)

## Backups: RPO 24 hours, RTO 4 hours
The running app checks once a minute and makes a backup when the newest is about a day old, keeping the newest `TMS_BACKUP_KEEP`.
```bash
python scripts/run_backup.py status          # latest backup, age, and whether the RPO is met
python scripts/run_backup.py backup          # make one now
python scripts/run_backup.py restore         # newest backup; stop the app first
```
Each backup has a SHA-256 manifest; a damaged file is refused. Backups hold password hashes and encrypted evidence, so keep the
folder private (files are created owner-only). Restore drill: `tests/unit/infra/test_backup_restore.py` (TC-BCP-01).

## Availability: 99.5% a month
The service writes a heartbeat every 30 seconds. `GET /api/v1/admin/availability?month=2026-10` (Administrator) reports availability,
the outages, and the planned maintenance that was excluded (`POST /api/v1/admin/maintenance-windows`). `GET /api/v1/health` is the
public probe for a load balancer.

## Fail-safe at the intersection (TMS-NF-006)
`signal_control/failsafe.py` is the field controller: it keeps the last known-good plan on local disk and keeps cycling safely with no
connection to the centre (checked over a simulated 4-hour outage). New plans from the centre are taken at the next cycle boundary.
