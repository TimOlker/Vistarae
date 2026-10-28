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
from typing import Any, Final
from urllib.parse import urlparse
from uuid import UUID

from vistarae_core.domain.value_objects import AddressRecord, PromptType
from vistarae_core.schemas.scraping import POICandidateSchema
from vistarae_core.services.address_normalizer import AddressNormalizer
from vistarae_core.services.prompt_cache import default_prompt_cache

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

# Scale and category duration heuristics table: (hours, days) (REQ: FR-017)
CATEGORY_DURATION_HEURISTICS: Final[dict[str, tuple[float, int | None]]] = {
    "national park": (12.0, 1),
    "national monument": (4.0, 0),
    "state park": (6.0, 0),
    "theme park": (6.0, 0),
    "amusement park": (6.0, 0),
    "water park": (5.0, 0),
    "castle": (2.5, 0),
    "palace": (2.5, 0),
    "château": (2.5, 0),
    "chateau": (2.5, 0),
    "fortress": (2.5, 0),
    "museum": (2.5, 0),
    "art gallery": (2.0, 0),
    "gallery": (2.0, 0),
    "viewpoint": (1.0, 0),
    "lookout": (0.5, 0),
    "overlook": (0.5, 0),
    "scenic overlook": (0.5, 0),
    "waterfall": (1.5, 0),
    "hiking trail": (3.0, 0),
    "trail": (2.5, 0),
    "beach": (4.0, 0),
    "zoo": (4.0, 0),
    "aquarium": (3.0, 0),
    "botanical garden": (2.5, 0),
    "garden": (2.0, 0),
    "cathedral": (1.5, 0),
    "basilica": (1.5, 0),
    "church": (1.0, 0),
    "temple": (1.5, 0),
    "monument": (1.0, 0),
    "memorial": (1.0, 0),
    "historic site": (2.0, 0),
    "brewery": (2.0, 0),
    "winery": (2.5, 0),
    "distillery": (2.0, 0),
    "restaurant": (1.5, 0),
    "cafe": (1.0, 0),
}


_UNSET = object()


