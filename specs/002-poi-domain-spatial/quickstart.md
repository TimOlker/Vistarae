# Quickstart Validation Guide: Point of Interest Domain & Geospatial Engine

**Feature**: `002-poi-domain-spatial`  
**Date**: 2026-10-19  
**Status**: Completed  
**Author**: Antigravity  

---

## 1. Prerequisites & Environment Setup

Ensure the local Docker PostGIS container is active and dependencies are up to date:

```bash
# 1. Start local PostGIS and ElasticMQ dependencies
docker compose up -d

# 2. Sync workspace dependencies with uv
uv sync

# 3. Apply database migrations to head (runs 0001 and 0002_poi_domain_spatial)
uv run alembic upgrade head

# 4. Verify local gateway is running (port 8030)
uv run uvicorn services.local_gateway:app --reload --port 8030
```

---

## 2. Automated Test Execution

Run the targeted unit and integration test suite with coverage enforcement:

```bash
# Run all unit tests for POI domain, repositories, and geospatial adapters
uv run pytest tests/unit/services/poi/ -v

# Run the complete test suite asserting >= 90% branch and line coverage
uv run pytest --cov=packages/core --cov=services --cov-fail-under=90
```

---

## 3. End-to-End Validation Scenarios

Set a test JWT authorization token:
```bash
export AUTH_HEADER="Authorization: Bearer <TEST_USER_JWT>"
```

### Scenario 1: Create a POI with Geocoding and AI Vector Embeddings
```bash
curl -X POST "http://localhost:8030/api/pois" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Glacier Point Overlook",
    "description": "Dramatic granite overlook towering 3,214 feet above Yosemite Valley with sweeping vistas of Half Dome.",
    "lon": -119.5742,
    "lat": 37.7304,
    "visit_state": "not_visited",
    "rating": 5,
    "recommended_duration_hours": 2.5,
    "tag_names": ["viewpoint", "yosemite", "scenic"]
  }'
```
*Expected Outcome*: HTTP 201 Created with populated `id`, canonical `lon`/`lat`, `enrichment_status = 'SUCCESS'`, and tags assigned.

---

### Scenario 2: Planar Bounding-Box Viewport Query
Fetch all POIs within a bounding box covering Yosemite National Park:
```bash
curl -X GET "http://localhost:8030/api/pois?bbox=-120.0,37.0,-119.0,38.0&visit_state=not_visited&hierarchy=all" \
  -H "$AUTH_HEADER"
```
*Expected Outcome*: HTTP 200 OK returning only POIs within the geographic envelope, completed in $< 75$ms p95 latency backed by `idx_pois_user_geom_geometry`.

---

### Scenario 3: Deduplication Detection Probe
Probe for collision against an existing POI using trigram similarity and geodesic proximity:
```bash
curl -X GET "http://localhost:8030/api/pois/dedup-check?name=Glacier+Point&lon=-119.5745&lat=37.7302&preset=urban" \
  -H "$AUTH_HEADER"
```
*Expected Outcome*: HTTP 200 OK returning a list of `matches` with `distance_meters < 805` and `name_similarity >= 0.60`.

---

### Scenario 4: Interactive Record Merge
Merge a duplicate record into the canonical target POI:
```bash
curl -X POST "http://localhost:8030/api/pois/merge" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "target_poi_id": "<TARGET_POI_UUID>",
    "source_poi_id": "<SOURCE_POI_UUID>",
    "use_source_for": ["description", "official_url"],
    "merge_tags": true
  }'
```
*Expected Outcome*: HTTP 200 OK with the target record updated, subordinate children re-parented, and source POI deleted. If merging would create a cyclic hierarchy, returns HTTP 400 Bad Request with RFC 7807 `ProblemDetails`.

---

### Scenario 5: Semantic AI Vector Search
Query POIs conceptually without matching exact keywords:
```bash
curl -X GET "http://localhost:8030/api/pois?semantic_q=breathtaking+high+granite+cliffs" \
  -H "$AUTH_HEADER"
```
*Expected Outcome*: HTTP 200 OK returning ranked POIs with `similarity_score` (between 0.0 and 1.0) sorted by cosine similarity distance.

---

## 4. References

- Data models & entity schemas: [data-model.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/data-model.md)
- OpenAPI 3.1 Contract: [poi-api.yaml](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/contracts/poi-api.yaml)
- Architecture decisions: [research.md](file:///d:/Coding/Vistarae/specs/002-poi-domain-spatial/research.md)
