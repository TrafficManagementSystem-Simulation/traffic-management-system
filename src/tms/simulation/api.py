"""Simulation endpoints (Naveen). Analysts and administrators only."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from tms.admin import rbac
from tms.common.db import get_db
from tms.common.errors import NotFoundError
from tms.simulation import compare as compare_mod
from tms.simulation import metrics as metrics_mod
from tms.simulation.engine import run_simulation
from tms.simulation.models import SimComparison, SimNetwork, SimRun
from tms.simulation.network import check_or_raise, validate_network

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])
SIM_ROLES = (rbac.ANALYST, rbac.ADMINISTRATOR)


def sample_dir() -> Path:
    override = os.getenv("TMS_SAMPLE_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[3] / "data" / "sample_networks"


class NetworkIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    topology: dict


class SampleIn(BaseModel):
    name: str


class RunIn(BaseModel):
    networkId: int
    durationSeconds: int = 3600
    seed: int = 42
    demandScale: float = 1.0
    greenOverrides: Optional[dict] = None


def _network_row(db: Session, network_id: int) -> SimNetwork:
    row = db.get(SimNetwork, network_id)
    if row is None:
        raise NotFoundError(f"Network {network_id} does not exist", code="network_not_found")
    return row


@router.post("/networks/validate")
def validate(body: dict, _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    errors = validate_network(body)
    return {"valid": not errors, "errors": errors}


@router.post("/networks", status_code=201)
def create_network(body: NetworkIn, db: Session = Depends(get_db),
                   user: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    topology = check_or_raise(body.topology)
    row = SimNetwork(name=body.name, topology=json.dumps(topology), created_by=user.username)
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "nodes": len(topology["nodes"]), "links": len(topology["links"])}


@router.get("/samples")
def samples(_: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    folder = sample_dir()
    return sorted(p.stem for p in folder.glob("*.json")) if folder.exists() else []


@router.post("/networks/import-sample", status_code=201)
def import_sample(body: SampleIn, db: Session = Depends(get_db),
                  user: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    path = sample_dir() / f"{Path(body.name).name}.json"   # Path(...).name blocks folder tricks
    if not path.exists():
        raise NotFoundError(f"Sample '{body.name}' does not exist", code="sample_not_found")
    topology = check_or_raise(json.loads(path.read_text()))
    row = SimNetwork(name=topology.get("name", body.name), topology=json.dumps(topology), created_by=user.username)
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "nodes": len(topology["nodes"]), "links": len(topology["links"])}


@router.get("/networks")
def list_networks(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    rows = db.scalars(select(SimNetwork).order_by(SimNetwork.id)).all()
    return [{"id": r.id, "name": r.name, "createdAt": r.created_at.isoformat()} for r in rows]


@router.get("/networks/{network_id}")
def get_network(network_id: int, db: Session = Depends(get_db),
                _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = _network_row(db, network_id)
    return {"id": row.id, "name": row.name, "topology": json.loads(row.topology)}


@router.post("/runs", status_code=201)
def run(body: RunIn, db: Session = Depends(get_db), user: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = _network_row(db, body.networkId)
    params = {"duration_seconds": body.durationSeconds, "seed": body.seed, "demand_scale": body.demandScale,
              "green_overrides": body.greenOverrides or {}}
    started = time.perf_counter()
    result = run_simulation(json.loads(row.topology), params)
    metric_started = time.perf_counter()
    metrics = metrics_mod.compute_metrics(result)
    metrics["metricsComputeMs"] = round((time.perf_counter() - metric_started) * 1000, 2)
    metrics["runSeconds"] = round(time.perf_counter() - started, 2)
    saved = SimRun(network_id=row.id, params=json.dumps(result["params"]), metrics=json.dumps(metrics),
                   trajectories=json.dumps(result["trajectories"]), created_by=user.username)
    db.add(saved)
    db.commit()
    return {"runId": saved.id, "networkId": row.id, "params": result["params"], "metrics": metrics}


@router.get("/runs")
def list_runs(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    rows = db.scalars(select(SimRun).order_by(SimRun.id.desc())).all()
    return [{"runId": r.id, "networkId": r.network_id, "createdAt": r.created_at.isoformat(),
             "metrics": json.loads(r.metrics)} for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = db.get(SimRun, run_id)
    if row is None:
        raise NotFoundError(f"Run {run_id} does not exist", code="run_not_found")
    return {"runId": row.id, "networkId": row.network_id, "params": json.loads(row.params),
            "metrics": json.loads(row.metrics)}


@router.get("/runs/{run_id}/trajectories")
def get_trajectories(run_id: int, db: Session = Depends(get_db),
                     _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = db.get(SimRun, run_id)
    if row is None:
        raise NotFoundError(f"Run {run_id} does not exist", code="run_not_found")
    return {"runId": row.id, "trajectories": json.loads(row.trajectories)}


# ---------- scenario comparison (TMS-F-012) ----------

class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    greenOverrides: Optional[dict] = None
    demandScale: Optional[float] = None


class CompareIn(BaseModel):
    networkId: int
    durationSeconds: int = 3600
    seed: int = 42
    demandScale: float = 1.0
    scenarios: list[ScenarioIn]


@router.post("/comparisons", status_code=201)
def create_comparison(body: CompareIn, db: Session = Depends(get_db),
                      user: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = _network_row(db, body.networkId)
    common = {"duration_seconds": body.durationSeconds, "seed": body.seed, "demand_scale": body.demandScale}
    scenarios = [{"name": s.name, "green_overrides": s.greenOverrides, "demand_scale": s.demandScale}
                 for s in body.scenarios]
    outcome = compare_mod.compare(json.loads(row.topology), scenarios, common)
    run_ids = {}
    for item in outcome["scenarios"]:          # every scenario is also kept as a normal run
        saved = SimRun(network_id=row.id, params=json.dumps(item["params"]), metrics=json.dumps(item["metrics"]),
                       trajectories=json.dumps(item["trajectories"]), created_by=user.username)
        db.add(saved)
        db.flush()
        run_ids[item["name"]] = saved.id
    result = {"baseline": outcome["baseline"], "differences": outcome["differences"], "best": outcome["best"],
              "disclaimer": outcome["disclaimer"],
              "scenarios": [{"name": i["name"], "runId": run_ids[i["name"]], "params": i["params"],
                             "metrics": i["metrics"]} for i in outcome["scenarios"]]}
    comparison = SimComparison(network_id=row.id, params=json.dumps({**common, "scenarios": scenarios}),
                               result=json.dumps(result), created_by=user.username)
    db.add(comparison)
    db.commit()
    return {"comparisonId": comparison.id, "networkId": row.id, **result}


@router.get("/comparisons")
def list_comparisons(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    rows = db.scalars(select(SimComparison).order_by(SimComparison.id.desc())).all()
    return [{"comparisonId": r.id, "networkId": r.network_id, "createdAt": r.created_at.isoformat(),
             "baseline": json.loads(r.result)["baseline"],
             "scenarios": [s["name"] for s in json.loads(r.result)["scenarios"]]} for r in rows]


@router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: int, db: Session = Depends(get_db),
                   _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    row = db.get(SimComparison, comparison_id)
    if row is None:
        raise NotFoundError(f"Comparison {comparison_id} does not exist", code="comparison_not_found")
    return {"comparisonId": row.id, "networkId": row.network_id, **json.loads(row.result)}


# ---------- replay (TMS-F-013) ----------

@router.get("/runs/{run_id}/replay")
def replay(run_id: int, speed: str = "1", db: Session = Depends(get_db),
           _: rbac.CurrentUser = Depends(rbac.require_role(*SIM_ROLES))):
    chosen = compare_mod.parse_speed(speed)
    row = db.get(SimRun, run_id)
    if row is None:
        raise NotFoundError(f"Run {run_id} does not exist", code="run_not_found")
    params = json.loads(row.params)
    return {"runId": row.id, "networkId": row.network_id, "durationSeconds": params["duration_seconds"],
            **compare_mod.replay_frames(json.loads(row.trajectories), chosen)}
