# Code Coverage Report

Run date: 2026-11-19  |  Tool: coverage.py 7 via pytest-cov, branch coverage on  |  Measured over: unit + system tests combined

## Overall

| Statements | Missed | Branches | Partial branches | Coverage |
|---|---|---|---|---|
| 2983 | 123 | 758 | 76 | **94%** |

## Per package

| Package | Statements | Missed | Coverage |
|---|---|---|---|
| admin | 401 | 12 | 97% |
| common | 212 | 11 | 95% |
| detection | 348 | 5 | 99% |
| incident | 295 | 2 | 99% |
| infra | 327 | 9 | 97% |
| (app root) | 105 | 43 | 59% |
| reporting | 175 | 2 | 99% |
| signal_control | 565 | 7 | 99% |
| simulation | 539 | 32 | 94% |
| ui | 16 | 0 | 100% |

## Per file

| File | Statements | Missed | Branches | Partial | Coverage |
|---|---|---|---|---|---|
| `tms/admin/api.py` | 79 | 0 | 0 | 0 | 100% |
| `tms/admin/config_service.py` | 97 | 7 | 38 | 7 | 90% |
| `tms/admin/mfa.py` | 36 | 0 | 8 | 0 | 100% |
| `tms/admin/models.py` | 40 | 0 | 0 | 0 | 100% |
| `tms/admin/rbac.py` | 149 | 5 | 40 | 4 | 95% |
| `tms/common/clock.py` | 23 | 2 | 4 | 2 | 85% |
| `tms/common/config.py` | 50 | 0 | 10 | 0 | 100% |
| `tms/common/db.py` | 68 | 9 | 14 | 3 | 83% |
| `tms/common/errors.py` | 45 | 0 | 6 | 0 | 100% |
| `tms/common/logging.py` | 8 | 0 | 2 | 0 | 100% |
| `tms/common/seed.py` | 18 | 0 | 8 | 2 | 92% |
| `tms/detection/api.py` | 111 | 1 | 20 | 1 | 98% |
| `tms/detection/classifier.py` | 23 | 0 | 8 | 0 | 100% |
| `tms/detection/counter.py` | 50 | 3 | 16 | 3 | 91% |
| `tms/detection/evidence.py` | 57 | 1 | 10 | 1 | 97% |
| `tms/detection/models.py` | 55 | 0 | 0 | 0 | 100% |
| `tms/detection/pedestrian.py` | 20 | 0 | 0 | 0 | 100% |
| `tms/detection/synthetic.py` | 32 | 0 | 8 | 0 | 100% |
| `tms/incident/api.py` | 38 | 0 | 0 | 0 | 100% |
| `tms/incident/detector.py` | 53 | 1 | 14 | 1 | 97% |
| `tms/incident/dispatch.py` | 46 | 0 | 6 | 0 | 100% |
| `tms/incident/models.py` | 36 | 0 | 0 | 0 | 100% |
| `tms/incident/security_monitor.py` | 50 | 0 | 16 | 2 | 97% |
| `tms/incident/service.py` | 72 | 1 | 22 | 1 | 98% |
| `tms/infra/api.py` | 42 | 0 | 0 | 0 | 100% |
| `tms/infra/backup.py` | 107 | 4 | 26 | 3 | 95% |
| `tms/infra/interop_api.py` | 26 | 0 | 2 | 0 | 100% |
| `tms/infra/interop_client.py` | 14 | 1 | 2 | 1 | 88% |
| `tms/infra/interop_contract.py` | 20 | 1 | 12 | 1 | 94% |
| `tms/infra/models.py` | 16 | 0 | 0 | 0 | 100% |
| `tms/infra/tls.py` | 26 | 0 | 0 | 0 | 100% |
| `tms/infra/uptime.py` | 76 | 3 | 24 | 3 | 94% |
| `tms/main.py` | 105 | 43 | 30 | 5 | 53% |
| `tms/reporting/api.py` | 37 | 0 | 6 | 0 | 100% |
| `tms/reporting/generator.py` | 77 | 2 | 24 | 0 | 98% |
| `tms/reporting/models.py` | 16 | 0 | 0 | 0 | 100% |
| `tms/reporting/scheduler.py` | 45 | 0 | 12 | 0 | 100% |
| `tms/signal_control/api.py` | 63 | 0 | 10 | 0 | 100% |
| `tms/signal_control/audit.py` | 26 | 1 | 6 | 2 | 91% |
| `tms/signal_control/controller.py` | 198 | 3 | 64 | 5 | 97% |
| `tms/signal_control/coordination.py` | 50 | 0 | 28 | 0 | 100% |
| `tms/signal_control/failsafe.py` | 76 | 3 | 20 | 1 | 96% |
| `tms/signal_control/models.py` | 39 | 0 | 0 | 0 | 100% |
| `tms/signal_control/override.py` | 53 | 0 | 14 | 0 | 100% |
| `tms/signal_control/preemption.py` | 35 | 0 | 8 | 0 | 100% |
| `tms/signal_control/timing_plugins.py` | 25 | 0 | 4 | 0 | 100% |
| `tms/simulation/api.py` | 124 | 4 | 14 | 0 | 97% |
| `tms/simulation/compare.py` | 18 | 0 | 8 | 0 | 100% |
| `tms/simulation/engine.py` | 164 | 5 | 72 | 7 | 95% |
| `tms/simulation/generators.py` | 10 | 0 | 4 | 0 | 100% |
| `tms/simulation/metrics.py` | 10 | 0 | 0 | 0 | 100% |
| `tms/simulation/models.py` | 22 | 0 | 0 | 0 | 100% |
| `tms/simulation/network.py` | 150 | 23 | 104 | 21 | 83% |
| `tms/simulation/replay.py` | 41 | 0 | 12 | 0 | 100% |
| `tms/ui/routes.py` | 16 | 0 | 2 | 0 | 100% |

## Notes

- `main.py` is lowest (about 53%): its uncovered lines are the background tick loop and server start-up, which run only under a live server and are shown in the demo rather than unit-tested.
- `simulation/network.py` (83%) misses mostly error branches for malformed network files.
- Full line-by-line HTML report: open `reports/coverage-html/index.html`. Machine-readable: `reports/coverage.xml`.

## How to reproduce

```
pip install -r requirements.txt pytest-cov
pytest --cov --cov-report=term --cov-report=html
```
