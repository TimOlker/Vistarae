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

from fastapi import HTTPException, status
from vistarae_core.adapters.repositories.exclusion_zone_repo import haversine_distance_km
from vistarae_core.domain.entities import POI, IngestCandidate, TagEntity
from vistarae_core.domain.enums import TagResolutionAction
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
from vistarae_core.ports.repositories import (
    IIngestCandidateRepository,
    IIngestJobRepository,
    IPOIRepository,
    ITagRepository,
    IUserExclusionZoneRepository,
)
from vistarae_core.schemas.ingest_staging import (
    ActiveSessionResponse,
    CandidateUpdateRequest,
    Phase2ProgressResponse,
)
from vistarae_core.schemas.poi_exchange import POIExchangeRecord
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
        ingest_repo: IIngestJobRepository | None = None,
        exclusion_zone_repo: IUserExclusionZoneRepository | None = None,
        tag_repo: ITagRepository | None = None,
    ) -> None:
        """Initializes StagingService with repository and domain service adapters.

        Args:
            candidate_repo: Repository managing ingest_candidates table.
            poi_repo: Optional repository managing pois table.
            geocoding_service: Optional service for forward/reverse geocoding.
            duplicate_service: Optional service for scale-aware duplicate triage.
            exclusion_zone_repo: Optional repository for checking privacy exclusion zones.
            tag_repo: Optional repository for user taxonomy tags.
        """
        self._candidate_repo = candidate_repo
        self._poi_repo = poi_repo
        self._geocoding_service = geocoding_service
        self._duplicate_service = duplicate_service
        self._orchestrator = orchestrator
        self._ingest_repo = ingest_repo
        self._exclusion_zone_repo = exclusion_zone_repo
        self._tag_repo = tag_repo
        self._enrichment_progress: dict[UUID, dict[str, Any]] = {}

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

    async def _forward_geocode_candidate(  # noqa: C901
        self,
        name: str,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        street: str | None = None,
        batch_cache: dict[str, tuple[float | None, float | None, list[AddressRecord]]]
        | None = None,
    ) -> tuple[float | None, float | None, list[AddressRecord]]:
        """Resolves missing coordinates via hierarchical forward geocoding (REQ-ING-004)."""
        if not self._geocoding_service or not hasattr(self._geocoding_service, "geocode"):
            return None, None, []

        if not name or not name.strip():
            return None, None, []

        clean_name = name.strip()
        queries: list[str] = []

        if street and city and state and country:
            queries.append(f"{clean_name}, {street}, {city}, {state}, {country}")
            queries.append(f"{street}, {city}, {state}, {country}")
        elif street and city and country:
            queries.append(f"{clean_name}, {street}, {city}, {country}")
            queries.append(f"{street}, {city}, {country}")

        if city and state and country:
            queries.append(f"{clean_name}, {city}, {state}, {country}")
        elif city and country:
            queries.append(f"{clean_name}, {city}, {country}")

        if state and country:
            queries.append(f"{clean_name}, {state}, {country}")
        elif country:
            queries.append(f"{clean_name}, {country}")

        if street and country:
            queries.append(f"{street}, {country}")

        if city:
            queries.append(f"{clean_name}, {city}")

        # Always include the POI name itself as a standalone query (e.g. for world-famous landmarks/monuments/sites)
        queries.append(clean_name)

        # Unique queries capped at top 3 most specific
        unique_queries = list(dict.fromkeys([q.strip() for q in queries if q.strip()]))[:3]

        for query in unique_queries:
            if batch_cache is not None and query in batch_cache:
                c_lat, c_lon, c_addrs = batch_cache[query]
                if c_lat is not None and c_lon is not None:
                    return c_lat, c_lon, c_addrs
                continue

            try:
                lat, lon, addrs, _ = await self._geocoding_service.geocode(query)
                if batch_cache is not None:
                    batch_cache[query] = (lat, lon, addrs)
                if lat is not None and lon is not None:
                    return lat, lon, addrs
            except Exception as exc:
                if batch_cache is not None:
                    batch_cache[query] = (None, None, [])
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

    async def stage_records(  # noqa: C901
        self,
        user_id: UUID,
        job_id: UUID,
        records: Sequence[POIExportRecord],
    ) -> Sequence[IngestCandidate]:
        """Stages parsed CSV records into ingest_candidates with deduplication and geocoding."""
        candidates_to_stage: list[IngestCandidate] = []
        batch_geocache: dict[str, tuple[float | None, float | None, list[AddressRecord]]] = {}
        user_exclusion_zones: list[Any] = []
        if self._exclusion_zone_repo is not None:
            user_exclusion_zones = list(await self._exclusion_zone_repo.list_by_user(user_id))

        tag_lookup: dict[str, str] = {}
        if self._tag_repo:
            try:
                user_tags = await self._tag_repo.list_by_user(user_id)
                for t in user_tags:
                    tag_lookup[t.name.lower()] = t.name
                    tag_lookup[t.slug.lower()] = t.name
                    for alias in t.aliases or []:
                        tag_lookup[alias.lower()] = t.name
            except Exception as exc:
                logger.debug("Could not load user tags for filtering staging upload: %s", exc)

        for idx, rec in enumerate(records):
            lat = float(rec.latitude) if rec.latitude is not None else None
            lon = float(rec.longitude) if rec.longitude is not None else None
            confidence_score = rec.location_confidence_percent or 0

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
                    rec.poi_name,
                    city=city,
                    state=state,
                    country=country,
                    street=street,
                    batch_cache=batch_geocache,
                )
                if fwd_lat is not None and fwd_lon is not None:
                    lat, lon = fwd_lat, fwd_lon
                    confidence_score = max(confidence_score, 85)
                    if fwd_addrs:
                        first = fwd_addrs[0]
                        street = street or first.street
                        city = city or first.city
                        state = state or first.state_province
                        postal = postal or first.postal_code
                        country = country or first.country
                        addresses_list = [a.model_dump() for a in fwd_addrs]

            # 3. Privacy Exclusion Zones Check
            is_excluded = False
            if lat is not None and lon is not None and user_exclusion_zones:
                for ez in user_exclusion_zones:
                    if haversine_distance_km(lat, lon, ez.latitude, ez.longitude) <= ez.radius_km:
                        is_excluded = True
                        break

            # 4. Deduplication & Nesting classification (REQ-ING-006 to REQ-ING-010, FR-019, FR-020)
            recommended_disposition = IngestDisposition.ACCEPT
            matched_existing_poi_id: UUID | None = None
            parent_poi_id: UUID | None = None
            merge_target_id: UUID | None = None
            disposition_justification: str | None = None

            in_batch_match = self._check_in_batch_duplicate(
                rec.poi_name, lat, lon, candidates_to_stage
            )

            if is_excluded:
                recommended_disposition = IngestDisposition.EXCLUDE
                disposition_justification = "Point falls within user exclusion zone"
            elif in_batch_match is not None:
                # In-batch duplicate match
                recommended_disposition = IngestDisposition.IN_BATCH_MERGE
                merge_target_id = in_batch_match.id
                disposition_justification = f"Duplicate of #{in_batch_match.row_index + 1} '{in_batch_match.poi_name}' in batch"
            elif lat is None or lon is None:
                # Unmappable missing-coordinate row (REQ-ING-005)
                recommended_disposition = IngestDisposition.IGNORE
                disposition_justification = "Missing coordinates and geocoding failed"
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
                    disposition_justification = f"Matches existing POI '{verdict.existing_poi_name}' ({round(verdict.distance_meters, 1)}m away)"
                elif verdict.status == "NEARBY_PARENT":
                    recommended_disposition = IngestDisposition.SUBLOCATION
                    parent_poi_id = verdict.existing_poi_id
                    disposition_justification = f"Near macro-site '{verdict.existing_poi_name}' ({round(verdict.distance_meters, 1)}m away)"
                else:
                    if 0 < confidence_score < 40:
                        recommended_disposition = IngestDisposition.IGNORE
                        disposition_justification = "Low confidence location score"
                    else:
                        recommended_disposition = IngestDisposition.ACCEPT
                        disposition_justification = "Unique coordinate location verified"
            else:
                if 0 < confidence_score < 40:
                    recommended_disposition = IngestDisposition.IGNORE
                    disposition_justification = "Low confidence location score"
                else:
                    recommended_disposition = IngestDisposition.ACCEPT
                    disposition_justification = "Unique coordinate location verified"

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
                tags=[
                    tag_lookup[t.strip().lower()]
                    for t in (rec.tags or [])
                    if t.strip().lower() in tag_lookup
                ]
                if tag_lookup
                else list(rec.tags or []),
                description=None,
                reason_to_visit=None,
                update_coordinates=False,
                is_skipped=False,
                phase_state=IngestCandidatePhaseState.PHASE_1_TRIAGE,
                no_websites=False,
                disposition_justification=disposition_justification,
                is_user_overridden=False,
                parent_candidate_id=None,
                merge_target_id=merge_target_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            candidates_to_stage.append(candidate)

        return await self._candidate_repo.create_batch(candidates_to_stage)

    async def get_unapproved_tags(
        self,
        user_id: UUID,
        records: Sequence[POIExchangeRecord],
    ) -> dict[str, int]:
        """Compares incoming tags against user library and returns unapproved tags with occurrence counts."""
        if not self._tag_repo:
            return {}
        try:
            user_tags = await self._tag_repo.list_by_user(user_id)
            approved = {t.name.lower() for t in user_tags}
            for t in user_tags:
                approved.add(t.slug.lower())
                for alias in t.aliases or []:
                    approved.add(alias.lower())
        except Exception as exc:
            logger.warning("Could not fetch user tags: %s", exc)
            return {}

        unapproved_counts: dict[str, int] = {}
        for r in records:
            for tag in r.tags or []:
                cleaned = str(tag).strip()
                if not cleaned:
                    continue
                if cleaned.lower() not in approved:
                    unapproved_counts[cleaned] = unapproved_counts.get(cleaned, 0) + 1
        return unapproved_counts

    async def resolve_unapproved_tags(
        self,
        user_id: UUID,
        records: Sequence[POIExchangeRecord],
        action: TagResolutionAction,
        unapproved_tags: Sequence[str],
    ) -> list[POIExchangeRecord]:
        unapproved_set = {t.strip().lower() for t in unapproved_tags}
        if action == TagResolutionAction.APPROVE_AND_ADD:
            if self._tag_repo:
                for tag_name in unapproved_tags:
                    clean = tag_name.strip()
                    if clean:
                        new_tag = TagEntity(
                            id=uuid4(),
                            user_id=user_id,
                            name=clean,
                            slug=clean.lower().replace(" ", "-"),
                        )
                        try:
                            await self._tag_repo.create(new_tag)
                        except Exception as exc:
                            logger.warning("Could not persist approved tag %s: %s", clean, exc)
            return list(records)

        if action == TagResolutionAction.STRIP_UNAPPROVED:
            updated_records: list[POIExchangeRecord] = []
            for r in records:
                r_dict = r.model_dump()
                r_dict["tags"] = [
                    t for t in (r.tags or []) if str(t).strip().lower() not in unapproved_set
                ]
                updated_records.append(POIExchangeRecord(**r_dict))
            return updated_records

        return list(records)

    async def stage_exchange_records(  # noqa: C901
        self,
        user_id: UUID,
        job_id: UUID,
        records: Sequence[POIExchangeRecord],
    ) -> Sequence[IngestCandidate]:
        """Stages POIExchangeRecord items with tenant-scoped ID reconciliation (REQ-IMP-007)."""
        candidates_to_stage: list[IngestCandidate] = []
        batch_geocache: dict[str, tuple[float | None, float | None, list[AddressRecord]]] = {}
        user_exclusion_zones: list[Any] = []
        if self._exclusion_zone_repo is not None:
            user_exclusion_zones = list(await self._exclusion_zone_repo.list_by_user(user_id))

        for idx, rec in enumerate(records):
            lat = float(rec.latitude) if rec.latitude is not None else None
            lon = float(rec.longitude) if rec.longitude is not None else None

            street = rec.street_address or None
            city = rec.city or None
            state = rec.state_province or None
            postal = rec.postal_code or None
            country = rec.country or None
            addresses_list: list[dict[str, Any]] = []

            # 1. Reverse geocoding fallback
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

            # 2. Forward geocoding fallback
            if lat is None or lon is None:
                fwd_lat, fwd_lon, fwd_addrs = await self._forward_geocode_candidate(
                    rec.poi_name,
                    city=city,
                    state=state,
                    country=country,
                    street=street,
                    batch_cache=batch_geocache,
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

            # 3. Privacy Exclusion Zones Check
            is_excluded = False
            if lat is not None and lon is not None and user_exclusion_zones:
                for ez in user_exclusion_zones:
                    if haversine_distance_km(lat, lon, ez.latitude, ez.longitude) <= ez.radius_km:
                        is_excluded = True
                        break

            # 4. Tenant-Scoped ID Reconciliation (REQ-IMP-007)
            recommended_disposition = IngestDisposition.ACCEPT
            user_disposition: IngestDisposition | None = None
            matched_existing_poi_id: UUID | None = None
            parent_poi_id: UUID | None = None

            matched_tenant_poi = False
            if rec.poi_id and self._poi_repo:
                try:
                    existing_poi = await self._poi_repo.get_by_id(rec.poi_id)
                    if existing_poi and existing_poi.user_id == user_id:
                        recommended_disposition = IngestDisposition.UPDATE_EXISTING
                        user_disposition = IngestDisposition.UPDATE_EXISTING
                        matched_existing_poi_id = rec.poi_id
                        matched_tenant_poi = True
                except Exception as exc:
                    logger.debug("Failed querying existing POI %s: %s", rec.poi_id, exc)

            if not matched_tenant_poi:
                in_batch_match = self._check_in_batch_duplicate(
                    rec.poi_name, lat, lon, candidates_to_stage
                )
                if is_excluded:
                    recommended_disposition = IngestDisposition.EXCLUDE
                elif in_batch_match is not None:
                    recommended_disposition = IngestDisposition.UPDATE_EXISTING
                elif lat is None or lon is None:
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
                user_disposition=user_disposition,
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
                dates_visited=list(rec.dates_visited or []),
                photo_directory=rec.photo_directory or "",
                confidence_score=rec.location_confidence_percent or 100,
                tags=list(rec.tags or []),
                description=rec.ai_description or None,
                reason_to_visit=rec.reason_to_visit or None,
                official_url=rec.official_website or None,
                wiki_url=rec.wikipedia_url or None,
                hero_image_url=rec.hero_image_url or None,
                recommended_duration_hours=Decimal(str(rec.recommended_duration_hours))
                if rec.recommended_duration_hours
                else None,
                recommended_visit_days=rec.itinerary_days or 1,
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
        """Lists staged candidates for an ingest job scoped to user.

        In Phase 2, in-batch duplicates without an existing DB match are consolidated
        into single 'New POI' entries, and 'Update Existing' is reserved strictly for
        actual database POI matches.
        """
        candidates = list(await self._candidate_repo.list_by_job(user_id, job_id, phase_state))
        if phase_state == IngestCandidatePhaseState.PHASE_2_ENRICHED:
            primary_map: dict[str, IngestCandidate] = {}
            for cand in candidates:
                if cand.matched_existing_poi_id:
                    continue
                disp = cand.user_disposition or cand.recommended_disposition
                if disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
                    continue

                norm_key = f"{cand.poi_name.strip().lower()}|{(cand.city or '').strip().lower()}"
                if norm_key not in primary_map:
                    primary_map[norm_key] = cand
                    # If this in-batch entry was marked update_existing without a DB match,
                    # normalize it to ACCEPT (New POI) since it creates a brand new POI
                    if (
                        cand.recommended_disposition == IngestDisposition.UPDATE_EXISTING
                        and not cand.user_disposition
                    ):
                        cand.user_disposition = IngestDisposition.ACCEPT
                        await self._candidate_repo.update_candidate(user_id, cand)
                elif not cand.is_skipped:
                    # In-batch duplicate: consolidate visit dates and mark duplicate as skipped
                    prim = primary_map[norm_key]
                    merged_dates = sorted(list(set(prim.dates_visited + cand.dates_visited)))
                    if merged_dates != prim.dates_visited:
                        prim.dates_visited = merged_dates
                        await self._candidate_repo.update_candidate(user_id, prim)
                    cand.is_skipped = True
                    await self._candidate_repo.update_candidate(user_id, cand)

            return [c for c in candidates if not c.is_skipped]

        return candidates

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
        """Updates candidate attributes and user disposition overrides with validation."""
        candidate = await self.get_candidate(user_id, candidate_id)

        update_fields = update_req.model_dump(exclude_unset=True)

        # Check sublocation parent requirement (FR-022)
        target_disp = (
            update_req.user_disposition
            if update_req.user_disposition is not None
            else (candidate.user_disposition or candidate.recommended_disposition)
        )
        if target_disp == IngestDisposition.SUBLOCATION:
            p_poi = update_req.parent_poi_id if "parent_poi_id" in update_fields else candidate.parent_poi_id
            p_cand = update_req.parent_candidate_id if "parent_candidate_id" in update_fields else candidate.parent_candidate_id
            if p_poi is None and p_cand is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Sublocation requires an assigned parent POI",
                )

        # Orphan prevention guard (FR-027)
        if target_disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
            all_cands = await self._candidate_repo.list_by_job(user_id, candidate.job_id)
            for c in all_cands:
                c_disp = c.user_disposition or c.recommended_disposition
                if c.id != candidate.id and c_disp not in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
                    if c.parent_candidate_id == candidate.id or c.merge_target_id == candidate.id:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Cannot ignore or exclude candidate '{candidate.poi_name}': candidate '{c.poi_name}' depends on it as a parent or merge target.",
                        )

        # Cycle detection for candidate hierarchy (FR-023, FR-029)
        target_parent_cand = update_req.parent_candidate_id if "parent_candidate_id" in update_fields else candidate.parent_candidate_id
        if target_parent_cand is not None:
            visited = {candidate.id}
            curr = target_parent_cand
            while curr is not None:
                if curr in visited:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Circular hierarchy detected: candidate {curr} is already an ancestor.",
                    )
                visited.add(curr)
                parent_record = await self._candidate_repo.get_candidate(curr, user_id)
                if parent_record is None:
                    break
                curr = parent_record.parent_candidate_id

        # Adaptive disposition justification and override badge (FR-019, FR-020)
        if "user_disposition" in update_fields:
            if update_req.user_disposition is not None and update_req.user_disposition != candidate.recommended_disposition:
                candidate.is_user_overridden = True
                if not update_req.disposition_justification and not candidate.disposition_justification:
                    candidate.disposition_justification = f"User overridden from {candidate.recommended_disposition.value}"
            elif update_req.user_disposition is None or update_req.user_disposition == candidate.recommended_disposition:
                candidate.is_user_overridden = False

        # Reactive no_websites reset (FR-010)
        if ("official_url" in update_fields and update_fields["official_url"]) or ("wiki_url" in update_fields and update_fields["wiki_url"]):
            candidate.no_websites = False

        for field, val in update_fields.items():
            if field in ("latitude", "longitude") and val is not None:
                setattr(candidate, field, Decimal(str(val)))
            elif field == "dates_visited" and val is not None:
                setattr(candidate, field, list(val))
            elif field == "tags" and val is not None:
                if self._tag_repo:
                    try:
                        user_tags = await self._tag_repo.list_by_user(user_id)
                        tag_map: dict[str, str] = {}
                        for t in user_tags:
                            tag_map[t.name.lower()] = t.name
                            tag_map[t.slug.lower()] = t.name
                            for alias in t.aliases or []:
                                tag_map[alias.lower()] = t.name
                        valid_tags: list[str] = []
                        for t in val:
                            canonical = tag_map.get(t.strip().lower())
                            if canonical and canonical not in valid_tags:
                                valid_tags.append(canonical)
                        setattr(candidate, field, valid_tags)
                    except Exception:
                        setattr(candidate, field, list(val))
                else:
                    setattr(candidate, field, list(val))
            elif hasattr(candidate, field):
                setattr(candidate, field, val)

        candidate.updated_at = datetime.now(UTC)
        return await self._candidate_repo.update_candidate(user_id, candidate)

    async def advance_to_phase2(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> tuple[int, int]:
        """Advances non-ignored candidates to Phase 2, consolidating in-batch duplicates into New POIs."""
        candidates = await self._candidate_repo.list_by_job(
            user_id, job_id, IngestCandidatePhaseState.PHASE_1_TRIAGE
        )
        if not candidates:
            candidates = await self._candidate_repo.list_by_job(user_id, job_id)

        advanced_count = 0
        ignored_count = 0

        # Consolidate in-batch duplicates without a DB match into single New POI entries
        primary_in_batch: dict[str, IngestCandidate] = {}

        for cand in candidates:
            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
                ignored_count += 1
                continue

            # Actual database matches remain UPDATE_EXISTING
            if cand.matched_existing_poi_id:
                advanced_count += 1
                continue

            # In-batch match consolidation: group by normalized name and locality
            norm_name = cand.poi_name.strip().lower()
            norm_city = (cand.city or "").strip().lower()
            key = f"{norm_name}|{norm_city}"

            if key not in primary_in_batch:
                primary_in_batch[key] = cand
                # An in-batch entry creating a new POI is ACCEPT ("New POI")
                if effective_disp == IngestDisposition.UPDATE_EXISTING:
                    cand.user_disposition = IngestDisposition.ACCEPT
                    await self._candidate_repo.update_candidate(user_id, cand)
                advanced_count += 1
            else:
                # Merge visit dates and tags into the primary New POI
                primary = primary_in_batch[key]
                primary.dates_visited = sorted(
                    list(set(primary.dates_visited + cand.dates_visited))
                )
                if cand.tags:
                    primary.tags = sorted(list(set(primary.tags + cand.tags)))
                await self._candidate_repo.update_candidate(user_id, primary)

                # Mark secondary duplicate as skipped so it doesn't appear as a redundant entry in Phase 2
                cand.is_skipped = True
                await self._candidate_repo.update_candidate(user_id, cand)

        await self._candidate_repo.advance_to_phase2(user_id, job_id)
        return advanced_count, ignored_count

    async def cancel_staging(
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> int:
        """Aborts triage/review and purges staged candidate records (REQ-ING-015, REQ-ING-024)."""
        return await self._candidate_repo.purge_by_job(user_id, job_id)

    async def commit_job(  # noqa: C901
        self,
        user_id: UUID,
        job_id: UUID,
    ) -> tuple[int, list[UUID], list[UUID]]:
        """Executes final database transaction committing or merging candidates into pois table (REQ-ING-023)."""
        if self._poi_repo is None:
            raise RuntimeError("POIRepository is required to commit staged jobs")

        candidates = list(await self._candidate_repo.list_by_job(user_id, job_id))
        created_ids: list[UUID] = []
        merged_ids: list[UUID] = []
        created_batch_pois: dict[str, POI] = {}
        cand_to_created_poi: dict[UUID, UUID] = {}

        # 1. Attribute aggregation for IN_BATCH_MERGE candidates (FR-028)
        cand_by_id = {c.id: c for c in candidates}
        for cand in candidates:
            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp == IngestDisposition.IN_BATCH_MERGE or cand.merge_target_id:
                target_cand = cand_by_id.get(cand.merge_target_id) if cand.merge_target_id else None
                if not target_cand:
                    for other in candidates:
                        if other.id != cand.id and other.poi_name.strip().lower() == cand.poi_name.strip().lower():
                            target_cand = other
                            break
                if target_cand and target_cand.id != cand.id:
                    target_cand.dates_visited = sorted(list(set(target_cand.dates_visited + cand.dates_visited)))
                    if cand.tags:
                        target_cand.tags = sorted(list(set((target_cand.tags or []) + cand.tags)))
                    if not target_cand.official_url and cand.official_url:
                        target_cand.official_url = cand.official_url
                    if not target_cand.wiki_url and cand.wiki_url:
                        target_cand.wiki_url = cand.wiki_url
                    if not target_cand.hero_image_url and cand.hero_image_url:
                        target_cand.hero_image_url = cand.hero_image_url
                    if cand.estimated_visit_time_notes:
                        if target_cand.estimated_visit_time_notes:
                            if cand.estimated_visit_time_notes not in target_cand.estimated_visit_time_notes:
                                target_cand.estimated_visit_time_notes += f"; {cand.estimated_visit_time_notes}"
                        else:
                            target_cand.estimated_visit_time_notes = cand.estimated_visit_time_notes
                    cand.is_skipped = True

        # 2. Sort candidates so parents with no parent_candidate_id are processed before children
        def _sort_key(c: IngestCandidate) -> int:
            return 1 if c.parent_candidate_id is not None else 0

        sorted_candidates = sorted(candidates, key=_sort_key)

        # Process candidates in order
        for cand in sorted_candidates:
            if cand.is_skipped:
                continue

            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
                continue

            lat = float(cand.latitude) if cand.latitude is not None else 0.0
            lon = float(cand.longitude) if cand.longitude is not None else 0.0
            point = WGS84Point(lon=lon, lat=lat)

            if effective_disp == IngestDisposition.UPDATE_EXISTING:
                target_poi = None
                if cand.matched_existing_poi_id:
                    target_poi = await self._poi_repo.get_by_id(
                        cand.matched_existing_poi_id, user_id
                    )
                elif cand.poi_name.strip().lower() in created_batch_pois:
                    target_poi = created_batch_pois[cand.poi_name.strip().lower()]

                if target_poi:
                    target_poi.visited_dates = sorted(
                        list(set(target_poi.visited_dates + cand.dates_visited))
                    )
                    target_poi.directory_paths = sorted(
                        list(set(target_poi.directory_paths + [cand.photo_directory]))
                    )
                    if hasattr(target_poi, "tags"):
                        target_poi.tags = sorted(
                            list(set(getattr(target_poi, "tags", []) + cand.tags))
                        )

                    if cand.update_coordinates:
                        target_poi.geom = point
                        target_poi.address = cand.street_address or target_poi.address
                        target_poi.city = cand.city or target_poi.city
                    if cand.street_address:
                        new_rec = AddressRecord(
                            street=cand.street_address,
                            city=cand.city,
                            state_province=cand.state_province,
                            country=cand.country or "Unknown",
                            postal_code=cand.postal_code,
                        )
                        target_poi.addresses = list(target_poi.addresses) + [new_rec]

                    if cand.official_url and not target_poi.official_url:
                        target_poi.official_url = cand.official_url
                    if cand.wiki_url and not target_poi.wiki_url:
                        target_poi.wiki_url = cand.wiki_url
                    if cand.hero_image_url and not target_poi.image_urls:
                        target_poi.image_urls = [cand.hero_image_url]
                    if (
                        cand.recommended_duration_hours
                        and not target_poi.recommended_duration_hours
                    ):
                        target_poi.recommended_duration_hours = Decimal(
                            str(cand.recommended_duration_hours)
                        )
                    if cand.recommended_visit_days and target_poi.recommended_visit_days <= 1:
                        target_poi.recommended_visit_days = cand.recommended_visit_days
                    if (
                        cand.estimated_visit_time_notes
                        and not target_poi.estimated_visit_time_notes
                    ):
                        target_poi.estimated_visit_time_notes = cand.estimated_visit_time_notes
                    if cand.related_websites:
                        existing_urls = {
                            w["url"].rstrip("/").lower()
                            for w in (target_poi.related_websites or [])
                            if isinstance(w, dict) and "url" in w
                        }
                        for site in cand.related_websites:
                            if isinstance(site, dict) and site.get("url"):
                                k = site["url"].rstrip("/").lower()
                                if k not in existing_urls:
                                    existing_urls.add(k)
                                    target_poi.related_websites.append(site)

                    await self._poi_repo.update(target_poi)
                    if cand.tags and self._tag_repo and hasattr(self._poi_repo, "bulk_attach_tags"):
                        try:
                            user_tags = await self._tag_repo.list_by_user(user_id)
                            tag_map = {t.name.lower(): t.id for t in user_tags}
                            matched_ids = [
                                tag_map[t.strip().lower()]
                                for t in cand.tags
                                if t.strip().lower() in tag_map
                            ]
                            if matched_ids:
                                await self._poi_repo.bulk_attach_tags(
                                    user_id=user_id,
                                    poi_ids=[target_poi.id],
                                    tag_ids=matched_ids,
                                )
                        except Exception as exc:
                            logger.warning(
                                "Failed attaching tags to merged POI %s: %s", target_poi.id, exc
                            )

                    merged_ids.append(target_poi.id)
                    continue

            # Resolve parent POI ID from parent candidate or existing parent POI (FR-023, FR-028)
            resolved_parent_id = None
            if effective_disp == IngestDisposition.SUBLOCATION:
                if cand.parent_candidate_id and cand.parent_candidate_id in cand_to_created_poi:
                    resolved_parent_id = cand_to_created_poi[cand.parent_candidate_id]
                else:
                    resolved_parent_id = cand.parent_poi_id

            # ACCEPT or SUBLOCATION (or unmatched UPDATE_EXISTING fallback)
            poi = POI(
                id=uuid4(),
                user_id=user_id,
                name=cand.poi_name,
                geom=point,
                parent_poi_id=resolved_parent_id,
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
                official_url=cand.official_url,
                wiki_url=cand.wiki_url,
                image_urls=[cand.hero_image_url] if cand.hero_image_url else [],
                related_websites=cand.related_websites or [],
                recommended_duration_hours=Decimal(str(cand.recommended_duration_hours))
                if cand.recommended_duration_hours is not None
                else None,
                recommended_visit_days=cand.recommended_visit_days or 1,
                estimated_visit_time_notes=cand.estimated_visit_time_notes,
                visited_dates=list(cand.dates_visited),
                visit_state=VisitState.VISITED_RETURN
                if cand.dates_visited
                else VisitState.NOT_VISITED,
                already_visited=bool(cand.dates_visited),
                source_type=SourceType.MANUAL,
                enrichment_status=EnrichmentStatus.SUCCESS,
            )
            saved = await self._poi_repo.create(poi)
            cand_to_created_poi[cand.id] = saved.id
            if cand.tags and self._tag_repo and hasattr(self._poi_repo, "bulk_attach_tags"):
                try:
                    user_tags = await self._tag_repo.list_by_user(user_id)
                    tag_map = {t.name.lower(): t.id for t in user_tags}
                    matched_ids = [
                        tag_map[t.strip().lower()]
                        for t in cand.tags
                        if t.strip().lower() in tag_map
                    ]
                    if matched_ids:
                        await self._poi_repo.bulk_attach_tags(
                            user_id=user_id,
                            poi_ids=[saved.id],
                            tag_ids=matched_ids,
                        )
                except Exception as exc:
                    logger.warning("Failed attaching tags to created POI %s: %s", saved.id, exc)

            created_ids.append(saved.id)
            created_batch_pois[cand.poi_name.strip().lower()] = saved

        # Attach non-ignored committed POIs to target list if defined on the job
        if self._ingest_repo and self._poi_repo:
            try:
                job = await self._ingest_repo.get_job_by_id(job_id, user_id)
                if job and job.target_list_id:
                    all_committed_ids = [pid for pid in created_ids + merged_ids if pid]
                    if all_committed_ids:
                        await self._poi_repo.bulk_attach_lists(
                            user_id=user_id,
                            poi_ids=all_committed_ids,
                            list_ids=[job.target_list_id],
                        )
                        logger.info(
                            "Attached %d committed POIs to target list %s",
                            len(all_committed_ids),
                            job.target_list_id,
                        )
            except Exception as exc:
                logger.warning("Failed attaching committed POIs to target list: %s", exc)

        # Purge staging table upon successful commit
        await self._candidate_repo.purge_by_job(user_id, job_id)
        committed_count = len(created_ids) + len(merged_ids)
        return committed_count, created_ids, merged_ids

    def get_phase2_progress(self, user_id: UUID, job_id: UUID) -> Phase2ProgressResponse:
        """Returns real-time enrichment progress metrics for a job."""
        from services.worker.candidate_enricher import (
            CandidateEnrichmentQueueManager,
            _global_enrichment_progress,
        )

        # Check global queue manager progress first
        if job_id in _global_enrichment_progress:
            return CandidateEnrichmentQueueManager.get_progress(job_id)

        local_prog = self._enrichment_progress.get(job_id)
        if local_prog:
            return Phase2ProgressResponse(
                job_id=job_id,
                total_count=local_prog.get("total_count", 0),
                enriched_count=local_prog.get("enriched_count", 0),
                is_complete=local_prog.get("is_complete", False),
                percent_complete=local_prog.get("percent_complete", 0),
                status_message=local_prog.get("status_message", "Enrichment in progress..."),
            )
        return CandidateEnrichmentQueueManager.get_progress(job_id)

    async def enrich_candidates_phase2(
        self,
        user_id: UUID,
        job_id: UUID,
        prompt_directives: dict[PromptType, str] | None = None,
    ) -> Sequence[IngestCandidate]:
        """Enriches non-ignored candidates using ScrapingOrchestrator and traveler directives."""
        from vistarae_core.services.prompt_cache import default_prompt_cache

        from services.worker.candidate_enricher import _global_enrichment_progress

        directives = prompt_directives or default_prompt_cache.get(user_id) or {}
        desc_directive = directives.get(PromptType.DESCRIPTION)
        reason_directive = directives.get(PromptType.REASON_TO_VISIT)

        candidates = await self._candidate_repo.list_by_job(
            user_id, job_id, IngestCandidatePhaseState.PHASE_2_ENRICHED
        )
        if not candidates:
            candidates = await self._candidate_repo.list_by_job(user_id, job_id)

        candidates_to_enrich = [
            cand
            for cand in candidates
            if not cand.is_skipped
            and (cand.user_disposition or cand.recommended_disposition)
            not in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE)
        ]
        total = len(candidates_to_enrich)
        _global_enrichment_progress[job_id] = {
            "total_count": total,
            "enriched_count": 0,
            "is_complete": False,
            "percent_complete": 0 if total > 0 else 100,
            "status_message": f"Queued {total} POIs for enrichment...",
        }

        enriched_list: list[IngestCandidate] = []
        for done_count, cand in enumerate(candidates_to_enrich, start=1):
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
                    cand.description = (
                        f"Historic destination and scenic attraction in {addr_ctx or 'the region'}."
                    )
                if not cand.reason_to_visit:
                    cand.reason_to_visit = f"Visitors explore {cand.poi_name} to appreciate its cultural character and memorable sights."

            if not cand.tags:
                cand.tags = ["Sightseeing", "Landmark"]

            cand.updated_at = datetime.now(UTC)
            updated = await self._candidate_repo.update_candidate(user_id, cand)
            enriched_list.append(updated)

            prog = _global_enrichment_progress.get(job_id)
            if prog:
                prog["enriched_count"] = done_count
                prog["percent_complete"] = int((done_count / total) * 100)
                prog["status_message"] = (
                    f"Enriched {done_count} of {total} POIs ({cand.poi_name})..."
                )

        prog = _global_enrichment_progress.get(job_id)
        if prog:
            prog["is_complete"] = True
            prog["percent_complete"] = 100
            prog["status_message"] = f"Finished enriching all {total} POI(s)!"

        return enriched_list

    async def get_active_session(self, user_id: UUID) -> ActiveSessionResponse:
        """Checks for an active uncommitted staging session for tenant."""
        active = await self._candidate_repo.get_active_session_job(user_id)
        if not active:
            return ActiveSessionResponse(has_active_session=False)

        job_id, phase_state, total_candidates, created_at = active
        target_list_id = None
        target_list_name = None

        if self._ingest_repo:
            job = await self._ingest_repo.get_job_by_id(job_id, user_id)
            if job and job.target_list_id:
                target_list_id = job.target_list_id

        return ActiveSessionResponse(
            has_active_session=True,
            job_id=job_id,
            phase_state=phase_state,
            total_candidates=total_candidates,
            created_at=created_at,
            target_list_id=target_list_id,
            target_list_name=target_list_name,
        )

    async def wipe_active_session(self, user_id: UUID) -> int:
        """Purges all uncommitted staging candidates across all jobs for tenant."""
        return await self._candidate_repo.purge_active_sessions(user_id)

    async def revert_to_phase1(self, user_id: UUID, job_id: UUID) -> int:
        """Reverts all candidates for a job from Phase 2 back to Phase 1.

        Args:
            user_id: Tenant user UUID.
            job_id: Ingest job UUID.

        Returns:
            Count of candidates reverted.
        """
        return await self._candidate_repo.revert_to_phase1(user_id, job_id)

    async def enrich_single_candidate(
        self,
        user_id: UUID,
        job_id: UUID,
        candidate_id: UUID,
    ) -> IngestCandidate:
        """Enriches a single candidate on-demand synchronously (FR-006)."""
        from services.worker.candidate_enricher import CandidateEnricher
        from vistarae_core.adapters.db.session import get_session_factory

        session_factory = get_session_factory()
        enricher = CandidateEnricher(
            session_factory=session_factory,
            orchestrator=self._orchestrator,
        )
        cand = await enricher.enrich_candidate(
            user_id=user_id, candidate_id=candidate_id, job_id=job_id
        )
        if cand is None:
            cand = await self.get_candidate(user_id, candidate_id)
        return cand

    async def batch_edit_candidates(
        self,
        user_id: UUID,
        job_id: UUID,
        req: Any,
    ) -> int:
        """Applies batch updates to Country, State/Province, City, and Date Visited across candidates (FR-014, FR-024)."""
        update_dict: dict[str, Any] = {}
        if req.country is not None:
            update_dict["country"] = req.country
        if req.state_province is not None:
            update_dict["state_province"] = req.state_province
        if req.city is not None:
            update_dict["city"] = req.city
        if req.date_visited is not None:
            update_dict["dates_visited"] = [req.date_visited]

        if not update_dict or not req.candidate_ids:
            return 0

        return await self._candidate_repo.batch_edit(user_id, req.candidate_ids, update_dict)

