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

"""LLM Location Resolver with Google Gemini Flash-Lite and SQLite Cache (T-017, T-022).

Adheres to:
- REQ-SCR-028: Termination on missing GOOGLE_API_KEY
- REQ-SCR-029: Structured POIStandardizedLocationSchema
- REQ-SCR-030: Google Gemini Flash-Lite with thinking_budget = 0
- REQ-SCR-031: Location confidence percentage (0-100)
- REQ-SCR-032: Generic activity ambiguity penalty (<= 15) without GPS
- REQ-SCR-033: Multi-location brand ambiguity penalty (<= 30) without GPS
- REQ-SCR-034: Local SQLite cache check before external calls
- Directional dev logging: MSG |-> and MSG |<- protocol
"""

from __future__ import annotations

import json
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT / "packages" / "core") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "packages" / "core"))

from pydantic import BaseModel, ConfigDict, Field  # noqa: E402
from vistarae_core.services.address_normalizer import AddressNormalizer  # noqa: E402

from services.scraper.cache import ScraperCacheManager, compute_cache_key  # noqa: E402
from services.scraper.path_parser import ParsedPathContext  # noqa: E402

logger = logging.getLogger("vistarae.scraper.resolver")

# Generic activity labels that cannot be mapped without GPS coordinates (REQ-SCR-032)
_GENERIC_ACTIVITY_KEYWORDS: Final[set[str]] = {
    "sledding",
    "picnic",
    "beach",
    "beach day",
    "hiking",
    "swimming",
    "camping",
    "party",
    "walk",
    "biking",
    "park",
    "playground",
}

# Multi-location commercial brands requiring penalty without GPS coordinates (REQ-SCR-033)
_MULTI_LOCATION_BRANDS: Final[set[str]] = {
    "mcdonald's",
    "mcdonalds",
    "starbucks",
    "subway",
    "walmart",
    "target",
    "dunkin",
    "kfc",
    "burger king",
    "wendy's",
    "costco",
    "taco bell",
    "7-eleven",
    "seven eleven",
}


class POIStandardizedLocationSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)
    """Structured response from Gemini location resolver."""

    poi_name: str = Field(..., description="Standardized, properly capitalized POI name")
    street: str | None = Field(None, description="Street address line if determinable")
    city: str | None = Field(None, description="Town or city name")
    state_province: str | None = Field(None, description="State, province, or region")
    postal_code: str | None = Field(None, description="Postal or ZIP code if determinable")
    country: str = Field(..., description="Standard English country name")
    location_confidence_percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Location confidence percentage (0-100)",
    )


def validate_api_key_or_exit() -> str:
    """Verifies that GOOGLE_API_KEY or GEMINI_API_KEY is present in the environment or halts execution.

    Returns:
        The validated API key string.

    Raises:
        SystemExit: If the key is missing or blank (REQ-SCR-028).
    """
    key = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        logger.error(
            "FATAL: GOOGLE_API_KEY environment variable is missing. "
            "The photo scraper requires an active Google AI Studio Gemini API key to resolve locations."
        )
        sys.exit(1)
    return key


def check_ambiguity_penalty(poi_name: str, has_coords: bool) -> int | None:
    """Calculates ambiguity confidence ceiling if coordinates are absent.

    Args:
        poi_name: Candidate POI or directory name.
        has_coords: Whether valid GPS coordinates exist for this location.

    Returns:
        Maximum allowed confidence score if ambiguous, or None if no penalty.
    """
    if has_coords:
        return None

    lower_name = poi_name.strip().lower()
    words = set(lower_name.replace("-", " ").replace("_", " ").split())

    # Check generic activities (score <= 15)
    for kw in _GENERIC_ACTIVITY_KEYWORDS:
        if kw in words or lower_name.startswith(kw):
            return 10 if any(k in lower_name for k in ("sledding", "beach", "swimming")) else 15

    # Check multi-location brands (score <= 30)
    for brand in _MULTI_LOCATION_BRANDS:
        if brand in lower_name:
            return 25 if "walmart" in brand or "starbucks" in brand or "mcdonald" in brand else 30

    return None


