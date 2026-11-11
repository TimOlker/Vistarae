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
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vistarae_core.adapters.db.tables import UserPreferencesTable
from vistarae_core.adapters.repositories.enrichment_cache_repo import (
    SqlAlchemyExternalEnrichmentCacheRepository,
)
from vistarae_core.adapters.repositories.ingest_candidate_repo import (
    SqlAlchemyIngestCandidateRepository,
)
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.adapters.repositories.user_prompt_repo import (
    SqlAlchemyUserPromptRepository,
)
from vistarae_core.domain.entities import IngestCandidate, IngestDisposition
from vistarae_core.domain.enums import SelectiveEnrichmentOverrides
from vistarae_core.domain.value_objects import PromptType
from vistarae_core.ports.repositories import IExternalEnrichmentCacheRepository
from vistarae_core.schemas.ingest_staging import Phase2ProgressResponse
from vistarae_core.services.prompt_cache import default_prompt_cache

from services.poi.routes.preferences import DEFAULT_DOMAINS
from services.poi.scraping.orchestrator import (
    ScrapingOrchestrator,
)
from services.poi.scraping.secondary_sources import (
    HillmanWondersAdapter,
    TripAdvisorAdapter,
    WikipediaAdapter,
    canonicalize_url,
    is_map_service_url,
    is_unwanted_website_url,
    scrape_website_metadata,
)
from services.poi.scraping.tag_matcher import TagMatcher

logger = logging.getLogger("vistarae.worker.candidate_enricher")

LLM_SEMAPHORE = asyncio.Semaphore(5)


def build_progressive_location_queries(
    poi_name: str,
    city: str | None = None,
    state_province: str | None = None,
    country: str | None = None,
) -> list[str]:
    """Generates search queries ordered from most targeted to broadest.

    Prioritizes the primary POI name with immediate city context (e.g. 'Zwinger Dresden'),
    then city and country (e.g. 'Zwinger Dresden Germany'), then POI name alone,
    followed by broader state/country combinations. This prevents regional container tokens
    (e.g. Dresden, Saxony) from diluting the search and matching the container city over the POI.
    """
    clean_name = poi_name.strip()
    c = (city or "").strip()
    s = (state_province or "").strip()
    co = (country or "").strip()

    queries: list[str] = []

    def _add(*location_tokens: str) -> None:
        parts = [clean_name]
        name_lower = clean_name.lower()
        for tok in location_tokens:
            if tok and tok.lower() not in name_lower:
                parts.append(tok)
        combined = " ".join(parts).strip()
        if combined and combined not in queries:
            queries.append(combined)

    # 1. Primary targeted query: Name + City (highest precision for city landmarks)
    if c:
        _add(c)

    # 2. Name + City + Country
    if c and co:
        _add(c, co)

    # 3. Name alone
    _add()

    # 4. Name + City + State + Country
    if c and s and co and s.lower() != c.lower():
        _add(c, s, co)

    # 5. Name + City + State
    if c and s and s.lower() != c.lower():
        _add(c, s)

    # 6. Name + State
    if s and s.lower() != c.lower():
        _add(s)

    # 7. Name + Country
    if co:
        _add(co)

    return queries


