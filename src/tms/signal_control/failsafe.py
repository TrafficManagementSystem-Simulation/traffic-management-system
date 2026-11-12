"""Field controller fail-safe (TMS-NF-006).

``FieldController`` is the small piece of software that sits at the intersection. It keeps the last
known-good timing plan on local disk and keeps cycling safely when the central platform cannot be
reached (for at least 4 hours; there is no time limit in this code). When the link comes back it takes
the central plan again at the next cycle boundary.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from tms.signal_control.controller import PlanValidationError, validate_plan


def safe_default_plan(cfg: dict) -> dict:
    """Fixed timing that is always legal: the minimum green for every phase."""
    return {"green": {p: cfg["min_green"] for p in cfg["phases"]}, "yellow": cfg["yellow"], "all_red": cfg["all_red"]}


@dataclass
class Signal:
    phase: str
    stage: str          # GREEN | YELLOW | ALL_RED


class FieldController:
    def __init__(self, cfg: dict, start: datetime, store: Path | None = None, plan: dict | None = None):
        self.cfg = cfg
        self.store = store
        self.link_up = True
        self.source = "default"
        self.plan = safe_default_plan(cfg)
        loaded = self._load()
        if plan is not None and self._accept(plan):
            self.source = "central"
        elif loaded is not None:
            self.plan, self.source = loaded, "local-store"
        self.pending: dict | None = None
        self._start = start
        self._sequence = self._build_sequence()
        self._cycle_started = start

    # ---- plans ----
    def _accept(self, plan: dict) -> bool:
        try:
            validate_plan(plan, self.cfg)
        except PlanValidationError:
            return False
        self.plan = plan
        if self.store:
            self.store.write_text(json.dumps(plan))
        return True

    def _load(self) -> dict | None:
        if not self.store or not self.store.exists():
            return None
        try:
            plan = json.loads(self.store.read_text())
            validate_plan(plan, self.cfg)
            return plan
        except (ValueError, PlanValidationError, OSError):
            return None  # damaged file: fall back to the safe default plan

    def _build_sequence(self) -> list[tuple[Signal, int]]:
        steps: list[tuple[Signal, int]] = []
        for phase in self.cfg["phases"]:
            steps += [(Signal(phase, "GREEN"), self.plan["green"][phase]),
                      (Signal(phase, "YELLOW"), self.plan["yellow"]),
                      (Signal(phase, "ALL_RED"), self.plan["all_red"])]
        return steps

    def receive_plan(self, plan: dict) -> bool:
        """A plan from the central platform. Ignored while the link is down; used from the next cycle."""
        if not self.link_up:
            return False
        try:
            validate_plan(plan, self.cfg)
        except PlanValidationError:
            return False
        self.pending = plan
        return True

    # ---- running ----
    @property
    def cycle_seconds(self) -> int:
        return sum(seconds for _, seconds in self._sequence)

    def signal_at(self, now: datetime) -> Signal:
        elapsed = (now - self._cycle_started).total_seconds()
        while elapsed >= self.cycle_seconds:
            self._cycle_started += timedelta(seconds=self.cycle_seconds)
            elapsed = (now - self._cycle_started).total_seconds()
            if self.pending is not None and self._accept(self.pending):
                self.source, self.pending = "central", None
                self._sequence = self._build_sequence()
        for signal, seconds in self._sequence:
            if elapsed < seconds:
                return signal
            elapsed -= seconds
        return self._sequence[-1][0]
