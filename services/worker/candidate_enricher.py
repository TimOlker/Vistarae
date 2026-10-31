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

"""Candidate enrichment worker and queue orchestrator.

Modular worker logic for enriching staged POI candidates during CSV import Phase 2:
- Parity with browser extension extraction logic (REQ-EXT-017 through REQ-EXT-029).
- Queries user's configured datasources (UserPreferencesTable.valid_scraping_domains).
- Augments with authorized secondary sources (Wikipedia with OpenSearch and official website detection, TripAdvisor).
- Resolves traveler prompt customization data (UserPromptTable / default_prompt_cache).
- Synthesizes 2-3 sentence travel description, reason to visit, duration hours/days, and visit duration notes via Gemini.
- Matches approved taxonomy tags via TagMatcher.
- Horizontally scalable via SQS / AWS Lambda event source mappings.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.adapters.db.session import get_session_factory
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.adapters.repositories.ingest_candidate_repo import (
    SqlAlchemyIngestCandidateRepository,
)
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.adapters.repositories.user_prompt_repo import (
    SqlAlchemyUserPromptRepository,
)
from vistarae_core.domain.entities import IngestCandidate, IngestDisposition
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.schemas.ingest_staging import Phase2ProgressResponse
from vistarae_core.services.prompt_cache import default_prompt_cache

from services.poi.routes.preferences import DEFAULT_DOMAINS
from services.poi.scraping.orchestrator import (
    CATEGORY_DURATION_HEURISTICS,
    ScrapingOrchestrator,
)
from services.poi.scraping.secondary_sources import WikipediaAdapter
from services.poi.scraping.tag_matcher import TagMatcher

logger = logging.getLogger("vistarae.worker.candidate_enricher")


class CandidateEnricher:
    """Enriches an individual staged POI candidate using web sources, AI, and user preferences."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        orchestrator: ScrapingOrchestrator | None = None,
    ) -> None:
        """Initializes CandidateEnricher with session factory and scraping orchestrator."""
        self._session_factory = session_factory or get_session_factory()
        self._orchestrator = orchestrator or ScrapingOrchestrator()

    async def enrich_candidate(
        self,
        user_id: UUID,
        candidate_id: UUID,
        job_id: UUID,
    ) -> IngestCandidate | None:
        """Enriches candidate fields within an isolated database transaction."""
        session = self._session_factory()
        async with session, session.begin():
            candidate_repo = SqlAlchemyIngestCandidateRepository(session)
            cand = await candidate_repo.get_candidate(candidate_id, user_id)
            if not cand:
                logger.warning("Candidate %s not found for user %s", candidate_id, user_id)
                return None

            if cand.is_skipped:
                return cand

            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE):
                return cand

            # 1. Fetch user's configured datasources
            stmt = select(UserPreferencesTable.valid_scraping_domains).where(
                UserPreferencesTable.user_id == user_id
            )
            result = await session.execute(stmt)
            domains_row = result.scalar_one_or_none()
            valid_domains = domains_row if domains_row else DEFAULT_DOMAINS

            # 2. Fetch user's prompt directives / customization data
            prompt_repo = SqlAlchemyUserPromptRepository(session)
            directives = await default_prompt_cache.get_or_load(user_id, prompt_repo)
            desc_directive = directives.get(PromptType.DESCRIPTION)
            reason_directive = directives.get(PromptType.REASON_TO_VISIT)
            time_directive = directives.get(PromptType.TIME_SPENT)

            # 3. Fetch user's approved taxonomy tags
            tag_repo = SqlAlchemyTagRepository(session)
            user_tags = []
            try:
                user_tags = await tag_repo.list_by_user(user_id)
            except Exception as exc:
                logger.debug("Failed loading user tags for %s: %s", user_id, exc)

            # Build location context
            addr_ctx = ", ".join(
                filter(None, [cand.street_address, cand.city, cand.state_province, cand.country])
            )
            combined_context = f"{cand.poi_name} in {addr_ctx}." if addr_ctx else cand.poi_name

            # 4. Web scraping via authorized secondary sources
            wiki_data: dict[str, Any] = {}
            if any("wikipedia" in d.lower() for d in valid_domains):
                try:
                    wiki_adapter = WikipediaAdapter(valid_domains=valid_domains)
                    wiki_data = await wiki_adapter.augment(query_title=cand.poi_name)
                    # If direct title was empty, retry with city context if available
                    if not wiki_data and cand.city:
                        wiki_data = await wiki_adapter.augment(
                            query_title=f"{cand.poi_name} {cand.city}"
                        )

                    if wiki_data:
                        if not cand.wiki_url and wiki_data.get("wikipedia_url"):
                            cand.wiki_url = wiki_data.get("wikipedia_url")
                        if not cand.hero_image_url and wiki_data.get("hero_image_url"):
                            cand.hero_image_url = wiki_data.get("hero_image_url")
                        if not cand.official_url and wiki_data.get("official_website_url"):
                            cand.official_url = wiki_data.get("official_website_url")
                except Exception as exc:
                    logger.debug("Wikipedia enrichment failed for '%s': %s", cand.poi_name, exc)

            secondary_extracts = (
                [wiki_data["description"]] if (wiki_data and wiki_data.get("description")) else []
            )

            # 5. Duration hours and days inference with pacing preference
            dur_h, dur_d = ScrapingOrchestrator._resolve_durations(
                primary_dur=float(cand.recommended_duration_hours)
                if cand.recommended_duration_hours is not None
                else None,
                secondary_dur=None,
                category=None,
                name=cand.poi_name,
                desc=cand.description or (wiki_data.get("description") if wiki_data else None),
                time_spent_directive=time_directive,
            )
            dur_h = dur_h or 2.0
            dur_d = max(1, dur_d or 1)

            if cand.recommended_duration_hours is None:
                cand.recommended_duration_hours = Decimal(str(dur_h))
            if cand.recommended_visit_days is None or cand.recommended_visit_days < 1:
                cand.recommended_visit_days = dur_d

            # 6. AI Description synthesis
            if not cand.description:
                cand.description = await self._orchestrator.synthesize_summary(
                    name=cand.poi_name,
                    primary_snippet=combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=desc_directive,
                )

            # 7. AI Reason to Visit synthesis
            if not cand.reason_to_visit:
                cand.reason_to_visit = await self._orchestrator.synthesize_reason_to_visit(
                    name=cand.poi_name,
                    primary_snippet=cand.description or combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=reason_directive,
                )

            # 8. AI Visit Duration Reasoning Notes synthesis
            if not cand.estimated_visit_time_notes:
                cand.estimated_visit_time_notes = (
                    await self._orchestrator.synthesize_visit_duration_notes(
                        name=cand.poi_name,
                        category=None,
                        duration_hours=dur_h,
                        duration_days=dur_d,
                        context_text=cand.description,
                        directive=time_directive,
                    )
                )

            # 9. Approved taxonomy tag matching strictly bounded to User's Tags Library
            if user_tags:
                try:
                    tag_matcher = TagMatcher(user_tags)
                    matched_slugs = tag_matcher.match_tags(
                        f"{cand.poi_name} {cand.description or ''} {cand.reason_to_visit or ''} {addr_ctx}"
                    )
                    # Lookup maps from name, slug, and alias to canonical user tag display name
                    name_map: dict[str, str] = {}
                    for t in user_tags:
                        name_map[t.name.lower()] = t.name
                        name_map[t.slug.lower()] = t.name
                        for alias in (t.aliases or []):
                            name_map[alias.lower()] = t.name

                    canonical_tags: set[str] = set()
                    # Filter existing candidate tags (e.g. from CSV) strictly to user's Tags Library
                    for existing_t in (cand.tags or []):
                        canonical = name_map.get(existing_t.strip().lower())
                        if canonical:
                            canonical_tags.add(canonical)

                    # Map matched slugs to canonical display names in user's Tags Library
                    for slug in (matched_slugs or []):
                        canonical = name_map.get(slug.strip().lower())
                        if canonical:
                            canonical_tags.add(canonical)

                    cand.tags = sorted(list(canonical_tags))
                except Exception as exc:
                    logger.debug("Tag matching failed for '%s': %s", cand.poi_name, exc)
            else:
                cand.tags = []

            # Fallback tags if none matched, strictly restricted to user's Tags Library
            if not cand.tags and user_tags:
                available_names = {t.name for t in user_tags}
                defaults = [t for t in ("Sightseeing", "Landmark") if t in available_names]
                if defaults:
                    cand.tags = defaults
                elif user_tags:
                    cand.tags = [user_tags[0].name]

            cand.updated_at = datetime.now(UTC)
            saved = await candidate_repo.update_candidate(user_id, cand)
            logger.info("Enriched candidate '%s' (id=%s)", cand.poi_name, cand.id)
            return saved


