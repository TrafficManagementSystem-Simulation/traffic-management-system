"""Application entry point.

Run:  uvicorn tms.main:create_app --factory --app-dir src --reload
Then open http://localhost:8000 (pages) or http://localhost:8000/docs (API).
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from importlib.util import find_spec
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from tms.common import clock, db
from tms.common.config import Settings, get_settings
from tms.common.errors import register_handlers
from tms.common.logging import setup_logging
from tms.ui import routes as ui_routes

log = logging.getLogger("tms")

# Each module owner's API. A module that has not been merged yet is skipped, so the shared
# skeleton and every person's pull request can be merged one at a time with CI green.
MODULE_ROUTERS = ("tms.admin.api", "tms.detection.api", "tms.signal_control.api", "tms.simulation.api", "tms.incident.api")

def available(module: str) -> bool:
    """True if ``module`` exists in this checkout."""
    try:
        return find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _tick_all() -> None:
    from tms.admin import config_service
    from tms.signal_control import controller

    with db.session_scope() as session:
        for item in config_service.list_intersections(session):
            controller.tick(session, item["id"], clock.now())
            if available("tms.incident.service"):
                from tms.incident import service as incident_service
                incident_service.scan(session, item["id"], clock.now())
            


async def _tick_loop() -> None:
    """Advance every signal once a second so the operator page shows live phases."""
    while True:
        await asyncio.sleep(1)
        try:
            await asyncio.to_thread(_tick_all)
        except Exception:  # noqa: BLE001 - keep the loop alive, log and carry on
            log.exception("signal tick failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ticking = app.state.settings.autotick and available("tms.signal_control.controller") and available("tms.admin.config_service")
    task = asyncio.create_task(_tick_loop()) if ticking else None
    try:
        yield
    finally:
        if task:
            task.cancel()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()
    db.configure(settings.database_url)
    db.init_db()
    if settings.seed_demo and available("tms.admin.rbac"):
        from tms.common.seed import seed_demo

        with db.session_scope() as session:
            seed_demo(session)

    app = FastAPI(title="Traffic Management System (Simulation)", version="0.1.0-sprint1", lifespan=lifespan)
    app.state.settings = settings
    # --- ADDED: wire up the emergency-dispatch service if the incident module is present ---
    if available("tms.incident.dispatch"):
        from tms.incident.dispatch import LoopbackEmergencyService
        app.state.emergency_service = LoopbackEmergencyService()
    # --- END ADDED ---
    register_handlers(app)
    for name in MODULE_ROUTERS:
        if available(name):
            app.include_router(importlib.import_module(name).router)
    app.include_router(ui_routes.router)
    static_dir = Path(__file__).parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app