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

"""Staging service coordinating candidate lifecycle, deduplication, and multi-visit merge (T-028, T-038).

Implements:
- Hierarchical reverse geocoding fallback for missing street addresses (REQ-ING-003)
- Hierarchical forward geocoding fallback for missing coordinates (REQ-ING-004, REQ-ING-005)
- Spatial (<= 50m) and trigram (>= 0.60) duplicate detection against user POIs (REQ-ING-006, REQ-ING-007)
- Sublocation nesting detection near macro-sites (< 0.60 similarity) (REQ-ING-008)
- Automatic confidence-based disposition assignment (REQ-ING-009, REQ-ING-010)
- In-batch multi-visit duplicate detection across CSV rows (REQ-ING-006, REQ-ING-023)
- Phase 1 proceed and cancel transitions (REQ-ING-015, REQ-ING-016)
- Atomic database commit with multi-visit union merging (REQ-ING-023)
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from vistarae_core.domain.entities import IngestCandidate, POI
from vistarae_core.domain.exceptions import IngestCandidateNotFoundError
from vistarae_core.domain.value_objects import (
    AddressRecord,
    EnrichmentStatus,
    IngestCandidatePhaseState,
    IngestDisposition,
    PromptType,
    SourceType,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import IIngestCandidateRepository, IPOIRepository
from vistarae_core.schemas.ingest_staging import CandidateUpdateRequest
from vistarae_core.schemas.poi_export import POIExportRecord

from services.poi.services.duplicate_service import (
    haversine_distance_meters,
    trigram_similarity,
)

logger = logging.getLogger("vistarae.ingest.staging")


class StagingService:
    """Coordinates candidate staging, deduplication, triage, and database commit."""

    def __init__(
        self,
        candidate_repo: IIngestCandidateRepository,
        poi_repo: IPOIRepository | None = None,
        geocoding_service: Any | None = None,
        duplicate_service: Any | None = None,
        orchestrator: Any | None = None,
    ) -> None:
        """Initializes StagingService with repository and domain service adapters.

        Args:
            candidate_repo: Repository managing ingest_candidates table.
            poi_repo: Optional repository managing pois table.
            geocoding_service: Optional service for forward/reverse geocoding.
            duplicate_service: Optional service for scale-aware duplicate triage.
        """
        self._candidate_repo = candidate_repo
        self._poi_repo = poi_repo
        self._geocoding_service = geocoding_service
        self._duplicate_service = duplicate_service
        self._orchestrator = orchestrator

    async def _reverse_geocode_candidate(
        self,
        lat: float,
        lon: float,
    ) -> list[AddressRecord]:
        """Resolves missing address components via hierarchical reverse geocoding (REQ-ING-003)."""
        if not self._geocoding_service or not hasattr(self._geocoding_service, "reverse_geocode"):
            return []
        try:
            return await self._geocoding_service.reverse_geocode(lat, lon)
        except Exception as exc:
            logger.warning("MSG   |<- Reverse geocoding failed for (%s, %s): %s", lat, lon, exc)
            return []

    async def _forward_geocode_candidate(
        self,
        name: str,
        city: str | None,
        state: str | None,
        country: str | None,
    ) -> tuple[float | None, float | None, list[AddressRecord]]:
        """Resolves missing coordinates via hierarchical forward geocoding (REQ-ING-004)."""
        if not self._geocoding_service or not hasattr(self._geocoding_service, "geocode"):
            return None, None, []

        queries: list[str] = []
        if city and state and country:
            queries.append(f"{name}, {city}, {state}, {country}")
        if state and country:
            queries.append(f"{name}, {state}, {country}")
        if country:
            queries.append(f"{name}, {country}")
        queries.append(name)

        for query in queries:
            try:
                lat, lon, addrs, _ = await self._geocoding_service.geocode(query)
                if lat is not None and lon is not None:
                    return lat, lon, addrs
            except Exception as exc:
                logger.warning("Forward geocode query '%s' failed: %s", query, exc)

        return None, None, []

    def _check_in_batch_duplicate(
        self,
        name: str,
        lat: float | None,
        lon: float | None,
        staged_so_far: list[IngestCandidate],
    ) -> IngestCandidate | None:
        """Checks if candidate matches an earlier row in the same batch (REQ-ING-006)."""
        if lat is None or lon is None:
            return None

        for existing in staged_so_far:
            if existing.latitude is None or existing.longitude is None:
                continue
            dist = haversine_distance_meters(
                lat,
                lon,
                float(existing.latitude),
                float(existing.longitude),
            )
            sim = trigram_similarity(name, existing.poi_name)
            if dist <= 50.0 and sim >= 0.60:
                return existing
        return None

    async def stage_records(
        self,
        user_id: UUID,
        job_id: UUID,
        records: Sequence[POIExportRecord],
    ) -> Sequence[IngestCandidate]:
        """Stages parsed CSV records into ingest_candidates with deduplication and geocoding."""
        candidates_to_stage: list[IngestCandidate] = []

        for idx, rec in enumerate(records):
            lat = float(rec.latitude) if rec.latitude is not None else None
            lon = float(rec.longitude) if rec.longitude is not None else None

            street = rec.street_address[0] if rec.street_address else None
            city = rec.town_city[0] if rec.town_city else None
            state = rec.state_province[0] if rec.state_province else None
            postal = rec.zip_code[0] if rec.zip_code else None
            country = rec.country[0] if rec.country else None
            addresses_list: list[dict[str, Any]] = []

            # 1. Reverse geocoding fallback if coordinates exist but address is missing (REQ-ING-003)
            if lat is not None and lon is not None and not street:
                rev_addrs = await self._reverse_geocode_candidate(lat, lon)
                if rev_addrs:
                    first = rev_addrs[0]
                    street = street or first.street
                    city = city or first.city
                    state = state or first.state_province
                    postal = postal or first.postal_code
                    country = country or first.country
                    addresses_list = [a.model_dump() for a in rev_addrs]

            # 2. Forward geocoding fallback if coordinates are missing (REQ-ING-004, REQ-ING-005)
            if lat is None or lon is None:
                fwd_lat, fwd_lon, fwd_addrs = await self._forward_geocode_candidate(
                    rec.poi_name, city, state, country
                )
                if fwd_lat is not None and fwd_lon is not None:
                    lat, lon = fwd_lat, fwd_lon
                    if fwd_addrs:
                        first = fwd_addrs[0]
                        street = street or first.street
                        city = city or first.city
                        state = state or first.state_province
                        postal = postal or first.postal_code
                        country = country or first.country
                        addresses_list = [a.model_dump() for a in fwd_addrs]

            # 3. Deduplication & Nesting classification (REQ-ING-006 to REQ-ING-010)
            recommended_disposition = IngestDisposition.ACCEPT
            matched_existing_poi_id: UUID | None = None
            parent_poi_id: UUID | None = None

            in_batch_match = self._check_in_batch_duplicate(
                rec.poi_name, lat, lon, candidates_to_stage
            )

            if in_batch_match is not None:
                # In-batch duplicate match
                recommended_disposition = IngestDisposition.UPDATE_EXISTING
            elif lat is None or lon is None:
                # Unmappable missing-coordinate row (REQ-ING-005)
                recommended_disposition = IngestDisposition.IGNORE
            elif self._duplicate_service is not None:
                verdict = await self._duplicate_service.evaluate_candidate(
                    user_id=user_id,
                    name=rec.poi_name,
                    latitude=lat,
                    longitude=lon,
                )
                if verdict.status == "POTENTIAL_DUPLICATE":
                    recommended_disposition = IngestDisposition.UPDATE_EXISTING
                    matched_existing_poi_id = verdict.existing_poi_id
                elif verdict.status == "NEARBY_PARENT":
                    recommended_disposition = IngestDisposition.SUBLOCATION
                    parent_poi_id = verdict.existing_poi_id
                else:
                    if rec.location_confidence_percent >= 40:
                        recommended_disposition = IngestDisposition.ACCEPT
                    else:
                        recommended_disposition = IngestDisposition.IGNORE
            else:
                if rec.location_confidence_percent < 40:
                    recommended_disposition = IngestDisposition.IGNORE

            candidate = IngestCandidate(
                id=uuid4(),
                user_id=user_id,
                job_id=job_id,
                row_index=idx,
                poi_name=rec.poi_name,
                recommended_disposition=recommended_disposition,
                user_disposition=None,
                matched_existing_poi_id=matched_existing_poi_id,
                parent_poi_id=parent_poi_id,
                latitude=Decimal(str(round(lat, 7))) if lat is not None else None,
                longitude=Decimal(str(round(lon, 7))) if lon is not None else None,
                street_address=street,
                city=city,
                state_province=state,
                postal_code=postal,
                country=country,
                addresses=addresses_list,
                dates_visited=list(rec.dates_visited),
                photo_directory=rec.photo_directory,
                confidence_score=rec.location_confidence_percent,
                tags=list(rec.tags),
                description=None,
                reason_to_visit=None,
                update_coordinates=False,
                is_skipped=False,
                phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            candidates_to_stage.append(candidate)

        return await self._candidate_repo.create_batch(candidates_to_stage)

    async def list_candidates(
        self,
        user_id: UUID,
        job_id: UUID,
        phase_state: IngestCandidatePhaseState | None = None,
    ) -> Sequence[IngestCandidate]:
        """Lists staged candidates for an ingest job scoped to user."""
        return await self._candidate_repo.list_by_job(user_id, job_id, phase_state)

    async def get_candidate(
        self,
        user_id: UUID,
        candidate_id: UUID,
    ) -> IngestCandidate:
        """Retrieves an individual candidate, raising IngestCandidateNotFoundError if missing."""
        cand = await self._candidate_repo.get_candidate(candidate_id, user_id)
        if cand is None:
            raise IngestCandidateNotFoundError(str(candidate_id))
        return cand

    async def update_candidate(
        self,
        user_id: UUID,
        candidate_id: UUID,
        update_req: CandidateUpdateRequest,
    ) -> IngestCandidate:
        """Updates candidate attributes and user disposition overrides."""
        candidate = await self.get_candidate(user_id, candidate_id)

        if update_req.poi_name is not None:
            candidate.poi_name = update_req.poi_name
        if update_req.user_disposition is not None:
            candidate.user_disposition = update_req.user_disposition
        if update_req.matched_existing_poi_id is not None:
            candidate.matched_existing_poi_id = update_req.matched_existing_poi_id
        if update_req.parent_poi_id is not None:
            candidate.parent_poi_id = update_req.parent_poi_id
        if update_req.latitude is not None:
            candidate.latitude = Decimal(str(update_req.latitude))
        if update_req.longitude is not None:
            candidate.longitude = Decimal(str(update_req.longitude))
        if update_req.street_address is not None:
            candidate.street_address = update_req.street_address
        if update_req.city is not None:
            candidate.city = update_req.city
        if update_req.state_province is not None:
            candidate.state_province = update_req.state_province
        if update_req.postal_code is not None:
            candidate.postal_code = update_req.postal_code
        if update_req.country is not None:
            candidate.country = update_req.country
        if update_req.dates_visited is not None:
            candidate.dates_visited = list(update_req.dates_visited)
        if update_req.photo_directory is not None:
            candidate.photo_directory = update_req.photo_directory
        if update_req.tags is not None:
            candidate.tags = list(update_req.tags)
        if update_req.description is not None:
            candidate.description = update_req.description
        if update_req.reason_to_visit is not None:
            candidate.reason_to_visit = update_req.reason_to_visit
        if update_req.update_coordinates is not None:
            candidate.update_coordinates = update_req.update_coordinates
        if update_req.is_skipped is not None:
            candidate.is_skipped = update_req.is_skipped

        candidate.updated_at = datetime.now(UTC)
        return await self._candidate_repo.update_candidate(user_id, candidate)

    async def advance_to_phase2(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> tuple[int, int]:
        """Advances non-ignored candidates to Phase 2 (REQ-ING-016)."""
        candidates = await self._candidate_repo.list_by_job(
            user_id, job_id, IngestCandidatePhaseState.PHASE_1_TRIAGE
        )
        advanced_count = 0
        ignored_count = 0

        for cand in candidates:
            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp == IngestDisposition.IGNORE:
                ignored_count += 1
            else:
                advanced_count += 1

        await self._candidate_repo.advance_to_phase2(user_id, job_id)
        return advanced_count, ignored_count

    async def cancel_staging(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> int:
        """Aborts triage/review and purges staged candidate records (REQ-ING-015, REQ-ING-024)."""
        return await self._candidate_repo.purge_by_job(user_id, job_id)

    async def commit_job(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> tuple[int, list[UUID], list[UUID]]:
        """Executes final database transaction committing or merging candidates into pois table (REQ-ING-023)."""
        if self._poi_repo is None:
            raise RuntimeError("POIRepository is required to commit staged jobs")

        candidates = await self._candidate_repo.list_by_job(user_id, job_id)
        created_ids: list[UUID] = []
        merged_ids: list[UUID] = []

        # Process candidates in order
        for cand in candidates:
            if cand.is_skipped:
                continue

            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp == IngestDisposition.IGNORE:
                continue

            lat = float(cand.latitude) if cand.latitude is not None else 0.0
            lon = float(cand.longitude) if cand.longitude is not None else 0.0
            point = WGS84Point(lon=lon, lat=lat)

            if effective_disp == IngestDisposition.UPDATE_EXISTING and cand.matched_existing_poi_id:
                # Merge into existing POI
                existing = await self._poi_repo.get_by_id(cand.matched_existing_poi_id, user_id)
                if existing:
                    existing.visited_dates = sorted(
                        list(set(existing.visited_dates + cand.dates_visited))
                    )
                    existing.directory_paths = sorted(
                        list(set(existing.directory_paths + [cand.photo_directory]))
                    )
                    if hasattr(existing, "tags"):
                        existing.tags = sorted(list(set(getattr(existing, "tags", []) + cand.tags)))

                    if cand.update_coordinates:
                        existing.geom = point
                        existing.address = cand.street_address or existing.address
                        existing.city = cand.city or existing.city
                    elif cand.street_address:
                        # Append address if not already present
                        new_rec = AddressRecord(
                            street=cand.street_address,
                            city=cand.city,
                            state_province=cand.state_province,
                            country=cand.country or "Unknown",
                            postal_code=cand.postal_code,
                        )
                        existing.addresses = list(existing.addresses) + [new_rec]

                    await self._poi_repo.update(existing)
                    merged_ids.append(existing.id)
                    continue

            # ACCEPT or SUBLOCATION (or unmatched UPDATE_EXISTING fallback)
            poi = POI(
                id=uuid4(),
                user_id=user_id,
                name=cand.poi_name,
                geom=point,
                parent_poi_id=cand.parent_poi_id
                if effective_disp == IngestDisposition.SUBLOCATION
                else None,
                description=cand.description,
                reason_to_visit=cand.reason_to_visit,
                address=cand.street_address,
                city=cand.city,
                states=[cand.state_province] if cand.state_province else [],
                countries=[cand.country] if cand.country else [],
                addresses=[
                    AddressRecord(
                        street=cand.street_address,
                        city=cand.city,
                        state_province=cand.state_province,
                        country=cand.country or "Unknown",
                        postal_code=cand.postal_code,
                    )
                ]
                if cand.country
                else [],
                directory_paths=[cand.photo_directory],
                visited_dates=list(cand.dates_visited),
                visit_state=VisitState.VISITED_RETURN if cand.dates_visited else VisitState.NOT_VISITED,
                already_visited=bool(cand.dates_visited),
                source_type=SourceType.MANUAL,
                enrichment_status=EnrichmentStatus.SUCCESS,
            )
            saved = await self._poi_repo.create(poi)
            created_ids.append(saved.id)

        # Purge staging table upon successful commit
        await self._candidate_repo.purge_by_job(user_id, job_id)
        committed_count = len(created_ids) + len(merged_ids)
        return committed_count, created_ids, merged_ids

    async def enrich_candidates_phase2(
        self,
        user_id: UUID,
        job_id: UUID,
        prompt_directives: dict[PromptType, str] | None = None,
    ) -> Sequence[IngestCandidate]:
        """Enriches non-ignored candidates using ScrapingOrchestrator and traveler directives (T-034)."""
        candidates = await self._candidate_repo.list_by_job(
            user_id, job_id, IngestCandidatePhaseState.PHASE_2_ENRICHED
        )
        if not candidates:
            candidates = await self._candidate_repo.list_by_job(user_id, job_id)

        from vistarae_core.services.prompt_cache import default_prompt_cache

        directives = prompt_directives or default_prompt_cache.get(user_id) or {}
        desc_directive = directives.get(PromptType.DESCRIPTION)
        reason_directive = directives.get(PromptType.REASON_TO_VISIT)

        enriched_list: list[IngestCandidate] = []

        for cand in candidates:
            if cand.is_skipped:
                continue
            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp == IngestDisposition.IGNORE:
                continue

            addr_ctx = ", ".join(
                filter(None, [cand.street_address, cand.city, cand.state_province, cand.country])
            )
            combined_context = f"{cand.poi_name} in {addr_ctx}." if addr_ctx else cand.poi_name

            if self._orchestrator is not None:
                if not cand.description:
                    cand.description = await self._orchestrator.synthesize_summary(
                        name=cand.poi_name,
                        primary_snippet=combined_context,
                        secondary_extracts=[],
                        directive=desc_directive,
                    )
                if not cand.reason_to_visit:
                    cand.reason_to_visit = await self._orchestrator.synthesize_reason_to_visit(
                        name=cand.poi_name,
                        primary_snippet=cand.description or combined_context,
                        directive=reason_directive,
                    )
            else:
                if not cand.description:
                    cand.description = f"Historic destination and scenic attraction in {addr_ctx or 'the region'}."
                if not cand.reason_to_visit:
                    cand.reason_to_visit = f"Visitors explore {cand.poi_name} to appreciate its cultural character and memorable sights."

            if not cand.tags:
                cand.tags = ["Sightseeing", "Landmark"]

            cand.updated_at = datetime.now(UTC)
            updated = await self._candidate_repo.update_candidate(user_id, cand)
            enriched_list.append(updated)

        return enriched_list
