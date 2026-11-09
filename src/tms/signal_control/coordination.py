"""Green-wave coordination (TMS-F-005): offsets that let a platoon cross a corridor without stopping.

Pure functions, so they are easy to test. ``corridor`` looks like::

    {"targetSpeedMps": 13.9, "cycleSeconds": 90, "greenSeconds": 40,
     "intersections": [{"id": "S1"}, {"id": "S2", "distanceFromPreviousM": 400}, ...]}
"""
from __future__ import annotations

from tms.common.errors import ValidationFailure


def _check(corridor: dict) -> list[dict]:
    problems = []
    nodes = corridor.get("intersections")
    if not isinstance(nodes, list) or len(nodes) < 2:
        problems.append("a corridor needs at least two intersections")
        nodes = []
    for key, low, high in (("targetSpeedMps", 3, 30), ("cycleSeconds", 40, 180), ("greenSeconds", 10, 120)):
        value = corridor.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            problems.append(f"{key} must be a number between {low} and {high}")
    for index, node in enumerate(nodes[1:], start=1):
        distance = node.get("distanceFromPreviousM") if isinstance(node, dict) else None
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not 20 <= distance <= 5000:
            problems.append(f"intersection {index} needs distanceFromPreviousM between 20 and 5000")
    if not problems and corridor["greenSeconds"] >= corridor["cycleSeconds"]:
        problems.append("greenSeconds must be shorter than cycleSeconds")
    if problems:
        raise ValidationFailure(problems)
    return nodes


def compute_offsets(corridor: dict) -> list[dict]:
    """Offset of each intersection's green start, in seconds after the first one (which is 0)."""
    nodes = _check(corridor)
    cycle, speed = corridor["cycleSeconds"], corridor["targetSpeedMps"]
    result, travelled = [], 0.0
    for index, node in enumerate(nodes):
        if index:
            travelled += node["distanceFromPreviousM"]
        result.append({"id": node["id"], "offsetSeconds": round((travelled / speed) % cycle, 1),
                       "travelSeconds": round(travelled / speed, 1)})
    return result


def platoon_stops(corridor: dict, offsets: list[float], platoon_seconds: float = 10.0) -> int:
    """How many intersections a platoon (leader arrives at the first green start, ``platoon_seconds`` long)
    has to stop at when driving at the target speed. 0 means a clean green wave."""
    nodes = _check(corridor)
    cycle, green, speed = corridor["cycleSeconds"], corridor["greenSeconds"], corridor["targetSpeedMps"]
    stops, travelled = 0, 0.0
    for index, node in enumerate(nodes):
        if index:
            travelled += node["distanceFromPreviousM"]
        arrival = travelled / speed
        into_green = (arrival - offsets[index]) % cycle
        if into_green + platoon_seconds > green and into_green != 0:
            stops += 1
    return stops


def apply_to_network(network: dict, offsets: list[dict]) -> dict:
    """Return a copy of a simulation network with each signal's ``offset`` set (used to compare runs)."""
    import copy

    result = copy.deepcopy(network)
    by_id = {item["id"]: int(round(item["offsetSeconds"])) for item in offsets}
    for node in result["nodes"]:
        if node.get("type") == "signal" and node["id"] in by_id:
            node["signal"]["offset"] = by_id[node["id"]]
    return result
