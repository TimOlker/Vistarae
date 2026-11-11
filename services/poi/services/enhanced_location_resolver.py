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

"""Enhanced POI Location Resolver with encyclopedic knowledge and AI canonicalization.

Provides multi-tiered fallback disambiguation when standard OpenStreetMap Nominatim
queries return 0 results (e.g. "Okapi Faunal Reserve" -> "Okapi Wildlife Reserve"):
1. Wikipedia Search & Coordinates API (resolves redirects, alternate names, and article coordinates)
2. Wikidata Entity Search (resolves multilingual aliases and P625 coordinates)
3. Gemini Flash-Lite Canonicalizer (structured JSON extraction with thinking_budget=0)
4. Heuristic Stopword & Travel Suffix Cleaning
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from vistarae_core.ports.repositories import IExternalEnrichmentCacheRepository

load_dotenv()

logger = logging.getLogger("vistarae.geocoding.enhanced_resolver")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
    "VistaraeTravelEngine/1.0 (https://vistarae.com; contact@vistarae.com)"
)

_COMMON_POI_SUFFIXES = [
    r"\s+-\s+visitor\s+center.*$",
    r"\s+visitor\s+center.*$",
    r"\s+information\s+center.*$",
    r"\s+scenic\s+overlook.*$",
    r"\s+scenic\s+viewpoint.*$",
    r"\s+scenic\s+view.*$",
    r"\s+overlook.*$",
    r"\s+viewpoint.*$",
    r"\s+gift\s+shop.*$",
    r"\s+tours?.*$",
    r"\s+trailhead.*$",
]


class EnhancedLocationCandidate(BaseModel):
    """Candidate representation for a resolved POI."""

    model_config = ConfigDict(str_strip_whitespace=True)

    canonical_name: str
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    state_province: str | None = None
    city: str | None = None
    source: str = Field(..., description="Source of resolution: wikipedia_coordinates, wikipedia_title, wikidata, gemini_flash_lite, cleaned_query")


class LLMPoiResolution(BaseModel):
    """Pydantic schema for Gemini Flash-Lite canonical POI extraction."""

    model_config = ConfigDict(str_strip_whitespace=True)

    canonical_name: str = Field(..., description="Official, standardized modern name of the travel attraction or landmark")
    country: str | None = Field(None, description="Country where the attraction is located")
    state_province: str | None = Field(None, description="State, province, or region")
    city: str | None = Field(None, description="City, municipality, or nearest town")
    alternate_names: list[str] = Field(
        default_factory=list,
        description="Alternate spellings, transliterations, historical names, and phonetic variations",
    )
    is_known_poi: bool = Field(True, description="Whether this refers to an identifiable real-world place")


class EnhancedLocationResolver:
    """Coordinates encyclopedic and AI fallbacks for unresolved POI search strings."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 4.0,
        gemini_client: Any = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        self._client = http_client
        self._timeout_seconds = timeout_seconds
        self._gemini_client = gemini_client
        self._cache_repo = cache_repo

    async def resolve_canonical_poi(  # noqa: C901
        self,
        query: str,
        country_hint: str | None = None,
        force_refresh: bool = False,
    ) -> list[EnhancedLocationCandidate]:
        """Resolves an unrecognized POI name into canonical names and/or coordinates."""
        q = query.strip()
        if not q or len(q) < 2:
            return []

        query_key = f"{q}:{country_hint.strip() if country_hint else ''}"
        if not force_refresh and self._cache_repo:
            cached = await self._cache_repo.get("enhanced_resolver", query_key)
            if cached and isinstance(cached.get("candidates"), list):
                logger.info("MSG <-|  EnhancedLocationResolver cache hit for '%s'", query_key)
                return [EnhancedLocationCandidate(**c) for c in cached["candidates"]]

        candidates: list[EnhancedLocationCandidate] = []
        seen_names: set[str] = {q.lower()}

        async def _cache_and_return(res: list[EnhancedLocationCandidate]) -> list[EnhancedLocationCandidate]:
            if self._cache_repo and res:
                await self._cache_repo.set(
                    "enhanced_resolver",
                    query_key,
                    {"candidates": [c.model_dump() for c in res]},
                )
            return res

        # -------------------------------------------------------------------------
        # Tier 1: Wikipedia Search & Page Coordinates Resolver
        # -------------------------------------------------------------------------
        wiki_candidates = await self._search_wikipedia(q)
        for c in wiki_candidates:
            if c.canonical_name.lower() not in seen_names or c.latitude is not None:
                candidates.append(c)
                seen_names.add(c.canonical_name.lower())
                # If we got exact GPS coordinates from Wikipedia, prioritize it immediately
                if c.latitude is not None and c.longitude is not None:
                    return await _cache_and_return(candidates)

        # -------------------------------------------------------------------------
        # Tier 2: Wikidata Entity Search Resolver (Exact coordinates only)
        # -------------------------------------------------------------------------
        wikidata_candidates = await self._search_wikidata(q)
        for c in wikidata_candidates:
            if c.latitude is not None and c.longitude is not None:
                candidates.append(c)
                seen_names.add(c.canonical_name.lower())
                return await _cache_and_return(candidates)

        # -------------------------------------------------------------------------
        # Tier 3: Gemini Flash-Lite Canonical Query Normalizer (budget=0)
        # Prioritized before non-coordinate Wikidata/Wikipedia title stubs
        # -------------------------------------------------------------------------
        llm_candidates = await self._resolve_with_gemini(q, country_hint=country_hint)
        for lc in llm_candidates:
            if lc.canonical_name.lower() not in seen_names or lc.latitude is not None:
                candidates.append(lc)
                seen_names.add(lc.canonical_name.lower())
                if lc.latitude is not None and lc.longitude is not None:
                    return await _cache_and_return(candidates)

        # Append non-coordinate Wikidata title stubs only as fallback after Gemini
        for c in wikidata_candidates:
            if c.canonical_name.lower() not in seen_names:
                candidates.append(c)
                seen_names.add(c.canonical_name.lower())

        # -------------------------------------------------------------------------
        # Tier 4: Heuristic Suffix & Stopword Stripping
        # -------------------------------------------------------------------------
        cleaned = q
        for pat in _COMMON_POI_SUFFIXES:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned and cleaned.lower() not in seen_names:
            candidates.append(
                EnhancedLocationCandidate(
                    canonical_name=cleaned,
                    source="cleaned_query",
                )
            )

        return await _cache_and_return(candidates)

    async def _search_wikipedia(self, query: str) -> list[EnhancedLocationCandidate]:
        """Queries Wikipedia search API and retrieves canonical title and coordinates."""
        candidates: list[EnhancedLocationCandidate] = []
        search_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={quote(query)}&format=json&limit=2"
        )
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}

        try:
            logger.info("MSG   |-> Wikipedia query search: '%s'", query)
            resp = await self._get_http(search_url, headers=headers)
            if resp.status_code != 200:
                return []

            data = resp.json()
            search_items = data.get("query", {}).get("search", [])
            for item in search_items:
                title = item.get("title", "").strip()
                if not title or "disambiguation" in title.lower() or "list of" in title.lower():
                    continue

                # Fetch coordinates for candidate title
                coords = await self._fetch_wikipedia_coordinates(title, headers)
                if coords:
                    lat, lon = coords
                    logger.info("MSG   |<- Wikipedia resolved coordinates for '%s': (%s, %s)", title, lat, lon)
                    candidates.append(
                        EnhancedLocationCandidate(
                            canonical_name=title,
                            latitude=lat,
                            longitude=lon,
                            source="wikipedia_coordinates",
                        )
                    )
                else:
                    candidates.append(
                        EnhancedLocationCandidate(
                            canonical_name=title,
                            source="wikipedia_title",
                        )
                    )
        except Exception as exc:
            logger.debug("Wikipedia search failed for '%s': %s", query, exc)

        return candidates

    async def _fetch_wikipedia_coordinates(
        self, title: str, headers: dict[str, str]
    ) -> tuple[float, float] | None:
        """Fetches primary GPS coordinates from a Wikipedia article title."""
        url = (
            f"https://en.wikipedia.org/w/api.php?action=query&prop=coordinates"
            f"&titles={quote(title)}&format=json"
        )
        try:
            resp = await self._get_http(url, headers=headers)
            if resp.status_code == 200:
                pages = resp.json().get("query", {}).get("pages", {})
                for _, page in pages.items():
                    coord_list = page.get("coordinates", [])
                    if coord_list and isinstance(coord_list, list):
                        lat = float(coord_list[0]["lat"])
                        lon = float(coord_list[0]["lon"])
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            return lat, lon
        except Exception as exc:
            logger.debug("Failed fetching coordinates for title '%s': %s", title, exc)
        return None

    async def _search_wikidata(self, query: str) -> list[EnhancedLocationCandidate]:
        """Queries Wikidata entity search and extracts P625 coordinates."""
        candidates: list[EnhancedLocationCandidate] = []
        url = (
            f"https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={quote(query)}&language=en&format=json&limit=2"
        )
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}

        try:
            logger.info("MSG   |-> Wikidata entity search: '%s'", query)
            resp = await self._get_http(url, headers=headers)
            if resp.status_code != 200:
                return []

            items = resp.json().get("search", [])
            for item in items:
                qid = item.get("id")
                label = item.get("label", "").strip()
                if not qid or not label:
                    continue

                # Query entity P625 claims
                entity_url = (
                    f"https://www.wikidata.org/w/api.php?action=wbgetentities"
                    f"&ids={qid}&props=claims|labels&languages=en&format=json"
                )
                e_resp = await self._get_http(entity_url, headers=headers)
                if e_resp.status_code == 200:
                    entity = e_resp.json().get("entities", {}).get(qid, {})
                    claims = entity.get("claims", {})
                    p625 = claims.get("P625", [])
                    if p625:
                        mainsnak = p625[0].get("mainsnak", {})
                        datavalue = mainsnak.get("datavalue", {}).get("value")
                        if isinstance(datavalue, dict) and "latitude" in datavalue and "longitude" in datavalue:
                            lat = float(datavalue["latitude"])
                            lon = float(datavalue["longitude"])
                            if -90 <= lat <= 90 and -180 <= lon <= 180:
                                candidates.append(
                                    EnhancedLocationCandidate(
                                        canonical_name=label,
                                        latitude=lat,
                                        longitude=lon,
                                        source="wikidata_coordinates",
                                    )
                                )
                                continue
                candidates.append(
                    EnhancedLocationCandidate(
                        canonical_name=label,
                        source="wikidata_title",
                    )
                )
        except Exception as exc:
            logger.debug("Wikidata entity search failed for '%s': %s", query, exc)

        return candidates

    async def _resolve_with_gemini(
        self, query: str, country_hint: str | None = None
    ) -> list[EnhancedLocationCandidate]:
        """Invokes Google Gemini with thinking_budget=0 for canonical POI name and transliteration resolution."""
        api_key = os.environ.get("GOOGLE_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return []

        prompt = (
            f"Resolve the point-of-interest (POI) or destination query into its official canonical English name "
            f"and geographic location context.\n"
            f"Handle non-standard transliterations, historical names, typographical errors, and phonetic spellings "
            f"(e.g. Arabic, Cyrillic, Asian transliterations, alternative Romanizations).\n"
            f"Raw Query: {query}\n"
            f"Country Hint: {country_hint or 'Unknown'}\n\n"
            f"Instructions:\n"
            f"- Identify the real-world destination or attraction.\n"
            f"- Return its official canonical modern name (e.g. 'Okapi Faunal Reserve' -> 'Okapi Wildlife Reserve', 'Barakesh' -> 'Baraqish').\n"
            f"- List all prominent alternative spellings or romanized transliterations in alternate_names.\n"
            f"- Set is_known_poi to true if this corresponds to a genuine place or landmark.\n"
        )

        try:
            logger.info("MSG   |-> [Gemini Flash Canonicalizer] query='%s' (country_hint=%s)", query, country_hint)
            client = self._get_genai_client(api_key)
            from google.genai import types

            model_name = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.8-flash"
            config_kwargs: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_schema": LLMPoiResolution,
                "temperature": 0.0,
            }
            if "flash" in model_name.lower():
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

            config = types.GenerateContentConfig(**config_kwargs)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            except Exception as gen_err:
                # If thinking_config was rejected by model (e.g. gemini-3.5-flash-lite), retry without it
                if "thinking_config" in config_kwargs:
                    config_kwargs_no_think = {
                        k: v for k, v in config_kwargs.items() if k != "thinking_config"
                    }
                    config_fallback = types.GenerateContentConfig(**config_kwargs_no_think)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config_fallback,
                    )
                else:
                    raise gen_err

            if not response or not response.text:
                return []

            data = json.loads(response.text)
            parsed = LLMPoiResolution(**data)
            if parsed.is_known_poi and parsed.canonical_name:
                logger.info(
                    "MSG   |<- [Gemini Flash Canonicalizer] resolved '%s' -> '%s' (alternates=%s, %s)",
                    query,
                    parsed.canonical_name,
                    parsed.alternate_names,
                    parsed.country,
                )
                # Attempt immediate coordinate resolution from Wikipedia for canonical name
                headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
                coords = await self._fetch_wikipedia_coordinates(parsed.canonical_name, headers)
                if not coords:
                    for alt in parsed.alternate_names:
                        coords = await self._fetch_wikipedia_coordinates(alt, headers)
                        if coords:
                            break

                lat, lon = coords if coords else (None, None)
                src = "wikipedia_coordinates" if coords else "gemini_flash_lite"
                results: list[EnhancedLocationCandidate] = [
                    EnhancedLocationCandidate(
                        canonical_name=parsed.canonical_name,
                        latitude=lat,
                        longitude=lon,
                        country=parsed.country or country_hint,
                        state_province=parsed.state_province,
                        city=parsed.city,
                        source=src,
                    )
                ]
                for alt in parsed.alternate_names:
                    alt_clean = alt.strip()
                    if alt_clean and alt_clean.lower() != parsed.canonical_name.lower():
                        results.append(
                            EnhancedLocationCandidate(
                                canonical_name=alt_clean,
                                country=parsed.country or country_hint,
                                state_province=parsed.state_province,
                                city=parsed.city,
                                source="gemini_alternate_name",
                            )
                        )
                return results
        except Exception as exc:
            logger.debug("Gemini canonical resolution failed for '%s': %s", query, exc)

        return []

    def _get_genai_client(self, api_key: str) -> Any:
        """Lazily creates or returns the Google GenAI client."""
        if self._gemini_client is None:
            from google import genai

            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    async def _get_http(self, url: str, headers: dict[str, str]) -> httpx.Response:
        """Performs HTTP GET using internal client or creates a short-lived client."""
        if self._client is not None:
            return await self._client.get(url, headers=headers, timeout=self._timeout_seconds)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            return await client.get(url, headers=headers)

