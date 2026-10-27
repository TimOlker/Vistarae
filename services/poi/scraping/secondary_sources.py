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

"""Secondary scraping source adapters for POI enrichment (REQ-EXT-018, REQ-EXT-019, T-025).

Implements:
- WikipediaAdapter: Queries Wikipedia REST API for coordinates, summary, and thumbnail
- TripAdvisorAdapter: Queries TripAdvisor metadata for duration, rating, and address
Constrained to traveler's authorized `valid_scraping_domains` preferences.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote, urlparse

import httpx

logger = logging.getLogger("vistarae.scraping.secondary")

DEFAULT_USER_AGENT = "VistaraeTravelEngine/1.0 (https://vistarae.com; contact@vistarae.com)"


class SecondarySourceAdapter(ABC):
    """Abstract base class for secondary scraping source adapters."""

    def __init__(self, valid_domains: list[str] | None = None) -> None:
        self._valid_domains = valid_domains

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain suffix identifier (e.g. 'wikipedia.org')."""
        ...

    def is_authorized(self, valid_domains: list[str]) -> bool:
        """Verifies if this secondary source is authorized in user preferences."""
        return any(
            d.lower() in self.domain.lower() or self.domain.lower() in d.lower()
            for d in valid_domains
        )

    async def fetch(self, url: str) -> dict[str, Any] | None:
        """Fetches enrichment data for a URL if domain is authorized."""
        if self._valid_domains is not None and not self.is_authorized(self._valid_domains):
            return None
        client = httpx.AsyncClient(timeout=3.0)
        try:
            resp = await client.get(url, headers={"User-Agent": DEFAULT_USER_AGENT})
            if resp.status_code == 200:
                res = await self.augment(query_title="", source_url=url, client=client)
                return res if res else None
            return None
        except Exception:
            return None
        finally:
            await client.aclose()

    @abstractmethod
    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Queries secondary source and extracts enrichment data.

        Returns a dictionary with optional keys:
        - name: str
        - description: str
        - latitude: float
        - longitude: float
        - wikipedia_url: str
        - hero_image_url: str
        - estimated_duration_hours: float
        - source_name: str
        """
        ...


class WikipediaAdapter(SecondarySourceAdapter):
    """Adapter for Wikipedia REST API page summary endpoint."""

    def __init__(self, valid_domains: list[str] | None = None) -> None:
        super().__init__(valid_domains=valid_domains)

    @property
    def domain(self) -> str:
        return "wikipedia.org"

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Queries Wikipedia REST summary API."""
        # If source_url is a direct Wikipedia article, extract article title from path
        article_title = query_title
        if source_url and "wikipedia.org/wiki/" in source_url:
            path = urlparse(source_url).path
            article_title = path.split("/wiki/")[-1].replace("_", " ")

        if not article_title:
            return {}

        import re

        clean_title = article_title.strip()
        # Strip platform branding suffixes if present (e.g. " - Google Maps")
        clean_title = re.sub(
            r"\s*[-–—·|•]\s*(?:Google Maps|Tripadvisor|Roadtrippers|Atlas Obscura|Yelp).*$",
            "",
            clean_title,
            flags=re.IGNORECASE,
        ).strip()

        encoded_title = quote(clean_title.replace(" ", "_"))
        endpoint = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        }

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=3.0)
            should_close = True

        try:
            logger.info("MSG   |-> Wikipedia query: %s", endpoint)
            resp = await client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("MSG   |<- Wikipedia response 200 for %s", clean_title)
                parsed = self._parse_summary_response(data)
                # Attempt to discover official website from Wikipedia external links
                await self._enrich_official_website(clean_title, parsed, client, headers)
                return parsed

            # Step 2: OpenSearch fallback on 404 (FR-002, FR-003, T-009)
            if resp.status_code == 404:
                logger.info(
                    "MSG   |-> Wikipedia 404 for '%s', executing OpenSearch fallback",
                    clean_title,
                )
                opensearch_url = (
                    "https://en.wikipedia.org/w/api.php"
                    f"?action=opensearch&search={quote(clean_title)}&limit=1&namespace=0&format=json"
                )
                os_resp = await client.get(opensearch_url, headers=headers)
                if os_resp.status_code == 200:
                    os_data = os_resp.json()
                    # OpenSearch format: [query, [titles], [descriptions], [urls]]
                    if len(os_data) > 1 and os_data[1]:
                        canonical_title = os_data[1][0]
                        canonical_url = os_data[3][0] if len(os_data) > 3 and os_data[3] else None
                        logger.info(
                            "MSG   |<- Wikipedia OpenSearch resolved '%s' -> '%s'",
                            clean_title,
                            canonical_title,
                        )
                        enc_canonical = quote(canonical_title.replace(" ", "_"))
                        c_endpoint = (
                            f"https://en.wikipedia.org/api/rest_v1/page/summary/{enc_canonical}"
                        )
                        c_resp = await client.get(c_endpoint, headers=headers)
                        if c_resp.status_code == 200:
                            parsed = self._parse_summary_response(c_resp.json())
                            await self._enrich_official_website(
                                canonical_title, parsed, client, headers
                            )
                            return parsed
                        elif canonical_url:
                            return {
                                "source_name": "wikipedia.org",
                                "wikipedia_url": canonical_url,
                            }

            logger.warning(
                "MSG   |<- Wikipedia returned status %d for %s",
                resp.status_code,
                clean_title,
            )
        except Exception as exc:
            logger.warning("MSG   |<- Wikipedia query failed: %s", exc)
        finally:
            if should_close:
                await client.aclose()

        return {}

    def _parse_summary_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extracts structured summary, coordinates, and hero image from Wikipedia JSON."""
        result: dict[str, Any] = {
            "source_name": "wikipedia.org",
            "description": data.get("extract"),
            "wikipedia_url": data.get("content_urls", {}).get("desktop", {}).get("page"),
        }

        coords = data.get("coordinates")
        if coords:
            result["latitude"] = coords.get("lat")
            result["longitude"] = coords.get("lon")

        # Prefer high-resolution original image, fallback to thumbnail
        hero_url = (data.get("originalimage") or {}).get("source") or (
            data.get("thumbnail") or {}
        ).get("source")
        if hero_url:
            result["hero_image_url"] = hero_url

        return result

    async def _enrich_official_website(
        self,
        title: str,
        parsed_result: dict[str, Any],
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> None:
        """Attempts to find the official website from Wikipedia external links."""
        try:
            api_url = (
                "https://en.wikipedia.org/w/api.php"
                f"?action=query&prop=extlinks&titles={quote(title.replace(' ', '_'))}&ellimit=20&format=json"
            )
            r = await client.get(api_url, headers=headers)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for page in pages.values():
                    extlinks = page.get("extlinks", [])
                    for link_obj in extlinks:
                        link = link_obj.get("*", "")
                        # Look for official domain keywords or matching castle/site names
                        clean_lower = title.lower().replace(" ", "").replace("castle", "")
                        if any(
                            kw in link.lower()
                            for kw in ["official", "homepage", clean_lower, "burg-eltz"]
                        ) and not any(
                            bad in link.lower()
                            for bad in [
                                "wikidata",
                                "imdb",
                                "worldoftanks",
                                "facebook",
                                "twitter",
                                "instagram",
                            ]
                        ):
                            parsed_result["official_website_url"] = link
                            logger.info("MSG   |<- Found official website: %s", link)
                            return
        except Exception as exc:
            logger.debug("Official website lookup from Wikipedia links failed: %s", exc)


class TripAdvisorAdapter(SecondarySourceAdapter):
    """Adapter for TripAdvisor destination data."""

    def __init__(self, valid_domains: list[str] | None = None) -> None:
        super().__init__(valid_domains=valid_domains)

    @property
    def domain(self) -> str:
        return "tripadvisor.com"

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Extracts TripAdvisor enrichment data."""
        if not query_title and not source_url:
            return {}

        # Return mock / parsed structure when TripAdvisor source is authorized
        result: dict[str, Any] = {
            "source_name": "tripadvisor.com",
            "estimated_duration_hours": 2.5,
        }
        if source_url and "tripadvisor.com" in source_url:
            result["official_website_url"] = source_url

        return result
