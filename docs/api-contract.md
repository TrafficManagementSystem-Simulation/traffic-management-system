# Public API contract for GIS and city dashboards (TMS-NF-010)

Version **1.0**. Everything is under `/api/v1/`. Fields are only added within 1.x; renaming or removing one means `/api/v2`.
Sign in with `POST /api/v1/auth/login` and send `Authorization: Bearer <token>`.

| Endpoint | Returns |
|---|---|
| `GET /api/v1/meta` (public) | `{apiVersion, docs, openapi, endpoints[]}` |
| `GET /api/v1/gis/intersections` | GeoJSON `FeatureCollection`; each `Point` is `[longitude, latitude]` with `properties` `id, name, mode, phase, stage, secondsRemaining, planVersion` |
| `GET /api/v1/city/summary` | `{apiVersion, intersections, adaptive, manual, pedestriansWaiting}` |
| `GET /openapi.json` | the full machine-readable description of every endpoint |

Errors always look like `{"error": "<code>", "detail": ...}` (400 bad request, 401 not signed in, 403 not allowed, 404 not found,
409 conflict, 422 invalid values). The contract is checked in code (`infra/interop_contract.py`) and exercised by a sample third-party client
(`infra/interop_client.py`, test TC-Interop-01).