class LocationResolver:
    """Resolves raw folder metadata into standardized geographic locations."""

    def __init__(
        self,
        cache_manager: ScraperCacheManager,
        api_key: str | None = None,
        model_name: str | None = None,
        genai_client: Any = None,
    ) -> None:
        """Initializes the resolver.

        Args:
            cache_manager: Local SQLite cache manager.
            api_key: Optional Gemini API key (defaults to env var).
            genai_client: Optional pre-configured Google GenAI client for testing.
        """
        self.cache = cache_manager
        self.api_key = (
            api_key
            or os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
        self.model_name = (
            model_name or os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"
        )
        self._client = genai_client

    def _get_genai_client(self) -> Any:
        """Lazily creates Google GenAI client."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def resolve(
        self,
        path_context: ParsedPathContext,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        tags: list[str] | None = None,
    ) -> POIStandardizedLocationSchema:
        """Resolves location metadata into a standardized POI address record.

        Args:
            path_context: Structured path hierarchy parsed from directories.
            latitude: Optional latitude.
            longitude: Optional longitude.
            tags: Optional tags/keywords extracted from media.

        Returns:
            Standardized POI location with confidence score.
        """
        tag_list = tags or []
        has_coords = latitude is not None and longitude is not None

        # 1. Check local SQLite cache first (REQ-SCR-034)
        cache_key = compute_cache_key(
            path_tokens=path_context.path_tokens,
            latitude=latitude,
            longitude=longitude,
            tags=tag_list,
        )
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Cache hit for key %s: %s", cache_key[:12], cached.get("poi_name"))
            return POIStandardizedLocationSchema(**cached)

        # 2. Check ambiguity penalty
        ambiguity_ceiling = check_ambiguity_penalty(path_context.poi_name, has_coords)

        # 3. Build prompt for Gemini Flash-Lite
        prompt = (
            f"Resolve the point-of-interest (POI) and geographic location for this photo collection:\n"
            f"Candidate POI Name: {path_context.poi_name}\n"
            f"Alternate Name: {path_context.alternate_name or 'None'}\n"
            f"Country Context: {path_context.country or 'Unknown'}\n"
            f"State/Province Context: {path_context.state_province or 'Unknown'}\n"
            f"City Context: {path_context.city or 'Unknown'}\n"
            f"GPS Latitude: {latitude if latitude is not None else 'None'}\n"
            f"GPS Longitude: {longitude if longitude is not None else 'None'}\n"
            f"Discovered Tags/Keywords: {', '.join(tag_list) if tag_list else 'None'}\n\n"
            f"Instructions:\n"
            f"- Return a structured JSON object with standardized official English names.\n"
            f"- For locations in the United Kingdom, standardize 'country' as 'United Kingdom' and 'state_province' "
            f"consistently as the constituent country ('England', 'Scotland', 'Wales', or 'Northern Ireland'). "
            f"Include regional counties (e.g. North Yorkshire, Somerset, Wiltshire, Gloucestershire) in city/locality context."
        )

        logger.info("MSG   |-> [LLM Location Resolution] query=%s", path_context.poi_name)

        client = self._get_genai_client()
        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": POIStandardizedLocationSchema,
            "temperature": 0.0,
        }
        if "thinking" in self.model_name.lower():
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

        config = types.GenerateContentConfig(**config_kwargs)

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        logger.info("MSG   |<- [LLM Location Resolution Response] result=%s", response.text)

        raw_dict = json.loads(response.text)

        # Country normalization
        country_candidate = raw_dict.get("country", "")
        norm_country = AddressNormalizer.normalize_country(country_candidate)
        if norm_country != "Unknown":
            raw_dict["country"] = norm_country
        elif path_context.country:
            raw_dict["country"] = path_context.country

        # Apply ambiguity penalties if active
        if ambiguity_ceiling is not None:
            raw_dict["location_confidence_percent"] = min(
                raw_dict.get("location_confidence_percent", 50),
                ambiguity_ceiling,
            )
            # If generic activity, clear address fields (REQ-SCR-032)
            if ambiguity_ceiling <= 15:
                raw_dict["street"] = None
                raw_dict["city"] = None
                raw_dict["state_province"] = None
                raw_dict["postal_code"] = None

        result = POIStandardizedLocationSchema(**raw_dict)

        # 4. Store in SQLite cache
        self.cache.set(cache_key, result.model_dump())

        return result