def normalize_related_websites(
    sites: list[dict[str, Any]] | None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Normalizes related websites: decodes URL encoding, strips whitespace/trailing slashes, removes map and archive URLs, and deduplicates."""
    from urllib.parse import urlparse  # noqa: PLC0415

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in sites or []:
        if not isinstance(s, dict):
            continue
        raw_url = str(s.get("url") or "")
        url = canonicalize_url(raw_url)
        name = str(s.get("name") or "Website").strip()
        if not url:
            continue
        if is_unwanted_website_url(url, name):
            continue
        if (
            name.lower() == "hillman wonders"
            or "hillmanwonders" in url.lower()
            or "hillmanswonders" in url.lower()
        ):
            name = "Hillman Wonders"
            parsed_u = urlparse(url)
            p = parsed_u.path.lower()
            if not p or p in ("", "/", "/index.html", "/index.htm"):
                url = "https://www.hillmanswonders.com/top-1000-sites.html"
            elif not url.startswith("https://www.hillmanswonders.com/"):
                url = f"https://www.hillmanswonders.com{parsed_u.path}"
            url = canonicalize_url(url)

        k = url.lower()
        if k not in seen:
            seen.add(k)
            normalized.append({"name": name, "url": url})

    has_hillman_tag = any("hillman" in str(t).lower() for t in (tags or []))
    hillman_url = "https://www.hillmanswonders.com/top-1000-sites.html"
    if has_hillman_tag and not any("hillman" in u for u in seen):
        normalized.append({"name": "Hillman Wonders", "url": hillman_url})

    return normalized


class CandidateEnricher:
    """Enriches an individual staged POI candidate using web sources, AI, and user preferences."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        orchestrator: ScrapingOrchestrator | None = None,
        llm_semaphore: asyncio.Semaphore | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        """Initializes CandidateEnricher with session factory, orchestrator, and bounded LLM concurrency."""
        self._session_factory = session_factory
        self._orchestrator = orchestrator or ScrapingOrchestrator()
        self.llm_semaphore = (
            llm_semaphore if llm_semaphore is not None else asyncio.Semaphore(5)
        )
        self._cache_repo = cache_repo

    async def apply_enrichment_to_candidate(  # noqa: C901
        self,
        candidate: IngestCandidate,
        overrides: SelectiveEnrichmentOverrides | None = None,
        valid_domains: Sequence[str] | None = None,
        directives: dict[PromptType, str] | None = None,
        user_tags: Sequence[Any] | None = None,
        force_refresh: bool = False,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> IngestCandidate:
        """Applies dynamic per-field presence resolution and selective field re-calculation overrides (REQ-IMP-006, REQ-REC-001, REQ-REC-002)."""
        overrides = overrides or SelectiveEnrichmentOverrides()
        valid_domains = valid_domains or DEFAULT_DOMAINS
        directives = directives or {}
        user_tags = user_tags or []
        is_force = bool(getattr(overrides, "recalculate_all", False) or force_refresh)
        effective_cache_repo = cache_repo or self._cache_repo

        desc_directive = directives.get(PromptType.DESCRIPTION)
        reason_directive = directives.get(PromptType.REASON_TO_VISIT)
        time_directive = directives.get(PromptType.TIME_SPENT)

        addr_ctx = ", ".join(
            filter(
                None,
                [
                    candidate.street_address,
                    candidate.city,
                    candidate.state_province,
                    candidate.country,
                ],
            )
        )
        context_parts = []
        if addr_ctx:
            context_parts.append(f"{candidate.poi_name} in {addr_ctx}.")
        else:
            context_parts.append(candidate.poi_name)

        if candidate.description and candidate.description.strip():
            clean_init = ScrapingOrchestrator._clean_source_attribution(
                candidate.description.strip(), name=candidate.poi_name
            )
            if clean_init and clean_init.lower() != candidate.poi_name.lower():
                context_parts.append(f"Initial notes: {clean_init}")

        combined_context = " ".join(context_parts)

        wiki_data: dict[str, Any] = {}
        official_meta_desc: str | None = None
        websites_count = len(candidate.related_websites or [])
        if candidate.official_url and str(candidate.official_url).strip():
            websites_count += 1
        if candidate.wiki_url and str(candidate.wiki_url).strip():
            websites_count += 1

        should_query_links = (
            overrides.recalculate_links
            or overrides.recalculate_description
            or overrides.recalculate_reason_to_visit
            or (websites_count == 0 and not candidate.no_websites)
            or is_force
        )
        if is_force or overrides.recalculate_links:
            candidate.related_websites = []

        # Clean any preexisting map service URLs (since POIs already have coordinates)
        if candidate.official_url and is_map_service_url(candidate.official_url):
            candidate.official_url = None
        if candidate.related_websites:
            candidate.related_websites = normalize_related_websites(
                candidate.related_websites, candidate.tags
            )

        if should_query_links and any("wikipedia" in d.lower() for d in valid_domains):
            try:
                wiki_adapter = WikipediaAdapter(
                    valid_domains=valid_domains, cache_repo=effective_cache_repo
                )
                candidate_queries = build_progressive_location_queries(
                    poi_name=candidate.poi_name,
                    city=candidate.city,
                    state_province=candidate.state_province,
                    country=candidate.country,
                )

                for q in candidate_queries:
                    wiki_data = await wiki_adapter.augment(
                        query_title=q, force_refresh=is_force, poi_name=candidate.poi_name
                    )
                    if wiki_data:
                        break
                if wiki_data:
                    if (is_force or overrides.recalculate_links or not candidate.wiki_url) and wiki_data.get(
                        "wikipedia_url"
                    ):
                        candidate.wiki_url = canonicalize_url(wiki_data.get("wikipedia_url"))

                    all_cand_imgs: list[str] = []
                    if wiki_data.get("hero_image_urls"):
                        for u in wiki_data["hero_image_urls"]:
                            if u not in all_cand_imgs:
                                all_cand_imgs.append(u)
                    elif wiki_data.get("hero_image_url"):
                        all_cand_imgs.append(wiki_data["hero_image_url"])

                    if (
                        is_force or overrides.recalculate_links or not candidate.official_url
                    ) and wiki_data.get("official_website_url"):
                        candidate.official_url = canonicalize_url(wiki_data.get("official_website_url"))

                    if candidate.official_url:
                        site_meta = await scrape_website_metadata(
                            candidate.official_url,
                            cache_repo=effective_cache_repo,
                            force_refresh=is_force,
                        )
                        for u in site_meta.get("images", []):
                            if u not in all_cand_imgs:
                                all_cand_imgs.append(u)
                        official_meta_desc = site_meta.get("description")

                    if all_cand_imgs:
                        raw_geo = dict(candidate.raw_geocoding) if isinstance(candidate.raw_geocoding, dict) else {}
                        raw_geo["hero_image_urls"] = all_cand_imgs
                        candidate.raw_geocoding = raw_geo
                        if is_force or overrides.recalculate_links or not candidate.hero_image_url:
                            candidate.hero_image_url = all_cand_imgs[0]
                    if wiki_data.get("related_websites"):
                        existing_urls = {
                            canonicalize_url(w["url"]).lower()
                            for w in (candidate.related_websites or [])
                            if isinstance(w, dict) and "url" in w
                        }
                        for site in wiki_data["related_websites"]:
                            if isinstance(site, dict) and site.get("url"):
                                if is_unwanted_website_url(site.get("url"), site.get("name")):
                                    continue
                                clean_u = canonicalize_url(site["url"])
                                k = clean_u.lower()
                                if k not in existing_urls:
                                    existing_urls.add(k)
                                    candidate.related_websites.append({"name": site.get("name") or "Website", "url": clean_u})
            except Exception as exc:
                logger.debug("Wikipedia enrichment failed for '%s': %s", candidate.poi_name, exc)

        # Secondary lookup for TripAdvisor
        if should_query_links and (
            not valid_domains or any("tripadvisor" in d.lower() for d in valid_domains)
        ):
            try:
                ta_adapter = TripAdvisorAdapter(
                    valid_domains=valid_domains, cache_repo=effective_cache_repo
                )
                ta_data = await ta_adapter.augment(
                    query_title=candidate.poi_name,
                    poi_name=candidate.poi_name,
                    city=candidate.city,
                    country=candidate.country,
                    force_refresh=is_force,
                )
                if ta_data and ta_data.get("related_websites"):
                    existing_urls = {
                        canonicalize_url(w["url"]).lower()
                        for w in (candidate.related_websites or [])
                        if isinstance(w, dict) and "url" in w
                    }
                    for site in ta_data["related_websites"]:
                        if isinstance(site, dict) and site.get("url"):
                            if is_unwanted_website_url(site.get("url"), site.get("name")):
                                continue
                            clean_u = canonicalize_url(site["url"])
                            k = clean_u.lower()
                            if k not in existing_urls:
                                existing_urls.add(k)
                                candidate.related_websites.append(
                                    {"name": site.get("name") or "Tripadvisor", "url": clean_u}
                                )
            except Exception as exc:
                logger.debug("TripAdvisor enrichment failed for '%s': %s", candidate.poi_name, exc)

        # Secondary lookup for Hillman Wonders
        is_hillman_allowed = (
            not valid_domains
            or any("hillman" in d.lower() for d in valid_domains)
            or any("hillman" in str(t).lower() for t in (candidate.tags or []))
            or any(d in valid_domains for d in ["wikipedia.org", "tripadvisor.com", "atlasobscura.com"])
        )
        if should_query_links and is_hillman_allowed:
            try:
                hillman_adapter = HillmanWondersAdapter(
                    valid_domains=valid_domains, cache_repo=effective_cache_repo
                )
                hillman_data = await hillman_adapter.augment(
                    query_title=candidate.poi_name, force_refresh=is_force
                )
                if hillman_data and hillman_data.get("related_websites"):
                    existing_urls = {
                        canonicalize_url(w["url"]).lower()
                        for w in (candidate.related_websites or [])
                        if isinstance(w, dict) and "url" in w
                    }
                    for site in hillman_data["related_websites"]:
                        if isinstance(site, dict) and site.get("url"):
                            if is_unwanted_website_url(site.get("url"), site.get("name")):
                                continue
                            clean_u = canonicalize_url(site["url"])
                            k = clean_u.lower()
                            if k not in existing_urls:
                                existing_urls.add(k)
                                candidate.related_websites.append(
                                    {"name": site.get("name") or "Hillman Wonders", "url": clean_u}
                                )
                    if hillman_data.get("secondary_extracts"):
                        secondary_extracts.extend(hillman_data["secondary_extracts"])
            except Exception as exc:
                logger.debug("Hillman Wonders enrichment failed for '%s': %s", candidate.poi_name, exc)

        # Filter out map services from candidate websites and canonicalize Hillman Wonders
        if candidate.official_url and is_map_service_url(candidate.official_url):
            candidate.official_url = None
        candidate.related_websites = normalize_related_websites(
            candidate.related_websites, candidate.tags
        )

        if should_query_links:
            new_count = len(candidate.related_websites or [])
            if candidate.official_url and str(candidate.official_url).strip():
                new_count += 1
            if candidate.wiki_url and str(candidate.wiki_url).strip():
                new_count += 1
            if new_count == 0:
                candidate.no_websites = True
            else:
                candidate.no_websites = False

        secondary_extracts: list[str] = []
        if wiki_data and wiki_data.get("description"):
            secondary_extracts.append(wiki_data["description"])
        if official_meta_desc:
            secondary_extracts.append(official_meta_desc)

        dur_h, dur_d = ScrapingOrchestrator._resolve_durations(
            primary_dur=float(candidate.recommended_duration_hours)
            if candidate.recommended_duration_hours is not None
            else None,
            secondary_dur=None,
            category=None,
            name=candidate.poi_name,
            desc=candidate.description or (wiki_data.get("description") if wiki_data else None),
            time_spent_directive=time_directive,
        )
        dur_h = dur_h or 2.0
        dur_d = max(1, dur_d or 1)

        if candidate.recommended_duration_hours is None or overrides.recalculate_duration:
            candidate.recommended_duration_hours = Decimal(str(dur_h))
        if (
            candidate.recommended_visit_days is None
            or candidate.recommended_visit_days < 1
            or overrides.recalculate_duration
        ):
            candidate.recommended_visit_days = dur_d

        if not candidate.description or overrides.recalculate_description:
            async with self.llm_semaphore:
                candidate.description = await self._orchestrator.synthesize_summary(
                    name=candidate.poi_name,
                    primary_snippet=combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=desc_directive,
                )

        if not candidate.reason_to_visit or overrides.recalculate_reason_to_visit:
            async with self.llm_semaphore:
                candidate.reason_to_visit = await self._orchestrator.synthesize_reason_to_visit(
                    name=candidate.poi_name,
                    primary_snippet=combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=reason_directive,
                    existing_description=candidate.description,
                    travel_style=reason_directive,
                )
        elif candidate.reason_to_visit:
            candidate.reason_to_visit = ScrapingOrchestrator._clean_reason_to_visit_plain_text(
                candidate.reason_to_visit
            )

        if not candidate.estimated_visit_time_notes or overrides.recalculate_duration:
            async with self.llm_semaphore:
                candidate.estimated_visit_time_notes = (
                    await self._orchestrator.synthesize_visit_duration_notes(
                        name=candidate.poi_name,
                        category=None,
                        duration_hours=dur_h,
                        duration_days=dur_d,
                        context_text=candidate.description,
                        directive=time_directive,
                    )
                )

        if (not candidate.tags or overrides.recalculate_tags) and user_tags:
            try:
                tag_matcher = TagMatcher(user_tags)
                matched_slugs = tag_matcher.match_tags(
                    f"{candidate.poi_name} {candidate.description or ''} {candidate.reason_to_visit or ''} {addr_ctx}"
                )
                name_map: dict[str, str] = {}
                for t in user_tags:
                    name_map[t.name.lower()] = t.name
                    name_map[t.slug.lower()] = t.name
                    for alias in t.aliases or []:
                        name_map[alias.lower()] = t.name
                canonical_tags: set[str] = set()
                if not overrides.recalculate_tags:
                    for existing_t in candidate.tags or []:
                        canonical = name_map.get(str(existing_t).strip().lower())
                        if canonical:
                            canonical_tags.add(canonical)
                for slug in matched_slugs or []:
                    canonical = name_map.get(slug.strip().lower())
                    if canonical:
                        canonical_tags.add(canonical)
                candidate.tags = sorted(list(canonical_tags))
            except Exception as exc:
                logger.debug("Tag matching failed for '%s': %s", candidate.poi_name, exc)

        return candidate

    async def enrich_candidate(  # noqa: C901
        self,
        user_id: UUID,
        candidate_id: UUID,
        job_id: UUID,
        force_refresh: bool = False,
    ) -> IngestCandidate | None:
        """Enriches candidate fields within an isolated database transaction."""
        session = self._session_factory()
        async with session, session.begin():
            cache_repo = SqlAlchemyExternalEnrichmentCacheRepository(session)
            candidate_repo = SqlAlchemyIngestCandidateRepository(session)
            cand = await candidate_repo.get_candidate(candidate_id, user_id)
            if not cand:
                logger.warning("Candidate %s not found for user %s", candidate_id, user_id)
                return None

            if cand.is_skipped:
                return cand

            # If coordinates are missing, attempt forward geocoding resolution
            if (
                (cand.latitude is None or cand.longitude is None)
                and self._orchestrator
                and getattr(self._orchestrator, "geocoding_service", None)
            ):
                try:
                    geo = self._orchestrator.geocoding_service
                    query = (
                        f"{cand.poi_name}, {cand.city}, {cand.country}"
                        if (cand.city and cand.country)
                        else cand.poi_name
                    )
                    lat, lon, addrs, _ = await geo.geocode(query)
                    if lat is not None and lon is not None:
                        cand.latitude = Decimal(str(lat))
                        cand.longitude = Decimal(str(lon))
                        if addrs:
                            first = addrs[0]
                            cand.street_address = cand.street_address or first.street
                            cand.city = cand.city or first.city
                            cand.state_province = cand.state_province or first.state_province
                            cand.postal_code = cand.postal_code or first.postal_code
                            cand.country = cand.country or first.country
                        if cand.recommended_disposition == IngestDisposition.IGNORE:
                            cand.recommended_disposition = IngestDisposition.ACCEPT
                            cand.disposition_justification = (
                                "Coordinates resolved via enrichment geocoding"
                            )
                except Exception as exc:
                    logger.debug("Enrichment geocoding failed for '%s': %s", cand.poi_name, exc)

            effective_disp = cand.user_disposition or cand.recommended_disposition
            if effective_disp in (IngestDisposition.IGNORE, IngestDisposition.EXCLUDE, IngestDisposition.EXISTING):
                return cand

            # 1. Fetch user's configured datasources
            stmt = select(UserPreferencesTable.valid_scraping_domains).where(
                UserPreferencesTable.user_id == user_id
            )
            result = await session.execute(stmt)
            domains_row = result.scalar_one_or_none()
            valid_domains = domains_row if domains_row else DEFAULT_DOMAINS

            travel_style_desc = None
            try:
                t_stmt = select(UserPreferencesTable.travel_style_description).where(
                    UserPreferencesTable.user_id == user_id
                )
                t_res = await session.execute(t_stmt)
                t_val = t_res.scalar_one_or_none()
                if isinstance(t_val, str):
                    travel_style_desc = t_val
            except Exception:
                pass

            # 2. Fetch user's prompt directives / customization data
            prompt_repo = SqlAlchemyUserPromptRepository(session)
            directives = await default_prompt_cache.get_or_load(user_id, prompt_repo)
            desc_directive = directives.get(PromptType.DESCRIPTION)
            reason_directive = directives.get(PromptType.REASON_TO_VISIT) or travel_style_desc
            time_directive = directives.get(PromptType.TIME_SPENT)

            # 3. Fetch user's approved taxonomy tags
            tag_repo = SqlAlchemyTagRepository(session)
            user_tags = []
            try:
                user_tags = await tag_repo.list_by_user(user_id)
            except Exception as exc:
                logger.debug("Failed loading user tags for %s: %s", user_id, exc)

            # Build location and default context
            addr_ctx = ", ".join(
                filter(None, [cand.street_address, cand.city, cand.state_province, cand.country])
            )
            context_parts = []
            if addr_ctx:
                context_parts.append(f"{cand.poi_name} in {addr_ctx}.")
            else:
                context_parts.append(cand.poi_name)

            if cand.description and cand.description.strip():
                clean_init = ScrapingOrchestrator._clean_source_attribution(
                    cand.description.strip(), name=cand.poi_name
                )
                if clean_init and clean_init.lower() != cand.poi_name.lower():
                    context_parts.append(f"Initial notes: {clean_init}")

            combined_context = " ".join(context_parts)

            if force_refresh:
                cand.wiki_url = None
                cand.official_url = None
                cand.related_websites = []

            # Clean any preexisting map service URLs (since POIs already have coordinates)
            if cand.official_url and is_map_service_url(cand.official_url):
                cand.official_url = None
            if cand.related_websites:
                cand.related_websites = normalize_related_websites(
                    cand.related_websites, cand.tags
                )

            secondary_extracts: list[str] = []

            # 4. Web scraping via authorized secondary sources
            wiki_data: dict[str, Any] = {}
            official_meta_desc: str | None = None
            if not cand.no_websites and any("wikipedia" in d.lower() for d in valid_domains):
                try:
                    wiki_adapter = WikipediaAdapter(valid_domains=valid_domains, cache_repo=cache_repo)
                    candidate_queries = build_progressive_location_queries(
                        poi_name=cand.poi_name,
                        city=cand.city,
                        state_province=cand.state_province,
                        country=cand.country,
                    )

                    for q in candidate_queries:
                        wiki_data = await wiki_adapter.augment(
                            query_title=q, force_refresh=force_refresh, poi_name=cand.poi_name
                        )
                        if wiki_data:
                            break

                    if wiki_data:
                        if (force_refresh or not cand.wiki_url) and wiki_data.get("wikipedia_url"):
                            cand.wiki_url = canonicalize_url(wiki_data.get("wikipedia_url"))

                        single_cand_imgs: list[str] = []
                        if wiki_data.get("hero_image_urls"):
                            for u in wiki_data["hero_image_urls"]:
                                if u not in single_cand_imgs:
                                    single_cand_imgs.append(u)
                        elif wiki_data.get("hero_image_url"):
                            single_cand_imgs.append(wiki_data["hero_image_url"])

                        if (force_refresh or not cand.official_url) and wiki_data.get("official_website_url"):
                            cand.official_url = canonicalize_url(wiki_data.get("official_website_url"))

                        if cand.official_url:
                            site_meta = await scrape_website_metadata(
                                cand.official_url,
                                cache_repo=cache_repo,
                                force_refresh=force_refresh,
                            )
                            for u in site_meta.get("images", []):
                                if u not in single_cand_imgs:
                                    single_cand_imgs.append(u)
                            official_meta_desc = site_meta.get("description")

                        if single_cand_imgs:
                            raw_geo = dict(cand.raw_geocoding) if isinstance(cand.raw_geocoding, dict) else {}
                            raw_geo["hero_image_urls"] = single_cand_imgs
                            cand.raw_geocoding = raw_geo
                            if force_refresh or not cand.hero_image_url:
                                cand.hero_image_url = single_cand_imgs[0]
                    if wiki_data.get("related_websites"):
                        existing_urls = {
                            canonicalize_url(w["url"]).lower()
                            for w in (cand.related_websites or [])
                            if isinstance(w, dict) and "url" in w
                        }
                        for site in wiki_data["related_websites"]:
                            if isinstance(site, dict) and site.get("url"):
                                if is_unwanted_website_url(site.get("url"), site.get("name")):
                                    continue
                                clean_u = canonicalize_url(site["url"])
                                k = clean_u.lower()
                                if k not in existing_urls:
                                    existing_urls.add(k)
                                    cand.related_websites.append({"name": site.get("name") or "Website", "url": clean_u})
                except Exception as exc:
                    logger.debug("Wikipedia enrichment failed for '%s': %s", cand.poi_name, exc)

            if wiki_data and wiki_data.get("description"):
                secondary_extracts.append(wiki_data["description"])

            # Secondary lookup for TripAdvisor
            if not cand.no_websites and (
                not valid_domains or any("tripadvisor" in d.lower() for d in valid_domains)
            ):
                try:
                    ta_adapter = TripAdvisorAdapter(
                        valid_domains=valid_domains, cache_repo=cache_repo
                    )
                    ta_data = await ta_adapter.augment(
                        query_title=cand.poi_name,
                        poi_name=cand.poi_name,
                        city=cand.city,
                        country=cand.country,
                        force_refresh=force_refresh,
                    )
                    if ta_data and ta_data.get("related_websites"):
                        existing_urls = {
                            canonicalize_url(w["url"]).lower()
                            for w in (cand.related_websites or [])
                            if isinstance(w, dict) and "url" in w
                        }
                        for site in ta_data["related_websites"]:
                            if isinstance(site, dict) and site.get("url"):
                                if is_unwanted_website_url(site.get("url"), site.get("name")):
                                    continue
                                clean_u = canonicalize_url(site["url"])
                                k = clean_u.lower()
                                if k not in existing_urls:
                                    existing_urls.add(k)
                                    cand.related_websites.append(
                                        {"name": site.get("name") or "Tripadvisor", "url": clean_u}
                                    )
                except Exception as exc:
                    logger.debug("TripAdvisor enrichment failed for '%s': %s", cand.poi_name, exc)

            # Secondary lookup for Hillman Wonders
            is_hillman_allowed = (
                not valid_domains
                or any("hillman" in d.lower() for d in valid_domains)
                or any("hillman" in str(t).lower() for t in (cand.tags or []))
                or any(d in valid_domains for d in ["wikipedia.org", "tripadvisor.com", "atlasobscura.com"])
            )
            if not cand.no_websites and is_hillman_allowed:
                try:
                    hillman_adapter = HillmanWondersAdapter(
                        valid_domains=valid_domains, cache_repo=cache_repo
                    )
                    hillman_data = await hillman_adapter.augment(
                        query_title=cand.poi_name, force_refresh=force_refresh
                    )
                    if hillman_data and hillman_data.get("related_websites"):
                        existing_urls = {
                            canonicalize_url(w["url"]).lower()
                            for w in (cand.related_websites or [])
                            if isinstance(w, dict) and "url" in w
                        }
                        for site in hillman_data["related_websites"]:
                            if isinstance(site, dict) and site.get("url"):
                                if is_unwanted_website_url(site.get("url"), site.get("name")):
                                    continue
                                clean_u = canonicalize_url(site["url"])
                                k = clean_u.lower()
                                if k not in existing_urls:
                                    existing_urls.add(k)
                                    cand.related_websites.append({"name": site.get("name") or "Hillman Wonders", "url": clean_u})
                        if hillman_data.get("description"):
                            secondary_extracts.append(hillman_data["description"])
                except Exception as exc:
                    logger.debug("Hillman Wonders enrichment failed for '%s': %s", cand.poi_name, exc)

            # Filter out map services from candidate websites and canonicalize Hillman Wonders
            if cand.official_url and is_map_service_url(cand.official_url):
                cand.official_url = None
            cand.related_websites = normalize_related_websites(
                cand.related_websites, cand.tags
            )

            if not cand.official_url and not cand.wiki_url and not cand.related_websites:
                cand.no_websites = True
            if official_meta_desc:
                secondary_extracts.append(official_meta_desc)

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

            if cand.recommended_duration_hours is None or force_refresh:
                cand.recommended_duration_hours = Decimal(str(dur_h))
            if cand.recommended_visit_days is None or cand.recommended_visit_days < 1 or force_refresh:
                cand.recommended_visit_days = dur_d

            # 6. AI Description synthesis
            if not cand.description or force_refresh:
                cand.description = await self._orchestrator.synthesize_summary(
                    name=cand.poi_name,
                    primary_snippet=combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=desc_directive,
                )

            # 7. AI Reason to Visit synthesis
            if not cand.reason_to_visit or force_refresh:
                cand.reason_to_visit = await self._orchestrator.synthesize_reason_to_visit(
                    name=cand.poi_name,
                    primary_snippet=combined_context,
                    secondary_extracts=secondary_extracts,
                    directive=reason_directive,
                    existing_description=cand.description,
                    travel_style=reason_directive,
                )
            elif cand.reason_to_visit:
                cand.reason_to_visit = ScrapingOrchestrator._clean_reason_to_visit_plain_text(
                    cand.reason_to_visit
                )

            # 8. AI Visit Duration Reasoning Notes synthesis
            if not cand.estimated_visit_time_notes or force_refresh:
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
                        for alias in t.aliases or []:
                            name_map[alias.lower()] = t.name

                    canonical_tags: set[str] = set()
                    # Filter existing candidate tags (e.g. from CSV) strictly to user's Tags Library
                    for existing_t in cand.tags or []:
                        canonical = name_map.get(existing_t.strip().lower())
                        if canonical:
                            canonical_tags.add(canonical)

                    # Map matched slugs to canonical display names in user's Tags Library
                    for slug in matched_slugs or []:
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
