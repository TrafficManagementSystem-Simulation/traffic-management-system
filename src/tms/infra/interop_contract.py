"""The published contract for third-party GIS and city-dashboard clients (TMS-NF-010).

Version 1.0. Fields are only ever added in 1.x; renaming or removing one means /api/v2.
"""
from __future__ import annotations

API_VERSION = "1.0"

# field -> type name, for the properties of every GeoJSON feature at /api/v1/gis/intersections
FEATURE_PROPERTIES = {"id": "string", "name": "string", "mode": "string", "phase": "string", "stage": "string",
                      "secondsRemaining": "number", "planVersion": "integer"}


def check_feature_collection(document: dict) -> list[str]:
    """Return what is wrong with ``document`` compared to the contract (empty list: it conforms)."""
    types = {"string": str, "number": (int, float), "integer": int}
    problems: list[str] = []
    if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        return ["expected a GeoJSON FeatureCollection"]
    if document.get("apiVersion") != API_VERSION:
        problems.append("apiVersion missing or different")
    for index, feature in enumerate(document["features"]):
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")
        if feature.get("type") != "Feature" or geometry.get("type") != "Point" or not (
                isinstance(coords, list) and len(coords) == 2 and all(isinstance(c, (int, float)) for c in coords)):
            problems.append(f"feature {index}: needs a Point geometry with [longitude, latitude]")
        props = feature.get("properties") or {}
        for name, kind in FEATURE_PROPERTIES.items():
            if not isinstance(props.get(name), types[kind]) or isinstance(props.get(name), bool):
                problems.append(f"feature {index}: property {name} must be a {kind}")
    return problems
