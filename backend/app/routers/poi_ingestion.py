# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""API Router for multi-format POI bulk ingestion, preset library, data quality validation, and conflict resolution."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.schemas.ingestion import (
    IngestCommitRequest,
    IngestCommitResponse,
    IngestParseRequest,
    IngestPreviewResponse,
    PresetSummary,
)
from app.schemas.poi import CollisionStatus
from app.services.auth import get_current_user
from app.services.ingestion import (
    detect_conflicts_for_candidates,
    enrich_and_geocode_candidates,
    execute_ingest_commit,
)
from app.services.poi_parser import (
    extract_raw_records,
    standardize_poi_candidates,
)

logger = logging.getLogger("vistarae.api.poi_ingestion")

router = APIRouter(prefix="/api/v1/pois/ingest", tags=["POI Ingestion"])

PRESETS_DIR = Path(__file__).resolve().parent.parent / "data" / "presets"


@router.get("/presets", response_model=list[PresetSummary])
async def list_ingestion_presets(
    current_user: User = Depends(get_current_user),
) -> list[PresetSummary]:
    """Returns available curated POI presets for one-click ingestion."""
    presets = []

    # NPS National Parks
    nps_file = PRESETS_DIR / "nps_national_parks.json"
    if nps_file.exists():
        try:
            with open(nps_file, encoding="utf-8") as f:
                data = json.load(f)
                presets.append(
                    PresetSummary(
                        id="nps_national_parks",
                        title="US National Park Service - 63 National Parks",
                        description="All 63 official US National Parks with verified coordinates, states, descriptions, and NPS tags.",
                        count=len(data),
                        tags=["NPS", "national park"],
                    )
                )
        except Exception as exc:
            logger.warning(f"Error reading nps_national_parks.json preset: {exc}")

    # UNESCO World Heritage
    unesco_file = PRESETS_DIR / "unesco_world_heritage.json"
    if unesco_file.exists():
        try:
            with open(unesco_file, encoding="utf-8") as f:
                data = json.load(f)
                presets.append(
                    PresetSummary(
                        id="unesco_world_heritage",
                        title="UNESCO World Heritage Sites (US & Global Highlights)",
                        description="Curated UNESCO World Heritage cultural and natural landmarks with coordinates, country codes, and UNESCO tags.",
                        count=len(data),
                        tags=["UNESCO", "world heritage"],
                    )
                )
        except Exception as exc:
            logger.warning(f"Error reading unesco_world_heritage.json preset: {exc}")

    return presets


@router.get("/presets/{preset_id}")
async def get_preset_content(
    preset_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieves raw content for a specific curated preset."""
    file_path = PRESETS_DIR / f"{preset_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found.")

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return {"preset_id": preset_id, "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read preset: {exc}") from exc


@router.post("/parse-and-preview", response_model=IngestPreviewResponse)
async def parse_and_preview_pois(
    payload: IngestParseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestPreviewResponse:
    """Parses raw content (CSV, TSV, JSON, GeoJSON, XML, KML, GPX),
    maps headers, validates required site names, evaluates data quality flags,
    performs bi-directional geocoding, and evaluates collisions against existing POIs.
    """
    if not payload.content or not payload.content.strip():
        raise HTTPException(
            status_code=400,
            detail="No content provided for parsing.",
        )

    # 1. Extract raw records and headers based on format detection
    try:
        raw_records, headers, detected_format = extract_raw_records(
            content=payload.content,
            filename=payload.filename,
            format_hint=payload.format_hint,
        )
    except Exception as exc:
        logger.error(f"Failed to extract raw records: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse input as {payload.format_hint or 'data'}: {str(exc)}",
        ) from exc

    # 2. Standardize candidate POIs and enforce required fields
    candidates, field_mappings = standardize_poi_candidates(
        raw_records=raw_records,
        headers=headers,
        default_tags=payload.default_tags,
        filename=payload.filename,
        detected_format=detected_format,
    )

    # 3. Bi-directional geocoding (Coordinates <-> Address)
    if payload.perform_geocoding:
        candidates = await enrich_and_geocode_candidates(
            candidates=candidates,
            db=db,
            perform_geocoding=True,
        )

    # 4. Conflict detection against existing POIs
    await detect_conflicts_for_candidates(
        candidates=candidates,
        user_id=current_user.id,
        db=db,
    )

    # 5. Calculate summary metrics
    valid_count = sum(1 for c in candidates if c.quality.is_valid)
    flagged_count = sum(1 for c in candidates if len(c.quality.flags) > 0)
    conflict_count = sum(
        1 for c in candidates if c.collision_status != CollisionStatus.UNIQUE_LOCATION
    )

    return IngestPreviewResponse(
        detected_format=detected_format,
        total_records=len(candidates),
        valid_records=valid_count,
        flagged_records=flagged_count,
        conflict_count=conflict_count,
        headers_found=headers,
        field_mappings=field_mappings,
        items=candidates,
    )


@router.post("/commit", response_model=IngestCommitResponse)
async def commit_ingested_pois(
    payload: IngestCommitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestCommitResponse:
    """Commits confirmed candidate POIs into PostgreSQL/PostGIS based on selected conflict actions."""
    if not payload.items:
        raise HTTPException(
            status_code=400,
            detail="No items provided to commit.",
        )

    response = await execute_ingest_commit(
        items=payload.items,
        default_tags=payload.default_tags,
        target_list_id=payload.target_list_id,
        new_list_title=payload.new_list_title,
        list_membership_scope=payload.list_membership_scope,
        user_id=current_user.id,
        db=db,
    )

    return response