class ScrapingOrchestrator:
    """Coordinates primary web extraction, secondary source augmentation, and Gemini synthesis."""

    def __init__(
        self,
        gemini_api_key: Any = _UNSET,
        secondary_adapters: list[SecondarySourceAdapter] | None = None,
        timeout_seconds: float = 3.0,
        valid_domains: list[str] | None = None,
        geocoding_service: Any = None,
    ) -> None:
        """Initializes the scraping orchestrator.

        Args:
            gemini_api_key: Google AI Studio API key (pass None to disable Gemini in tests).
            secondary_adapters: Optional custom adapter list (defaults to Wikipedia + TripAdvisor).
            timeout_seconds: Strict timeout ceiling for secondary requests (defaults to 3.0s).
            valid_domains: Optional default list of permitted secondary scraping domains.
            geocoding_service: Optional geocoding service for coordinate fallback.
        """
        if gemini_api_key is _UNSET:
            self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        else:
            self._gemini_api_key = gemini_api_key or ""
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
        # Remove suffixes like " - Wikipedia", " | TripAdvisor", " - Google Maps", etc.
        patterns = [
            r"\s*[-–—·|•]\s*Wikipedia.*$",
            r"\s*[-–—·|•]\s*Tripadvisor.*$",
            r"\s*[-–—·|•]\s*Google Maps.*$",
            r"\s*[-–—·|•]\s*Atlas Obscura.*$",
            r"\s*[-–—·|•]\s*Roadtrippers.*$",
            r"\s*[-–—·|•]\s*Yelp.*$",
            r"\s*[-–—·|•]\s*Official (Site|Website|Guide).*$",
        ]
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip() or title.strip()

    @classmethod
    def infer_duration(
        cls,
        category: str | None = None,
        name: str = "",
        description: str | None = None,
    ) -> tuple[float | None, int | None]:
        """Infers estimated visit duration in hours and days using category/scale heuristics (REQ: FR-017)."""
        # 1. Check explicit category match
        if category:
            cat_clean = category.strip().lower()
            for key, (h, d) in CATEGORY_DURATION_HEURISTICS.items():
                if key in cat_clean or cat_clean in key:
                    return h, d

        # 2. Check destination name keywords
        name_clean = name.strip().lower()
        for key, (h, d) in CATEGORY_DURATION_HEURISTICS.items():
            if re.search(rf"\b{re.escape(key)}\b", name_clean):
                return h, d

        # 3. Check description text keywords
        if description:
            desc_clean = description.strip().lower()
            for key, (h, d) in CATEGORY_DURATION_HEURISTICS.items():
                if re.search(rf"\b{re.escape(key)}\b", desc_clean):
                    return h, d

        return None, None

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
                temperature=0.0,
            )
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
            resp = client.models.generate_content(
                model=model_name,
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
        directive: str | None = None,
    ) -> str:
        """Internal helper for summary synthesis."""
        return await self.synthesize_summary(
            name, primary_snippet, secondary_extracts, directive=directive
        )

    @classmethod
    def _clean_source_attribution(cls, text: str, name: str | None = None) -> str:
        """Strips capture source prefixes (e.g. 'Captured from Google Maps: ...')."""
        if not text:
            return ""
        cleaned = re.sub(
            r"^\s*Captured\s+from\s+[^:\n]+:\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if name:
            double_prefix = f"{name} {name}"
            if cleaned.lower().startswith(double_prefix.lower()):
                cleaned = f"{name}{cleaned[len(double_prefix):]}"
        return cleaned.strip()

    async def synthesize_summary(
        self,
        name: str,
        primary_snippet: str | None,
        secondary_extracts: list[str],
        directive: str | None = None,
    ) -> str:
        """Synthesizes a tight 2-3 sentence travel description with optional personalized directive."""
        clean_primary = self._clean_source_attribution(primary_snippet or "", name=name)
        clean_secondary = [
            self._clean_source_attribution(s, name=name) for s in secondary_extracts if s
        ]
        combined_text = " ".join([s for s in [clean_primary, *clean_secondary] if s]).strip()
        if not combined_text:
            return f"Point of interest: {name}."

        if not self._gemini_api_key:
            # Deterministic fallback: extract first 2 sentences
            sentences = re.split(r"(?<=[.!?]) +", combined_text)
            fallback = " ".join(sentences[:2]) if sentences else combined_text[:200]
            return self._clean_source_attribution(fallback, name=name)

        def _call_gemini() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_api_key)
            prompt_parts = [
                f"Synthesize a tight, informative, elegant 2-3 sentence travel description for '{name}' ",
                f"using these source details: '{combined_text[:1500]}'. ",
                "Highlight historical significance, scenic beauty, or traveler activity. ",
                "\nCRITICAL REQUIREMENT: Do NOT include or mention the capture source (such as 'Captured from Google Maps', 'Captured from TripAdvisor', or any source/scraping attribution prefix) in the description. Start directly with the factual description of the destination itself.",
            ]
            if directive:
                prompt_parts.append(
                    f"\nTraveler preference directive: {directive}\n"
                    "Apply this preference IF AND ONLY IF the source details support it. "
                    "Do NOT invent, hallucinate, or force irrelevant themes if the destination does not feature them."
                )
            prompt_parts.append("\nReturn only the 2-3 sentence description without preamble.")
            prompt = "".join(prompt_parts)

            config = types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            res = (resp.text or "").strip() or combined_text[:200]
            return self._clean_source_attribution(res, name=name)

        try:
            logger.info("MSG   |-> Gemini summary synthesis for: %s", name)
            summary = await asyncio.to_thread(_call_gemini)
            logger.info("MSG   |<- Gemini summary synthesized: %d chars", len(summary))
            return summary
        except Exception as exc:
            logger.warning("MSG   |<- Gemini summary synthesis fallback: %s", exc)
            sentences = re.split(r"(?<=[.!?]) +", combined_text)
            fallback = " ".join(sentences[:2]) if sentences else combined_text[:200]
            return self._clean_source_attribution(fallback, name=name)

    async def synthesize_reason_to_visit(
        self,
        name: str,
        primary_snippet: str | None = None,
        secondary_extracts: list[str] | None = None,
        directive: str | None = None,
        *,
        description: str | None = None,
        reason_directive: str | None = None,
    ) -> str:
        """Synthesizes an experiential 2-3 sentence tourist rationale explaining why to visit."""
        actual_snippet = primary_snippet if primary_snippet is not None else description
        actual_extracts = secondary_extracts if secondary_extracts is not None else []
        actual_directive = directive if directive is not None else reason_directive

        clean_primary = self._clean_source_attribution(actual_snippet or "", name=name)
        clean_secondary = [
            self._clean_source_attribution(s, name=name) for s in actual_extracts if s
        ]
        combined_text = " ".join([s for s in [clean_primary, *clean_secondary] if s]).strip()

        if not self._gemini_api_key:
            return f"Visitors are drawn to {name} for its distinctive sights, cultural atmosphere, and memorable local character."

        def _call_gemini() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_api_key)
            prompt_parts = [
                f"Synthesize an engaging, compelling 2-3 sentence travel rationale explaining WHY a tourist would be interested in visiting '{name}' ",
                f"based on these source details: '{combined_text[:1500]}'. ",
                "Focus on tourist appeal, unique atmosphere, and memorable activities.",
                "\nCRITICAL REQUIREMENT: Do NOT include or mention the capture source or scraping attribution prefix. Focus exclusively on the tourist rationale.",
            ]
            if actual_directive:
                prompt_parts.append(
                    f"\nTraveler motivation directive: {actual_directive}\n"
                    "Highlight why this traveler specifically would enjoy visiting IF the destination aligns with these interests. "
                    "Do not invent or force irrelevant themes."
                )
            prompt_parts.append("\nReturn only the 2-3 sentence rationale without preamble.")
            prompt = "".join(prompt_parts)

            config = types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            res = (
                (resp.text or "").strip()
                or f"A compelling destination for travelers looking to experience {name}'s unique character and sights."
            )
            return self._clean_source_attribution(res, name=name)

        try:
            logger.info("MSG   |-> Gemini reason-to-visit synthesis for: %s", name)
            reason = await asyncio.to_thread(_call_gemini)
            logger.info("MSG   |<- Gemini reason-to-visit synthesized: %d chars", len(reason))
            return reason
        except Exception as exc:
            logger.warning("MSG   |<- Gemini reason-to-visit synthesis fallback: %s", exc)
            return f"Visitors are drawn to {name} for its distinctive sights, cultural atmosphere, and memorable local character."

    @classmethod
    def _heuristic_duration_notes(
        cls,
        name: str,
        category: str | None,
        duration_hours: float | None,
        duration_days: int | None = None,
        time_spent_directive: str | None = None,
    ) -> str:
        """Generates deterministic visit duration reasoning and notes based on timing factors."""
        dur_h = duration_hours or 2.0
        dur_d = duration_days or 0
        dur_str = (
            f"{dur_d} day{'s' if dur_d > 1 else ''}"
            if dur_d > 0
            else f"{dur_h:g} hour{'s' if dur_h != 1 else ''}"
        )

        pacing_note = ""
        if time_spent_directive:
            td_lower = time_spent_directive.lower()
            if any(k in td_lower for k in ("leisurely", "relaxed", "slow", "linger", "generous")):
                pacing_note = " Pacing is adjusted for a leisurely travel style, allowing extra time for in-depth exploration, photo stops, and unhurried rest."
            elif any(k in td_lower for k in ("brisk", "quick", "fast", "short", "half")):
                pacing_note = " Pacing reflects a brisk travel style focused on key highlights and swift transit."

        if dur_h <= 1.0 and dur_d == 0:
            return (
                f"Estimated {dur_str} for {name} accounts for arrival and walking approach (~10-15 min), "
                f"exploring the main viewpoints or highlights (~30-40 min), and brief orientation or photo stops."
                f"{pacing_note}"
            )
        elif dur_h <= 2.5 and dur_d == 0:
            return (
                f"Estimated {dur_str} for {name} accounts for shuttle bus transit or parking approach (~15-20 min), "
                f"time to spend in ticket lines (~15 min), a 45-60 minute guided or audio tour, "
                f"and 30-45 minutes of general time to see everything and view scheduled demonstrations."
                f"{pacing_note}"
            )
        elif dur_d > 0 or dur_h >= 6.0:
            return (
                f"Estimated {dur_str} for {name} accounts for shuttle bus transit, "
                f"attending scheduled ranger talks or interpretive demonstrations, "
                f"participating in full guided tours, and comprehensive exploration of major exhibits and scenic trails."
                f"{pacing_note}"
            )
        else:
            return (
                f"Estimated {dur_str} for {name} accounts for ticket queues and entry lines (~20-30 min), "
                f"shuttle bus or walking connection (~15-20 min), a comprehensive 60-90 minute tour, "
                f"and 1-2 hours of general time to see everything, including ranger talks, demonstrations, and grounds."
                f"{pacing_note}"
            )

    async def synthesize_visit_duration_notes(
        self,
        name: str,
        category: str | None,
        duration_hours: float | None,
        duration_days: int | None = None,
        context_text: str | None = None,
        directive: str | None = None,
    ) -> str:
        """Synthesizes text explanation of the reasoning of why duration values were set."""
        dur_h = duration_hours or 2.0
        dur_d = duration_days or 0
        dur_str = (
            f"{dur_d} day{'s' if dur_d > 1 else ''}"
            if dur_d > 0
            else f"{dur_h:g} hour{'s' if dur_h != 1 else ''}"
        )

        if not self._gemini_api_key:
            return self._heuristic_duration_notes(
                name=name,
                category=category,
                duration_hours=duration_hours,
                duration_days=duration_days,
                time_spent_directive=directive,
            )

        def _call_gemini() -> str:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._gemini_api_key)
            prompt_parts = [
                f"Explain the visit duration reasoning for '{name}' with an estimated visit time of {dur_str}.\n",
                "Synthesize a clear, informative 2-3 sentence explanation detailing why this duration was set.\n",
                "CRITICAL FACTORS TO INCLUDE IN THE REASONING (cover relevant items naturally):\n",
                "- Time to spend in line / ticket queues\n",
                "- How much time to take a guided tour, audio tour, or interior walk\n",
                "- Shuttle bus, transit connection, or walking approach from parking\n",
                "- General time to see everything and explore the main highlights\n",
                "- Time for scheduled exhibits, demonstrations, or ranger talks\n",
                "\nCRITICAL REQUIREMENT: Do NOT include or mention the capture source (such as 'Captured from Google Maps').\n",
            ]
            if directive:
                prompt_parts.append(
                    f"Traveler style / pacing input: '{directive}'.\n"
                    "Incorporate this travel style into the reasoning (e.g., whether the traveler prefers an unhurried, leisurely pace with in-depth tours, or a brisk, focused highlight tour).\n"
                )
            if context_text:
                cleaned_ctx = self._clean_source_attribution(context_text, name=name)
                prompt_parts.append(f"Destination context: '{cleaned_ctx[:1000]}'.\n")
            prompt_parts.append(
                "Return only the text explanation of the duration reasoning and notes without headings, bullet points, or preamble."
            )
            prompt = "".join(prompt_parts)

            config = types.GenerateContentConfig(
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            res = (resp.text or "").strip()
            return self._clean_source_attribution(res, name=name) or self._heuristic_duration_notes(
                name=name,
                category=category,
                duration_hours=duration_hours,
                duration_days=duration_days,
                time_spent_directive=directive,
            )

        try:
            logger.info("MSG   |-> Gemini visit duration notes synthesis for: %s", name)
            notes = await asyncio.to_thread(_call_gemini)
            logger.info("MSG   |<- Gemini visit duration notes synthesized: %d chars", len(notes))
            return notes
        except Exception as exc:
            logger.warning("MSG   |<- Gemini visit duration notes synthesis fallback: %s", exc)
            return self._heuristic_duration_notes(
                name=name,
                category=category,
                duration_hours=duration_hours,
                duration_days=duration_days,
                time_spent_directive=directive,
            )

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

    @classmethod
    def _parse_client_address(cls, client_raw_address: str | None) -> list[AddressRecord]:
        """Parses client raw address into normalized AddressRecord list."""
        if not client_raw_address:
            return []
        clean_addr = AddressNormalizer.clean_address_text(client_raw_address)
        if not clean_addr:
            return []

        parts = [p.strip() for p in clean_addr.split(",") if p.strip()]
        detected_country = "Unknown"
        for part in reversed(parts):
            norm_c = AddressNormalizer.normalize_country(part)
            if norm_c:
                detected_country = norm_c
                break

        street_parts = list(parts)
        if (
            street_parts
            and detected_country != "Unknown"
            and AddressNormalizer.normalize_country(street_parts[-1]) == detected_country
        ):
            street_parts.pop()

        city = None
        postal_code = None
        street = None

        if street_parts:
            last_token = street_parts[-1]
            m_post = re.match(r"^(\d{4,5})\s+(.+)$", last_token)
            if m_post:
                postal_code = m_post.group(1)
                city = m_post.group(2)
                street_parts.pop()
            elif len(street_parts) > 1:
                city = street_parts.pop()

        if street_parts:
            street = ", ".join(street_parts)
        elif not city and not postal_code:
            street = clean_addr

        return [
            AddressNormalizer.normalize_address(
                AddressRecord(
                    street=street,
                    city=city,
                    country=detected_country,
                    postal_code=postal_code,
                )
            )
        ]

    @classmethod
    def _resolve_durations(
        cls,
        primary_dur: float | None,
        secondary_dur: float | None,
        category: str | None,
        name: str,
        desc: str | None,
        time_spent_directive: str | None = None,
    ) -> tuple[float | None, int | None]:
        """Resolves duration hours and days with heuristic inference and user pacing directives."""
        dur_h = primary_dur if primary_dur is not None else secondary_dur
        if dur_h is None:
            dur_h, dur_d = cls.infer_duration(category=category, name=name, description=desc)
        else:
            dur_d = 0 if dur_h < 24 else int(dur_h // 24)

        if dur_h is not None and time_spent_directive:
            dir_lower = time_spent_directive.lower()
            if any(
                k in dir_lower
                for k in ("generous", "leisurely", "relaxed", "slow", "linger", "unhurried")
            ):
                dur_h = dur_h * 2.0 if dur_h <= 2.0 else min(dur_h * 1.5, 24.0)
            elif any(k in dir_lower for k in ("quick", "brisk", "fast", "short", "half")):
                dur_h = max(dur_h * 0.75, 0.5)
            dur_d = 0 if dur_h < 24 else int(dur_h // 24)

        return dur_h, dur_d

    async def extract(
        self,
        source_url: str,
        page_title: str | None = None,
        selected_text: str | None = None,
        client_latitude: float | None = None,
        client_longitude: float | None = None,
        client_raw_address: str | None = None,
        client_category: str | None = None,
        prompt_directives: dict[PromptType, str] | None = None,
        user_id: UUID | None = None,
    ) -> POICandidateSchema:
        """Extracts and normalizes POI candidate attributes from web and secondary sources."""
        directives = prompt_directives
        if directives is None and user_id is not None:
            directives = default_prompt_cache.get(user_id)

        desc_directive = directives.get(PromptType.DESCRIPTION) if directives else None
        reason_directive = directives.get(PromptType.REASON_TO_VISIT) if directives else None
        time_directive = directives.get(PromptType.TIME_SPENT) if directives else None

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
        desc = await self._synthesize_summary(
            name, primary_desc, secondary_extracts, directive=desc_directive
        )
        reason_to_visit = await self.synthesize_reason_to_visit(
            name, primary_desc, secondary_extracts, directive=reason_directive
        )

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

        latitude = client_latitude if client_latitude is not None else primary_lat
        if latitude is None:
            latitude = secondary.get("latitude")

        longitude = client_longitude if client_longitude is not None else primary_lon
        if longitude is None:
            longitude = secondary.get("longitude")

        if self._geocoding_service and (latitude is None or longitude is None):
            try:
                g_lat, g_lon, _, _ = await self._geocoding_service.geocode(name)
                if g_lat is not None:
                    latitude = g_lat
                    longitude = g_lon
            except Exception as exc:
                logger.warning("Geocoding service fallback failed: %s", exc)

        addresses = self._parse_client_address(client_raw_address)
        hero_image_url = primary_hero or secondary.get("hero_image_url")
        estimated_duration_hours, estimated_duration_days = self._resolve_durations(
            primary_dur,
            secondary.get("estimated_duration_hours"),
            client_category,
            name,
            desc,
            time_spent_directive=time_directive,
        )

        estimated_visit_time_notes = await self.synthesize_visit_duration_notes(
            name=name,
            category=client_category,
            duration_hours=estimated_duration_hours,
            duration_days=estimated_duration_days,
            context_text=desc,
            directive=time_directive,
        )

        return POICandidateSchema(
            name=name,
            description=desc,
            reason_to_visit=reason_to_visit,
            addresses=addresses,
            latitude=latitude,
            longitude=longitude,
            official_website_url=official_website_url,
            wikipedia_url=wikipedia_url,
            hero_image_url=hero_image_url,
            estimated_duration_hours=estimated_duration_hours,
            estimated_duration_days=estimated_duration_days,
            estimated_visit_time_notes=estimated_visit_time_notes,
            rating=None,
            source_type="Web",
            source_value=source_url,
            extraction_sources=extraction_sources,
        )

    async def extract_from_url(
        self,
        url: str,
        user_directives: dict[str, str] | None = None,
        user_id: UUID | None = None,
    ) -> POICandidateSchema:
        """Convenience wrapper for extracting POI candidate directly from URL with directives."""
        typed_directives: dict[PromptType, str] = {}
        if user_directives:
            for k, v in user_directives.items():
                try:
                    typed_directives[PromptType(k)] = v
                except ValueError:
                    continue
        return await self.extract(
            source_url=url,
            prompt_directives=typed_directives or None,
            user_id=user_id,
        )

    async def orchestrate(
        self,
        source_url: str,
        page_title: str | None = None,
        selected_text: str | None = None,
        valid_scraping_domains: list[str] | None = None,
        vetted_tags: list[dict[str, Any]] | None = None,
        client_latitude: float | None = None,
        client_longitude: float | None = None,
        client_raw_address: str | None = None,
        client_category: str | None = None,
        prompt_directives: dict[PromptType, str] | None = None,
        user_id: UUID | None = None,
    ) -> tuple[POICandidateSchema, list[str]]:
        """Orchestrates multi-source scraping, partial fallback, and synthesis.

        Args:
            source_url: Captured webpage URL.
            page_title: Raw page title from browser.
            selected_text: User selection or highlighted excerpt.
            valid_scraping_domains: Authorized domain list from user preferences.
            vetted_tags: User's tag dictionary library for recommendation.
            client_latitude: Optional parsed latitude from client extension.
            client_longitude: Optional parsed longitude from client extension.
            client_raw_address: Optional raw scraped address text.
            client_category: Optional inferred category from client.
            prompt_directives: Optional personalized prompt directives dictionary.
            user_id: Optional owning tenant UUID for prompt cache lookup.

        Returns:
            Tuple of (POICandidateSchema, list of recommended tag slugs).
        """
        prev_domains = self._valid_domains
        if valid_scraping_domains is not None:
            self._valid_domains = valid_scraping_domains
        try:
            candidate = await self.extract(
                source_url=source_url,
                page_title=page_title,
                selected_text=selected_text,
                client_latitude=client_latitude,
                client_longitude=client_longitude,
                client_raw_address=client_raw_address,
                client_category=client_category,
                prompt_directives=prompt_directives,
                user_id=user_id,
            )
            tag_matcher = TagMatcher(vetted_tags or [])
            combined_text_for_tags = f"{candidate.name} {candidate.description} {page_title or ''} {selected_text or ''} {client_category or ''}"
            recommended_tags = tag_matcher.match_tags(combined_text_for_tags)
            return candidate, recommended_tags
        finally:
            self._valid_domains = prev_domains