# In-memory progress tracking singleton for polling UI
_global_enrichment_progress: dict[UUID, dict[str, Any]] = {}


class CandidateEnrichmentQueueManager:
    """Coordinates queueing and parallel worker dispatch for job candidates."""

    def __init__(
        self,
        enricher: CandidateEnricher | None = None,
        max_concurrency: int = 5,
    ) -> None:
        self._enricher = enricher or CandidateEnricher()
        self._max_concurrency = max_concurrency

    @staticmethod
    def get_progress(job_id: UUID) -> Phase2ProgressResponse:
        """Retrieves live enrichment progress metrics for the given job."""
        prog = _global_enrichment_progress.get(job_id)
        if prog:
            return Phase2ProgressResponse(
                job_id=job_id,
                total_count=prog.get("total_count", 0),
                enriched_count=prog.get("enriched_count", 0),
                is_complete=prog.get("is_complete", False),
                percent_complete=prog.get("percent_complete", 0),
                status_message=prog.get("status_message", "Enrichment in progress..."),
            )
        return Phase2ProgressResponse(
            job_id=job_id,
            total_count=0,
            enriched_count=0,
            is_complete=True,
            percent_complete=100,
            status_message="Ready",
        )

    async def enqueue_and_process_job(
        self,
        user_id: UUID,
        job_id: UUID,
        candidate_ids: list[UUID],
    ) -> None:
        """Processes candidate enrichment tasks in parallel using an internal worker pool.

        Modular design: Each task is decoupled, runs in its own transaction, and can be
        executed locally via async queue workers or distributed to AWS SQS / Lambda workers.
        """
        total = len(candidate_ids)
        _global_enrichment_progress[job_id] = {
            "total_count": total,
            "enriched_count": 0,
            "is_complete": False,
            "percent_complete": 0 if total > 0 else 100,
            "status_message": f"Queued {total} POIs for parallel AI and web enrichment...",
        }

        if total == 0:
            _global_enrichment_progress[job_id]["is_complete"] = True
            _global_enrichment_progress[job_id]["status_message"] = "No POIs to enrich."
            return

        queue: asyncio.Queue[UUID] = asyncio.Queue()
        for cid in candidate_ids:
            queue.put_nowait(cid)

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def _worker() -> None:
            while not queue.empty():
                try:
                    cid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                async with semaphore:
                    try:
                        res = await self._enricher.enrich_candidate(user_id, cid, job_id)
                        prog = _global_enrichment_progress.get(job_id)
                        if prog:
                            prog["enriched_count"] += 1
                            done = prog["enriched_count"]
                            prog["percent_complete"] = int((done / total) * 100)
                            poi_name = res.poi_name if res else f"ID {cid}"
                            prog["status_message"] = (
                                f"Enriched {done} of {total} POIs ({poi_name})..."
                            )
                    except Exception as exc:
                        logger.exception("Error enriching candidate %s: %s", cid, exc)
                        prog = _global_enrichment_progress.get(job_id)
                        if prog:
                            prog["enriched_count"] += 1
                            done = prog["enriched_count"]
                            prog["percent_complete"] = int((done / total) * 100)
                    finally:
                        queue.task_done()

        # Launch concurrent workers
        num_workers = min(self._max_concurrency, total)
        worker_tasks = [asyncio.create_task(_worker()) for _ in range(num_workers)]
        await asyncio.gather(*worker_tasks)

        prog = _global_enrichment_progress.get(job_id)
        if prog:
            prog["is_complete"] = True
            prog["percent_complete"] = 100
            prog["status_message"] = f"Finished enriching all {total} POI(s)!"

