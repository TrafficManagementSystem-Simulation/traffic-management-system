"""Read-only, versioned interface for third-party GIS and city dashboards (TMS-NF-010)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tms.admin import config_service, rbac
from tms.common import clock
from tms.common.db import get_db
from tms.infra.interop_contract import API_VERSION
from tms.signal_control import controller

router = APIRouter(prefix="/api/v1", tags=["interoperability"])


@router.get("/meta")
def meta():
    """Public: which version of the contract this server speaks."""
    return {"apiVersion": API_VERSION, "docs": "/docs", "openapi": "/openapi.json",
            "endpoints": ["/api/v1/gis/intersections", "/api/v1/city/summary", "/api/v1/meta"]}


@router.get("/gis/intersections")
def gis_intersections(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role())):
    features = []
    now = clock.now()
    for item in config_service.list_intersections(db):
        cfg = config_service.get_intersection_config(db, item["id"])
        state = controller.view_state(db, item["id"], now)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [cfg["longitude"], cfg["latitude"]]},
            "properties": {"id": item["id"], "name": item["name"], "mode": state["mode"], "phase": state["phase"],
                           "stage": state["stage"], "secondsRemaining": state["secondsRemaining"],
                           "planVersion": state["planVersion"]},
        })
    return {"type": "FeatureCollection", "apiVersion": API_VERSION, "features": features}


@router.get("/city/summary")
def city_summary(db: Session = Depends(get_db), _: rbac.CurrentUser = Depends(rbac.require_role())):
    now = clock.now()
    states = [controller.view_state(db, i["id"], now) for i in config_service.list_intersections(db)]
    return {"apiVersion": API_VERSION, "intersections": len(states),
            "adaptive": len([s for s in states if s["mode"] == "adaptive"]),
            "manual": len([s for s in states if s["mode"] == "manual"]),
            "pedestriansWaiting": sum(s["pedestriansWaiting"] for s in states)}
