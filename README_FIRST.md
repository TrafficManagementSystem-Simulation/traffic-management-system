# What's in this package

Copy these folders straight into your local clone of
`traffic-management-system` (same paths, no renaming).

## Covers your 5 Sprint 1 issues

| Issue | Files that close it |
|---|---|
| **#7 TMS-F-006** Vehicle classification | `src/tms/detection/classifier.py`, `tests/unit/detection/test_classifier_and_synthetic.py` |
| **#33 TMS-F-007** Vehicle counting per lane | `src/tms/detection/counter.py`, `tests/unit/detection/test_counting_and_pedestrians.py` |
| **#8 TMS-F-008** Pedestrian detection | `src/tms/detection/pedestrian.py`, (same test file as above) |
| **#36 UI: Detection live counts page** | `src/tms/ui/templates/detection.html` |
| **#9 Sprint 1 integration test suite** | `tests/integration/test_sprint1_flows.py`, `docs/test-cases.md`, `docs/rtm.md` |

Also included because your code needs them: `src/tms/detection/api.py`,
`src/tms/detection/models.py`, `src/tms/detection/synthetic.py`,
`data/detection_samples/` (synthetic feed + validation set), and
`tests/unit/detection/test_detection_api.py`.

## Important — this will NOT run yet on your machine

I checked `main` on GitHub directly before building this. Right now:

- `requirements.txt` is **empty** (0 bytes) — nothing installs
- `src/tms/main.py` and `src/tms/common/db.py` exist but are **empty** (0 bytes)
- `src/tms/ui/routes.py`, `src/tms/ui/templates/base.html`, `src/tms/admin/` **don't exist yet**

Your `api.py`, `counter.py`, `models.py` etc. all `import` from
`tms.common.db`, `tms.common.clock`, `tms.common.errors`, and
`tms.admin.rbac` / `tms.admin.config_service`. None of that exists on
`main` yet — it's Naveen's (common/main.py) and Roshini's (admin/) work.

**So pushing this now will fail `pytest` in CI**, through no fault of
yours — the shared skeleton underneath it isn't filled in, only
scaffolded as empty files. Per the PR guide, PR1 (Naveen) and PR2
(Roshini) are supposed to merge *before* PR3 (you). Worth flagging to
Naveen today, since right now almost nothing on `main` is actually
runnable — `requirements.txt` included.

## Once PR1 and PR2 are actually in
```bash
git checkout main && git pull
git checkout -b feature/detection
# copy src/, tests/, data/ from this package into the repo root
pytest
git add . && git commit -m "F-006/007/008: vehicle classification, counting, pedestrian detection"
git push -u origin feature/detection
```
PR description: `Closes #7, #33, #8, #36` + test case IDs `TC-VDC-01`,
`TC-VDC-02`, `TC-VDC-03`.

The integration suite (`#9`) and docs go in a **separate**, later PR
(`feature/integration-tests-and-docs`) — it has to come after Manoj's
and Naveen's PRs merge too, since it tests detection → signal control
→ audit log end to end.
