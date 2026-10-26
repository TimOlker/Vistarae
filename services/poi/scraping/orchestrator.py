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

"""Multi-source scraping orchestrator with timeout safeguards (T-026).

Implements:
- 3.0s strict timeout ceiling with graceful partial fallback (REQ-EXT-020)
- English destination name normalization (REQ-EXT-017)
- Multi-source secondary augmentation respecting user preferences (REQ-EXT-018, REQ-EXT-019)
- Gemini Flash-Lite tight summary synthesis (thinking_budget = 0, REQ-EXT-021, REQ-EXT-028)
- Vetted tag recommendations via TagMatcher (REQ-EXT-029)
- Exclusion of photo folders and unassigned star rating (REQ-EXT-015, REQ-EXT-016)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from vistarae_core.schemas.scraping import POICandidateSchema

from services.poi.scraping.secondary_sources import (
    SecondarySourceAdapter,
    TripAdvisorAdapter,
    WikipediaAdapter,
)
from services.poi.scraping.tag_matcher import TagMatcher

logger = logging.getLogger("vistarae.scraping.orchestrator")

DEFAULT_VALID_DOMAINS = [
    "wikipedia.org",
    "tripadvisor.com",
    "atlasobscura.com",
    "google.com/maps",
    "roadtrippers.com",
]


class ScrapingOrchestrator:
    """Coordinates primary web extraction, secondary source augmentation, and Gemini synthesis."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        secondary_adapters: list[SecondarySourceAdapter] | None = None,
        timeout_seconds: float = 3.0,
        valid_domains: list[str] | None = None,
        geocoding_service: Any = None,
    ) -> None:
        """Initializes the scraping orchestrator.

        Args:
            gemini_api_key: Google AI Studio API key.
            secondary_adapters: Optional custom adapter list (defaults to Wikipedia + TripAdvisor).
            timeout_seconds: Strict timeout ceiling for secondary requests (defaults to 3.0s).
            valid_domains: Optional default list of permitted secondary scraping domains.
            geocoding_service: Optional geocoding service for coordinate fallback.
        """
        self._gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self._adapters: list[SecondarySourceAdapter] = (
            secondary_adapters
            if secondary_adapters is not None
            else [WikipediaAdapter(), TripAdvisorAdapter()]
        )
        self._timeout_seconds = timeout_seconds
        self._valid_domains = valid_domains
        self._geocoding_service = geocoding_service

    @staticmethod
    def clean_page_title(title: str | None, url: str) -> str:
        """Strips common site branding suffixes from document titles."""
        if not title:
            # Fall back to URL path segment
            parsed = urlparse(url)
            segments = [s for s in parsed.path.split("/") if s]
            return (
                segments[-1].replace("-", " ").replace("_", " ").title()
                if segments
                else "Destination"
            )

        cleaned = title
        # Remove suffixes like " - Wikipedia", " | TripAdvisor", etc.
        patterns = [
            r"\s*[-–—|]\s*Wikipedia.*$",
            r"\s*[-–—|]\s*Tripadvisor.*$",
            r"\s*[-–—|]\s*Google Maps.*$",
            r"\s*[-–—|]\s*Atlas Obscura.*$",
            r"\s*[-–—|]\s*Roadtrippers.*$",
            r"\s*[-–—|]\s*Official (Site|Website|Guide).*$",
        ]
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip() or title.strip()

    async def normalize_english_name(self, raw_name: str, source_url: str) -> str:
        """Normalizes destination name to standard English using Gemini Flash-Lite or heuristic fallback."""
        if not self._gemini_api_key:
            return raw_name

        def _call_gemini() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_api_key)
            prompt = (
                f"You are a travel database entity resolver. Given the raw page title '{raw_name}' "
                f"from URL '{source_url}', extract and return ONLY the canonical English name of the "
                "destination/attraction/point-of-interest. Do not include quotes, markdown, or commentary."
            )
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=0.0,
            )
            resp = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
                config=config,
            )
            text = (resp.text or "").strip()
            return text if text else raw_name

        try:
            logger.info("MSG   |-> Gemini English name normalization: %s", raw_name)
            normalized = await asyncio.to_thread(_call_gemini)
            logger.info("MSG   |<- Gemini normalized name: %s", normalized)
            return normalized
        except Exception as exc:
            logger.warning("MSG   |<- Gemini name normalization fallback: %s", exc)
            return raw_name

    async def _synthesize_summary(
        self,
        name: str,
        primary_snippet: str | None,
        secondary_extracts: list[str],
    ) -> str:
        """Internal helper for summary synthesis."""
        return await self.synthesize_summary(name, primary_snippet, secondary_extracts)

    async def synthesize_summary(
        self,
        name: str,
        primary_snippet: str | None,
        secondary_extracts: list[str],
    ) -> str:
        """Synthesizes a tight 2-3 sentence travel description."""
        combined_text = " ".join([s for s in [primary_snippet, *secondary_extracts] if s]).strip()
        if not combined_text:
            return f"Point of interest: {name}."

        if not self._gemini_api_key:
            # Deterministic fallback: extract first 2 sentences
            sentences = re.split(r"(?<=[.!?]) +", combined_text)
            return " ".join(sentences[:2]) if sentences else combined_text[:200]

        def _call_gemini() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_api_key)
            prompt = (
                f"Synthesize a tight, informative, elegant 2-3 sentence travel description for '{name}' "
                f"using these source details: '{combined_text[:1500]}'. "
                "Highlight historical significance, scenic beauty, or traveler activity. "
                "Return only the 2-3 sentence description without preamble."
            )
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=0.2,
            )
            resp = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
                config=config,
            )
            return (resp.text or "").strip() or combined_text[:200]

        try:
            logger.info("MSG   |-> Gemini summary synthesis for: %s", name)
            summary = await asyncio.to_thread(_call_gemini)
            logger.info("MSG   |<- Gemini summary synthesized: %d chars", len(summary))
            return summary
        except Exception as exc:
            logger.warning("MSG   |<- Gemini summary synthesis fallback: %s", exc)
            sentences = re.split(r"(?<=[.!?]) +", combined_text)
            return " ".join(sentences[:2]) if sentences else combined_text[:200]

    async def _extract_primary(
        self,
        source_url: str,
        page_title: str | None = None,
        selected_text: str | None = None,
    ) -> dict[str, Any]:
        """Extracts primary candidate data from initial webpage context."""
        initial_name = self.clean_page_title(page_title, source_url)
        name = await self.normalize_english_name(initial_name, source_url)
        return {
            "name": name,
            "description": selected_text or "",
            "source_url": source_url,
        }

    async def _augment_secondary(
        self,
        name: str,
        source_url: str,
        allowed_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Queries authorized secondary sources bounded by timeout ceiling (REQ-EXT-020)."""
        domains = allowed_domains or self._valid_domains or DEFAULT_VALID_DOMAINS
        authorized_adapters = [a for a in self._adapters if a.is_authorized(domains)]

        async def _query_with_timeout(adapter: SecondarySourceAdapter) -> dict[str, Any]:
            try:
                return await asyncio.wait_for(
                    adapter.augment(name, source_url=source_url),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError:
                logger.warning(
                    "MSG <-|  Secondary scraping source '%s' timed out after %.1fs; falling back to primary data",
                    adapter.domain,
                    self._timeout_seconds,
                )
                return {}
            except Exception as exc:
                logger.warning(
                    "MSG <-|  Secondary scraping source '%s' failed: %s; falling back to primary data",
                    adapter.domain,
                    exc,
                )
                return {}

        results = await asyncio.gather(*[_query_with_timeout(a) for a in authorized_adapters])

        merged: dict[str, Any] = {
            "extraction_sources": [],
            "latitude": None,
            "longitude": None,
            "wikipedia_url": None,
            "official_website_url": None,
            "hero_image_url": None,
            "estimated_duration_hours": None,
            "secondary_extracts": [],
        }

        for res in results:
            if not res:
                continue
            src = res.get("source_name")
            if src and src not in merged["extraction_sources"]:
                merged["extraction_sources"].append(src)

            if merged["latitude"] is None and res.get("latitude") is not None:
                merged["latitude"] = float(res["latitude"])
            if merged["longitude"] is None and res.get("longitude") is not None:
                merged["longitude"] = float(res["longitude"])
            if merged["wikipedia_url"] is None and res.get("wikipedia_url"):
                merged["wikipedia_url"] = str(res["wikipedia_url"])
            if merged["official_website_url"] is None and res.get("official_website_url"):
                merged["official_website_url"] = str(res["official_website_url"])
            if merged["hero_image_url"] is None and res.get("hero_image_url"):
                merged["hero_image_url"] = str(res["hero_image_url"])
            if (
                merged["estimated_duration_hours"] is None
                and res.get("estimated_duration_hours") is not None
            ):
                merged["estimated_duration_hours"] = float(res["estimated_duration_hours"])
            if res.get("description"):
                merged["secondary_extracts"].append(str(res["description"]))

        return merged

    async def extract(
        self,
        source_url: str,
        page_title: str | None = None,
        selected_text: str | None = None,
    ) -> POICandidateSchema:
        """Extracts and normalizes POI candidate attributes from web and secondary sources."""
        try:
            primary = await self._extract_primary(source_url, page_title, selected_text)
            name = primary.get("name") or self.clean_page_title(page_title, source_url)
            primary_desc = primary.get("description")
            primary_lat = primary.get("latitude")
            primary_lon = primary.get("longitude")
            primary_official = primary.get("official_url")
            primary_wiki = primary.get("wikipedia_url")
            primary_hero = primary.get("hero_image_url")
            primary_dur = primary.get("duration_hours")
        except Exception as exc:
            logger.warning("Primary extraction failed: %s; using page title fallback", exc)
            name = self.clean_page_title(page_title, source_url)
            primary_desc = selected_text or ""
            primary_lat = None
            primary_lon = None
            primary_official = None
            primary_wiki = None
            primary_hero = None
            primary_dur = None

        try:
            secondary = await self._augment_secondary(name, source_url)
        except Exception as exc:
            logger.warning("Secondary augmentation failed: %s; using primary only", exc)
            secondary = {}

        secondary_extracts = secondary.get("secondary_extracts", [])
        desc = await self._synthesize_summary(name, primary_desc, secondary_extracts)

        extraction_sources = list(secondary.get("extraction_sources", []))
        parsed_url = urlparse(source_url)
        if parsed_url.netloc and parsed_url.netloc not in extraction_sources:
            extraction_sources.insert(0, parsed_url.netloc)

        official_website_url = primary_official or secondary.get("official_website_url")
        wikipedia_url = primary_wiki or secondary.get("wikipedia_url")

        if "wikipedia.org/wiki/" in source_url:
            wikipedia_url = source_url
        elif not official_website_url and not any(
            d in source_url for d in ["wikipedia.org", "google.com", "tripadvisor.com"]
        ):
            official_website_url = source_url

        latitude = primary_lat if primary_lat is not None else secondary.get("latitude")
        longitude = primary_lon if primary_lon is not None else secondary.get("longitude")

        if self._geocoding_service and (latitude is None or longitude is None):
            try:
                g_lat, g_lon, _, _ = await self._geocoding_service.geocode(name)
                if g_lat is not None:
                    latitude = g_lat
                    longitude = g_lon
            except Exception as exc:
                logger.warning("Geocoding service fallback failed: %s", exc)

        hero_image_url = primary_hero or secondary.get("hero_image_url")
        estimated_duration_hours = (
            primary_dur if primary_dur is not None else secondary.get("estimated_duration_hours")
        )

        return POICandidateSchema(
            name=name,
            description=desc,
            addresses=[],
            latitude=latitude,
            longitude=longitude,
            official_website_url=official_website_url,
            wikipedia_url=wikipedia_url,
            hero_image_url=hero_image_url,
            estimated_duration_hours=estimated_duration_hours,
            estimated_duration_days=0
            if estimated_duration_hours and estimated_duration_hours < 24
            else None,
            rating=None,
            source_type="Web",
            source_value=source_url,
            extraction_sources=extraction_sources,
        )

    async def orchestrate(
        self,
        source_url: str,
        page_title: str | None = None,
        selected_text: str | None = None,
        valid_scraping_domains: list[str] | None = None,
        vetted_tags: list[dict[str, Any]] | None = None,
    ) -> tuple[POICandidateSchema, list[str]]:
        """Orchestrates multi-source scraping, partial fallback, and synthesis.

        Args:
            source_url: Captured webpage URL.
            page_title: Raw page title from browser.
            selected_text: User selection or highlighted excerpt.
            valid_scraping_domains: Authorized domain list from user preferences.
            vetted_tags: User's tag dictionary library for recommendation.

        Returns:
            Tuple of (POICandidateSchema, list of recommended tag slugs).
        """
        prev_domains = self._valid_domains
        if valid_scraping_domains is not None:
            self._valid_domains = valid_scraping_domains
        try:
            candidate = await self.extract(source_url, page_title, selected_text)
            tag_matcher = TagMatcher(vetted_tags or [])
            combined_text_for_tags = (
                f"{candidate.name} {candidate.description} {page_title or ''} {selected_text or ''}"
            )
            recommended_tags = tag_matcher.match_tags(combined_text_for_tags)
            return candidate, recommended_tags
        finally:
            self._valid_domains = prev_domains
