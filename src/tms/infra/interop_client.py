"""A small third-party style client: reads the published API only, as a GIS or city dashboard would."""
from __future__ import annotations

from typing import Callable

from tms.infra.interop_contract import check_feature_collection


class CityDashboardClient:
    def __init__(self, get: Callable[[str], dict]):
        self.get = get                         # any function that returns the parsed JSON of a path

    def intersections(self) -> list[dict]:
        document = self.get("/api/v1/gis/intersections")
        problems = check_feature_collection(document)
        if problems:
            raise ValueError("; ".join(problems))
        return [{"id": f["properties"]["id"], "lon": f["geometry"]["coordinates"][0],
                 "lat": f["geometry"]["coordinates"][1], "stage": f["properties"]["stage"]} for f in document["features"]]

    def summary(self) -> dict:
        return self.get("/api/v1/city/summary")
