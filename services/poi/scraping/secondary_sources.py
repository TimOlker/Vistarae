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
import re
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from vistarae_core.ports.repositories import IExternalEnrichmentCacheRepository

logger = logging.getLogger("vistarae.scraping.secondary")

DEFAULT_USER_AGENT = "VistaraeTravelEngine/1.0 (https://vistarae.com; contact@vistarae.com)"


def extract_meta_image(html: str, base_url: str = "") -> str | None:
    """Extracts hero image URL from og:image or twitter:image meta tags.

    Inspects:
    1. <meta property="og:image" content="..."> / og:image:secure_url
    2. <meta name="twitter:image" content="..."> / twitter:image:src
    Resolves relative paths against base_url and ensures non-empty, non-data URIs.
    """
    if not html:
        return None

    # 1. BeautifulSoup parsing
    try:
        soup = BeautifulSoup(html, "html.parser")
        for prop in ["og:image", "og:image:secure_url", "image"]:
            meta = soup.find("meta", attrs={"property": prop}) or soup.find(
                "meta", attrs={"name": prop}
            )
            if meta and meta.get("content"):
                val = str(meta["content"]).strip()
                if val and not val.startswith("data:"):
                    return urljoin(base_url, val) if base_url else val

        for name in ["twitter:image", "twitter:image:src"]:
            meta = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            if meta and meta.get("content"):
                val = str(meta["content"]).strip()
                if val and not val.startswith("data:"):
                    return urljoin(base_url, val) if base_url else val
    except Exception as exc:
        logger.debug("BeautifulSoup meta image extraction failed: %s", exc)

    # 2. Regex fallback for resilient extraction
    patterns = [
        re.compile(
            r'<meta[^>]*?(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["\'][^>]*?content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        re.compile(
            r'<meta[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["\']',
            re.IGNORECASE,
        ),
    ]
    for pat in patterns:
        m = pat.search(html)
        if m:
            val = m.group(1).strip()
            if val and not val.startswith("data:"):
                return urljoin(base_url, val) if base_url else val

    return None


def extract_meta_description(html: str) -> str | None:
    """Extracts summary/description from HTML meta tags (og:description, description, twitter:description)."""
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        for prop in ["og:description", "description", "twitter:description"]:
            for meta in soup.find_all("meta", attrs={"property": prop}) + soup.find_all(
                "meta", attrs={"name": prop}
            ):
                if meta and meta.get("content"):
                    clean = str(meta["content"]).strip()
                    if len(clean) > 15:
                        return clean
    except Exception as exc:
        logger.debug("BeautifulSoup meta description extraction failed: %s", exc)

    # Regex fallback
    patterns = [
        re.compile(
            r'<meta[^>]*?(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]*?content=["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        re.compile(
            r'<meta[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:description|description|twitter:description)["\']',
            re.IGNORECASE,
        ),
    ]
    for pat in patterns:
        m = pat.search(html)
        if m:
            clean = m.group(1).strip()
            if len(clean) > 15:
                return clean

    return None


async def scrape_website_hero_image(
    url: str,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
) -> str | None:
    """Fetches official website and inspects og:image and twitter:image meta tags before falling back to empty."""
    if not url or not url.startswith("http"):
        return None

    req_headers = headers or {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=4.0, follow_redirects=True)
        should_close = True

    try:
        logger.info("MSG   |-> Inspecting official website for hero image: %s", url)
        resp = await client.get(url, headers=req_headers)
        if resp.status_code == 200:
            found_img = extract_meta_image(resp.text, str(resp.url))
            if found_img:
                logger.info("MSG   |<- Found official website hero image: %s", found_img)
                return found_img
    except Exception as exc:
        logger.debug("Failed scraping hero image from official website %s: %s", url, exc)
    finally:
        if should_close:
            await client.aclose()

    return None


async def scrape_website_metadata(
    url: str,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
    cache_repo: IExternalEnrichmentCacheRepository | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetches official website and extracts images and description with caching."""
    if not url or not url.startswith("http"):
        return {"images": [], "description": None}

    if not force_refresh and cache_repo:
        cached = await cache_repo.get("website_metadata", url)
        if cached:
            return cached

    req_headers = headers or {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=4.0, follow_redirects=True)
        should_close = True

    res: dict[str, Any] = {"images": [], "description": None}
    try:
        resp = await client.get(url, headers=req_headers)
        if resp.status_code == 200:
            found_img = extract_meta_image(resp.text, str(resp.url))
            if found_img:
                res["images"].append(found_img)
            desc = extract_meta_description(resp.text)
            if desc:
                res["description"] = desc
    except Exception as exc:
        logger.debug("Failed scraping metadata from official website %s: %s", url, exc)
    finally:
        if should_close:
            await client.aclose()

    if cache_repo and (res["images"] or res["description"]):
        await cache_repo.set("website_metadata", url, res)

    return res


class SecondarySourceAdapter(ABC):
    """Abstract base class for secondary scraping source adapters."""

    def __init__(
        self,
        valid_domains: list[str] | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        self._valid_domains = valid_domains
        self._cache_repo = cache_repo

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


WIKIDATA_PROPERTY_MAP: dict[str, tuple[str, Any]] = {
    "P856": ("Official Website", lambda val: val if str(val).startswith("http") else None),
    "P7772": ("Atlas Obscura", lambda val: f"https://www.atlasobscura.com/places/{val}"),
    "P3134": (
        "Tripadvisor",
        lambda val: (
            f"https://www.tripadvisor.com/Attraction_Review-d{val}"
            if str(val).isdigit()
            else f"https://www.tripadvisor.com/{val}"
        ),
    ),
    "P4056": (
        "National Trust",
        lambda val: (
            f"https://www.nationaltrust.org.uk/{val}"
            if not str(val).startswith("http")
            else str(val)
        ),
    ),
    "P3516": (
        "English Heritage",
        lambda val: (
            f"https://www.english-heritage.org.uk/visit/places/{val}"
            if not str(val).startswith("http")
            else str(val)
        ),
    ),
    "P6766": (
        "AllTrails",
        lambda val: (
            f"https://www.alltrails.com/trail/{val}"
            if not str(val).startswith("http")
            else str(val)
        ),
    ),
    "P10689": (
        "Google Arts & Culture",
        lambda val: f"https://artsandculture.google.com/entity/{val}",
    ),
}

MAP_SERVICE_DOMAINS: tuple[str, ...] = (
    "openstreetmap.org",
    "osm.org",
    "google.com/maps",
    "maps.google.",
    "goo.gl/maps",
    "maps.app.goo.gl",
    "bing.com/maps",
    "maps.apple.com",
    "mapquest.com",
    "waze.com",
    "here.com",
    "wego.here.com",
    "geohack.toolforge.org",
)

MAP_SERVICE_NAMES: set[str] = {
    "openstreetmap",
    "osm",
    "google maps",
    "googlemaps",
    "bing maps",
    "apple maps",
    "mapquest",
    "waze",
}


def is_map_service_url(url: str | None, name: str | None = None) -> bool:
    """Checks whether a website URL or label belongs to an interactive mapping / GPS service.

    POIs already possess GPS coordinates, so third-party map links (OpenStreetMap,
    Google Maps, etc.) are excluded from POI websites during AI enrichment.
    """
    if name and name.strip().lower() in MAP_SERVICE_NAMES:
        return True
    if not url:
        return False
    u = url.strip().lower()
    return any(d in u for d in MAP_SERVICE_DOMAINS)


def canonicalize_url(url: str | None) -> str:
    """Normalizes a URL: resolves URL percent-encoding, trims whitespace, and removes trailing slashes."""
    if not url or not isinstance(url, str):
        return ""
    clean = url.strip()
    if not clean or not clean.startswith("http"):
        return ""
    try:
        clean = unquote(clean).strip()
    except Exception:
        pass
    clean = clean.rstrip("/")
    return clean


def is_unwanted_website_url(url: str | None, name: str | None = None) -> bool:
    """Checks whether a website URL is a map service or an obsolete web archive URL."""
    if not url:
        return True
    if is_map_service_url(url, name):
        return True
    u_lower = url.lower()
    if "web.archive.org" in u_lower or "archive.org/web" in u_lower:
        return True
    return False

KNOWN_DOMAIN_NAMES: dict[str, str] = {
    "atlasobscura.com": "Atlas Obscura",
    "tripadvisor.com": "Tripadvisor",
    "roadtrippers.com": "Roadtrippers",
    "alltrails.com": "AllTrails",
    "nationaltrust.org.uk": "National Trust",
    "english-heritage.org.uk": "English Heritage",
    "historicenvironment.scot": "Historic Environment Scotland",
    "nps.gov": "National Park Service",
    "unesco.org": "UNESCO World Heritage",
    "visitwales.com": "Visit Wales",
    "visitscotland.com": "Visit Scotland",
    "visitengland.com": "Visit England",
    "museum.wales": "National Museum Wales",
}


POI_CATEGORIES: set[str] = {
    "museum",
    "castle",
    "cathedral",
    "church",
    "palace",
    "fortress",
    "fort",
    "park",
    "garden",
    "gardens",
    "bridge",
    "tower",
    "ruins",
    "abbey",
    "sanctuary",
    "temple",
    "shrine",
    "monument",
    "memorial",
    "villa",
    "baths",
    "amphitheatre",
    "amphitheater",
    "waterfall",
    "falls",
    "lake",
    "beach",
    "lookout",
    "viewpoint",
    "overlook",
    "zoo",
    "aquarium",
    "farm",
    "market",
    "brewery",
    "distillery",
    "winery",
    "trail",
    "cave",
    "caves",
    "gorge",
    "lighthouse",
    "inn",
    "pub",
    "house",
    "estate",
}


class WikidataAdapter(SecondarySourceAdapter):
    """Adapter for Wikidata knowledge graph (REQ-EXT-018, REQ-EXT-019).

    Elevated in POI search to retrieve structured properties, hero images, coordinates,
    and cross-platform related websites (Atlas Obscura, Tripadvisor, Official Website, etc.).
    """

    def __init__(
        self,
        valid_domains: list[str] | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        super().__init__(valid_domains=valid_domains, cache_repo=cache_repo)

    @property
    def domain(self) -> str:
        return "wikidata.org"

    async def search_entities(
        self,
        query: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        poi_name: str | None = None,
    ) -> list[tuple[float, str, dict[str, Any]]]:
        """Searches Wikidata items by name label and aliases."""
        url = (
            f"https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={quote(query)}&language=en&format=json&limit=5"
        )
        try:
            logger.info("MSG   |-> Wikidata search: %s", query)
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("search", [])
                candidates = []
                for item in items:
                    qid = item.get("id")
                    label = item.get("label", "")
                    desc = item.get("description", "")
                    if qid and label:
                        score = WikipediaAdapter._score_search_result(
                            query, label, desc, poi_name=poi_name
                        )
                        candidates.append((score, qid, item))
                candidates.sort(key=lambda x: x[0], reverse=True)
                return candidates
        except Exception as exc:
            logger.debug("Wikidata search failed for '%s': %s", query, exc)
        return []

    async def fetch_entity_details(
        self,
        qid: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        query_hint: str = "",
    ) -> dict[str, Any] | None:
        """Fetches full entity claims, sitelinks, and rich attributes for a QID."""
        url = (
            f"https://www.wikidata.org/w/api.php?action=wbgetentities"
            f"&ids={qid}&props=claims|descriptions|labels|sitelinks&languages=en&format=json"
        )
        try:
            logger.info("MSG   |-> Fetching Wikidata entity: %s", qid)
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            entities = resp.json().get("entities", {})
            entity = entities.get(qid)
            if not entity:
                return None

            label = entity.get("labels", {}).get("en", {}).get("value") or query_hint or qid
            desc = entity.get("descriptions", {}).get("en", {}).get("value")
            claims = entity.get("claims", {})
            sitelinks = entity.get("sitelinks", {})

            result: dict[str, Any] = {
                "source_name": "wikidata.org",
                "name": label,
                "description": desc,
                "wikibase_item": qid,
                "related_websites": [],
            }

            # Coordinates P625
            coords = claims.get("P625", [])
            if coords:
                mainsnak = coords[0].get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {}).get("value")
                if (
                    isinstance(datavalue, dict)
                    and "latitude" in datavalue
                    and "longitude" in datavalue
                ):
                    result["latitude"] = float(datavalue["latitude"])
                    result["longitude"] = float(datavalue["longitude"])

            # Wikipedia URL from sitelinks.enwiki
            enwiki = sitelinks.get("enwiki", {}).get("title")
            if enwiki:
                wiki_url = canonicalize_url(f"https://en.wikipedia.org/wiki/{enwiki.replace(' ', '_')}")
                result["wikipedia_url"] = wiki_url

            # P856 Official Website
            official_claims = claims.get("P856", [])
            if official_claims:
                off_val = official_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(off_val, str) and off_val.startswith("http"):
                    result["official_website_url"] = canonicalize_url(off_val)

            # Build related websites list
            related = self.extract_related_websites(
                claims=claims,
                sitelinks=sitelinks,
                official_url=result.get("official_website_url"),
                wiki_url=result.get("wikipedia_url"),
            )
            result["related_websites"] = related

            # Hero image P18
            p18_claims = claims.get("P18", [])
            if p18_claims:
                img_name = p18_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(img_name, str) and img_name:
                    result["hero_image_url"] = (
                        f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(img_name)}"
                    )

            # If hero image is absent but official website is available, scrape official website
            if not result.get("hero_image_url") and result.get("official_website_url"):
                site_hero = await scrape_website_hero_image(
                    result["official_website_url"], client=client, headers=headers
                )
                if site_hero:
                    result["hero_image_url"] = site_hero

            return result
        except Exception as exc:
            logger.debug("Failed fetching Wikidata entity '%s': %s", qid, exc)
        return None

    @staticmethod
    def extract_related_websites(
        claims: dict[str, Any],
        sitelinks: dict[str, Any] | None = None,
        official_url: str | None = None,
        wiki_url: str | None = None,
    ) -> list[dict[str, str]]:
        """Constructs a deduplicated list of related websites from claims and sitelinks."""
        websites: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        def _add(name: str, url: str | None):
            clean = canonicalize_url(url)
            if not clean or not clean.startswith("http"):
                return
            if is_unwanted_website_url(clean, name):
                return
            key = clean.lower()
            if key not in seen_urls:
                seen_urls.add(key)
                websites.append({"name": name, "url": clean})

        if official_url:
            _add("Official Website", official_url)
        if wiki_url:
            _add("Wikipedia", wiki_url)

        if sitelinks:
            enwiki = sitelinks.get("enwiki", {}).get("title")
            if enwiki:
                _add(
                    "Wikipedia", f"https://en.wikipedia.org/wiki/{enwiki.replace(' ', '_')}"
                )

        for prop, (site_name, formatter) in WIKIDATA_PROPERTY_MAP.items():
            prop_claims = claims.get(prop, [])
            for c in prop_claims:
                val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if val is not None:
                    try:
                        formatted = formatter(val)
                        if formatted:
                            _add(site_name, formatted)
                    except Exception:
                        pass

        return websites

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        force_refresh: bool = False,
        poi_name: str | None = None,
    ) -> dict[str, Any]:
        """Queries Wikidata by entity ID or name search."""
        if not query_title and not source_url:
            return {}

        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=4.0)
            should_close = True

        try:
            # If source_url points to a Wikidata QID
            if source_url and "wikidata.org/wiki/Q" in source_url:
                qid = source_url.split("/wiki/")[-1].split("?")[0].strip()
                res = await self.fetch_entity_details(qid, client, headers, query_hint=query_title)
                if res:
                    return res

            # Search Wikidata entities
            effective_poi_name = poi_name or (query_title.split(",")[0] if "," in query_title else query_title)
            candidates = await self.search_entities(
                query_title, client, headers, poi_name=effective_poi_name
            )
            for score, qid, item in candidates:
                if score > 0.2:
                    logger.info(
                        "MSG   |<- Wikidata resolved '%s' -> %s ('%s', score=%.2f)",
                        query_title,
                        qid,
                        item.get("label"),
                        score,
                    )
                    res = await self.fetch_entity_details(
                        qid, client, headers, query_hint=item.get("label", query_title)
                    )
                    if res:
                        return res
        except Exception as exc:
            logger.debug("Wikidata augment failed for '%s': %s", query_title, exc)
        finally:
            if should_close:
                await client.aclose()

        return {}


class WikipediaAdapter(SecondarySourceAdapter):
    """Adapter for Wikipedia REST summary API, OpenSearch, CirrusSearch, and Wikidata claims."""

    def __init__(
        self,
        valid_domains: list[str] | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        super().__init__(valid_domains=valid_domains, cache_repo=cache_repo)
        self._wikidata = WikidataAdapter(valid_domains=valid_domains, cache_repo=cache_repo)

    @property
    def domain(self) -> str:
        return "wikipedia.org"

    def _generate_candidate_queries(self, title: str) -> list[str]:
        """Builds candidate query variations for higher Wikipedia detection rate."""
        clean_title = title.strip()
        clean_title = re.sub(
            r"\s*[-–—·|•]\s*(?:Google Maps|Tripadvisor|Roadtrippers|Atlas Obscura|Yelp).*$",
            "",
            clean_title,
            flags=re.IGNORECASE,
        ).strip()

        candidate_queries = [clean_title]
        no_parens = re.sub(r"\s*\([^)]*\)", "", clean_title).strip()
        if no_parens and no_parens not in candidate_queries:
            candidate_queries.append(no_parens)
        before_comma = clean_title.split(",")[0].strip()
        if before_comma and before_comma not in candidate_queries:
            candidate_queries.append(before_comma)
        no_the = re.sub(r"^The\s+", "", clean_title, flags=re.IGNORECASE).strip()
        if no_the and no_the not in candidate_queries:
            candidate_queries.append(no_the)
        return candidate_queries

    async def _try_summary_query(
        self,
        q_term: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        """Executes a single Wikipedia REST summary query."""
        encoded_title = quote(q_term.replace(" ", "_"))
        endpoint = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        try:
            logger.info("MSG   |-> Wikipedia query: %s", endpoint)
            resp = await client.get(endpoint, headers=headers)
            if resp.status_code == 200:
                logger.info("MSG   |<- Wikipedia response 200 for %s", q_term)
                parsed = self._parse_summary_response(resp.json())
                await self._enrich_official_website(q_term, parsed, client, headers)
                return parsed
        except BaseException as exc:
            logger.debug("Wikipedia REST query error for '%s': %s", q_term, exc)
        return None

    @staticmethod
    def _score_search_result(
        query: str, title: str, snippet: str = "", poi_name: str | None = None
    ) -> float:
        """Scores relevance of a search candidate against the POI query."""
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
        }
        q_tokens = {w for w in re.findall(r"\w+", query.lower()) if w not in stop_words}
        t_tokens = {w for w in re.findall(r"\w+", title.lower()) if w not in stop_words}
        s_tokens = {
            w
            for w in re.findall(r"\w+", re.sub(r"<[^>]+>", " ", snippet.lower()))
            if w not in stop_words
        }

        if not q_tokens:
            return 0.0

        effective_poi_name = poi_name or (query.split(",")[0] if "," in query else None)
        p_tokens: set[str] = set()
        if effective_poi_name:
            p_tokens = {
                w for w in re.findall(r"\w+", effective_poi_name.lower()) if w not in stop_words
            }
            if p_tokens:
                poi_overlap = len(p_tokens.intersection(t_tokens)) / len(p_tokens)
                if poi_overlap == 0.0:
                    return 0.0

        title_overlap = len(q_tokens.intersection(t_tokens)) / len(q_tokens)
        total_overlap = len(q_tokens.intersection(t_tokens.union(s_tokens))) / len(q_tokens)

        q_cats = q_tokens.intersection(POI_CATEGORIES)
        t_cats = t_tokens.intersection(POI_CATEGORIES)
        category_bonus = 0.0
        if q_cats:
            category_bonus = 0.4 if q_cats.intersection(t_cats) else -0.3

        if effective_poi_name and p_tokens:
            poi_overlap = len(p_tokens.intersection(t_tokens)) / len(p_tokens)
            category_bonus += 0.35 * poi_overlap

        return (title_overlap * 0.6) + (total_overlap * 0.3) + category_bonus

    async def _try_generator_search_query(
        self,
        q_term: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        fuzzy: bool = False,
        poi_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Executes fuzzy search with redirects=1 and action=query&generator=search.

        Enables alternate POI titles (e.g. 'Caerleon Roman Legion Museum') to resolve
        to canonical articles (e.g. 'National Roman Legion Museum').
        """
        search_term = f"{q_term}~" if fuzzy else q_term
        logger.info(
            "MSG   |-> Wikipedia generator=search for '%s' (fuzzy=%s, redirects=1)",
            search_term,
            fuzzy,
        )
        api_url = (
            "https://en.wikipedia.org/w/api.php?"
            "action=query"
            "&generator=search"
            f"&gsrsearch={quote(search_term)}"
            "&gsrlimit=5"
            "&gsrnamespace=0"
            "&redirects=1"
            "&prop=coordinates|pageprops|pageimages|info|extracts"
            "&exintro=1"
            "&explaintext=1"
            "&inprop=url"
            "&pithumbsize=1000"
            "&format=json"
        )
        try:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code != 200:
                return None

            data = resp.json()
            pages_dict = data.get("query", {}).get("pages", {})
            if not pages_dict:
                if not fuzzy:
                    return await self._try_generator_search_query(
                        q_term, client, headers, fuzzy=True, poi_name=poi_name
                    )
                return None

            candidate_pages: list[tuple[float, dict[str, Any]]] = []
            for p in pages_dict.values():
                title = p.get("title", "")
                if not title or title.lower().startswith("list of "):
                    continue
                extract = p.get("extract", "")
                score = self._score_search_result(q_term, title, extract, poi_name=poi_name)
                candidate_pages.append((score, p))

            candidate_pages.sort(key=lambda x: x[0], reverse=True)

            for score, page_data in candidate_pages:
                if score > 0.2:
                    p_title = page_data.get("title", "")
                    logger.info(
                        "MSG   |<- Generator search resolved '%s' -> '%s' (score=%.2f)",
                        q_term,
                        p_title,
                        score,
                    )
                    parsed: dict[str, Any] = {
                        "source_name": "wikipedia.org",
                        "name": p_title,
                        "description": page_data.get("extract"),
                        "wikipedia_url": page_data.get("canonicalurl")
                        or page_data.get("fullurl")
                        or f"https://en.wikipedia.org/wiki/{quote(p_title.replace(' ', '_'))}",
                        "wikibase_item": (page_data.get("pageprops") or {}).get("wikibase_item"),
                    }
                    hero_url = (page_data.get("original") or {}).get("source") or (
                        page_data.get("thumbnail") or {}
                    ).get("source")
                    if hero_url:
                        parsed["hero_image_url"] = hero_url

                    coords = page_data.get("coordinates")
                    if coords and len(coords) > 0:
                        parsed["latitude"] = coords[0].get("lat")
                        parsed["longitude"] = coords[0].get("lon")

                    await self._enrich_official_website(p_title, parsed, client, headers)
                    return parsed

            if not fuzzy:
                return await self._try_generator_search_query(
                    q_term, client, headers, fuzzy=True, poi_name=poi_name
                )
        except BaseException as exc:
            logger.debug("Wikipedia generator search error for '%s': %s", q_term, exc)

        return None

    async def _try_opensearch_query(
        self,
        q_term: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        poi_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Executes OpenSearch fallback for a query term with semantic re-ranking."""
        logger.info("MSG   |-> Wikipedia 404 for '%s', executing OpenSearch fallback", q_term)
        opensearch_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={quote(q_term)}&limit=5&namespace=0&format=json"
        try:
            os_resp = await client.get(opensearch_url, headers=headers)
            if os_resp.status_code != 200:
                return None
            os_data = os_resp.json()
            if len(os_data) <= 1 or not os_data[1]:
                return None

            titles = os_data[1]
            descs = os_data[2] if len(os_data) > 2 else []
            urls = os_data[3] if len(os_data) > 3 else []

            pairs = []
            for idx, canonical_title in enumerate(titles):
                canonical_desc = descs[idx] if len(descs) > idx else ""
                canonical_url = urls[idx] if len(urls) > idx else None
                score = self._score_search_result(
                    q_term, canonical_title, canonical_desc, poi_name=poi_name
                )
                pairs.append((score, canonical_title, canonical_url))

            pairs.sort(key=lambda x: x[0], reverse=True)

            for score, canonical_title, canonical_url in pairs:
                if score > 0.2:
                    logger.info(
                        "MSG   |<- Wikipedia OpenSearch resolved '%s' -> '%s' (score=%.2f)",
                        q_term,
                        canonical_title,
                        score,
                    )
                    res = await self._try_summary_query(canonical_title, client, headers)
                    if res:
                        return res
                    if canonical_url:
                        return {"source_name": "wikipedia.org", "wikipedia_url": canonical_url}
        except BaseException as exc:
            logger.debug("OpenSearch lookup error for '%s': %s", q_term, exc)
        return None

    async def _try_cirrus_query(
        self,
        q_term: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        poi_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Executes CirrusSearch fallback for a query term with category-aligned re-ranking."""
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(q_term)}&srlimit=5&format=json"
        try:
            s_resp = await client.get(search_url, headers=headers)
            if s_resp.status_code == 200:
                s_results = s_resp.json().get("query", {}).get("search", [])
                ranked_items = sorted(
                    s_results,
                    key=lambda item: self._score_search_result(
                        q_term, item.get("title", ""), item.get("snippet", ""), poi_name=poi_name
                    ),
                    reverse=True,
                )
                for s_item in ranked_items:
                    s_title = s_item.get("title")
                    if s_title and not s_title.lower().startswith("list of "):
                        score = self._score_search_result(
                            q_term, s_title, s_item.get("snippet", ""), poi_name=poi_name
                        )
                        if score > 0.2:
                            logger.info(
                                "MSG   |<- CirrusSearch resolved '%s' -> '%s' (score=%.2f)",
                                q_term,
                                s_title,
                                score,
                            )
                            res = await self._try_summary_query(s_title, client, headers)
                            if res:
                                return res
        except BaseException as exc:
            logger.debug("CirrusSearch lookup error for '%s': %s", q_term, exc)
        return None

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        force_refresh: bool = False,
        poi_name: str | None = None,
    ) -> dict[str, Any]:
        """Queries Wikipedia REST summary API, OpenSearch, CirrusSearch, and Wikidata claims."""
        article_title = query_title
        if source_url and "wikipedia.org/wiki/" in source_url:
            path = urlparse(source_url).path
            article_title = path.split("/wiki/")[-1].replace("_", " ")

        if not article_title:
            return {}

        effective_poi_name = poi_name or (query_title.split(",")[0] if "," in query_title else None)
        candidate_queries = self._generate_candidate_queries(article_title)
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=3.0)
            should_close = True

        try:
            for q_term in candidate_queries:
                summary_res = await self._try_summary_query(q_term, client, headers)
                if summary_res:
                    return summary_res

            for q_term in candidate_queries:
                opensearch_res = await self._try_opensearch_query(
                    q_term, client, headers, poi_name=effective_poi_name
                )
                if opensearch_res:
                    return opensearch_res

            for q_term in candidate_queries:
                gen_search_res = await self._try_generator_search_query(
                    q_term, client, headers, poi_name=effective_poi_name
                )
                if gen_search_res:
                    return gen_search_res

            for q_term in candidate_queries[:2]:
                cirrus_res = await self._try_cirrus_query(
                    q_term, client, headers, poi_name=effective_poi_name
                )
                if cirrus_res:
                    return cirrus_res

            # Fallback to direct Wikidata knowledge search (elevates POIs like "Beaser Garden Maze")
            wd_res = await self._wikidata.augment(
                article_title, source_url=source_url, client=client, poi_name=effective_poi_name
            )
            if wd_res:
                return wd_res
        except BaseException as exc:
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
            "wikibase_item": data.get("wikibase_item"),
        }

        coords = data.get("coordinates")
        if coords:
            result["latitude"] = coords.get("lat")
            result["longitude"] = coords.get("lon")

        hero_url = (data.get("originalimage") or {}).get("source") or (
            data.get("thumbnail") or {}
        ).get("source")
        if hero_url:
            result["hero_image_url"] = hero_url

        return result

    async def _enrich_wikidata_claims(
        self,
        wikibase_item: str,
        parsed_result: dict[str, Any],
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> None:
        """Queries Wikidata claims P856 (official website) and P18 (hero image)."""
        # P856 Official Website
        try:
            wikidata_url = f"https://www.wikidata.org/w/api.php?action=wbgetclaims&entity={wikibase_item}&property=P856&format=json"
            wr = await client.get(wikidata_url, headers=headers)
            if wr.status_code == 200:
                claims = wr.json().get("claims", {}).get("P856", [])
                if claims:
                    official = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                    if isinstance(official, str) and official.startswith("http"):
                        parsed_result["official_website_url"] = official
                        logger.info(
                            "MSG   |<- Found official website via Wikidata P856: %s", official
                        )
        except BaseException as exc:
            logger.debug("Wikidata P856 lookup failed: %s", exc)

        # P18 Image (if hero image still absent)
        if not parsed_result.get("hero_image_url"):
            try:
                wikidata_img_url = f"https://www.wikidata.org/w/api.php?action=wbgetclaims&entity={wikibase_item}&property=P18&format=json"
                wr = await client.get(wikidata_img_url, headers=headers)
                if wr.status_code == 200:
                    img_claims = wr.json().get("claims", {}).get("P18", [])
                    if img_claims:
                        img_filename = (
                            img_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                        )
                        if isinstance(img_filename, str) and img_filename:
                            parsed_result["hero_image_url"] = (
                                f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(img_filename)}"
                            )
                            logger.info(
                                "MSG   |<- Found hero image via Wikidata P18: %s",
                                parsed_result["hero_image_url"],
                            )
            except BaseException as exc:
                logger.debug("Wikidata P18 lookup failed: %s", exc)

    @staticmethod
    def _add_related_website(parsed_result: dict[str, Any], name: str, url: str) -> None:
        clean = canonicalize_url(url)
        if not clean or not clean.startswith("http"):
            return
        if is_unwanted_website_url(clean, name):
            return
        if "related_websites" not in parsed_result:
            parsed_result["related_websites"] = []
        if (
            name == "Hillman Wonders"
            or "hillmanwonders.com" in clean.lower()
            or "hillmanswonders.com" in clean.lower()
        ):
            name = "Hillman Wonders"
            parsed_u = urlparse(clean)
            p = parsed_u.path.lower()
            if not p or p in ("", "/", "/index.html", "/index.htm"):
                clean = "https://www.hillmanswonders.com/top-1000-sites.html"
            elif not clean.startswith("https://www.hillmanswonders.com/"):
                clean = f"https://www.hillmanswonders.com{parsed_u.path}"
            clean = canonicalize_url(clean)

        key = clean.lower()
        if not any(
            canonicalize_url(r.get("url", "")).lower() == key
            for r in parsed_result["related_websites"]
        ):
            parsed_result["related_websites"].append({"name": name, "url": clean})

    async def _enrich_from_extlinks(
        self,
        title: str,
        parsed_result: dict[str, Any],
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> None:
        """Discovers official website and related travel websites from Wikipedia external links."""
        excluded_domains = [
            "wikidata",
            "wikipedia",
            "wikimedia",
            "imdb",
            "worldoftanks",
            "facebook",
            "twitter",
            "x.com",
            "instagram",
            "youtube",
            "yelp",
            "google.",
            "archive.org",
            "geohack",
            "britannica",
            "openstreetmap",
            "osm.org",
            "bing.com/maps",
            "maps.apple",
        ]
        try:
            api_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extlinks&titles={quote(title.replace(' ', '_'))}&ellimit=50&format=json"
            r = await client.get(api_url, headers=headers)
            if r.status_code != 200:
                return
            pages = r.json().get("query", {}).get("pages", {})
            user_domains = self._valid_domains or []
            for page in pages.values():
                for link_obj in page.get("extlinks", []):
                    link = link_obj.get("*", "")
                    if not link or not link.startswith("http") or is_map_service_url(link):
                        continue

                    # 1. Official website detection
                    if not parsed_result.get("official_website_url"):
                        clean_lower = title.lower().replace(" ", "").replace("castle", "")
                        has_kw = any(
                            kw in link.lower()
                            for kw in ["official", "homepage", clean_lower, "burg-eltz"]
                        )
                        if has_kw and not any(bad in link.lower() for bad in excluded_domains):
                            parsed_result["official_website_url"] = link
                            self._add_related_website(parsed_result, "Official Website", link)
                            logger.info("MSG   |<- Found official website: %s", link)

                    # 2. Known travel authority & user-preferred domains
                    link_lower = link.lower()
                    for dom, name in KNOWN_DOMAIN_NAMES.items():
                        if dom in link_lower:
                            self._add_related_website(parsed_result, name, link)

                    for u_dom in user_domains:
                        if u_dom.lower() in link_lower:
                            site_name = KNOWN_DOMAIN_NAMES.get(
                                u_dom.lower(), u_dom.split(".")[0].capitalize()
                            )
                            self._add_related_website(parsed_result, site_name, link)
        except BaseException as exc:
            logger.debug("External links lookup failed: %s", exc)

    async def _enrich_official_website(
        self,
        title: str,
        parsed_result: dict[str, Any],
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> None:
        """Discovers the official website, related websites, and hero image from Wikidata and Wikipedia."""
        if "related_websites" not in parsed_result:
            parsed_result["related_websites"] = []

        if parsed_result.get("wikipedia_url"):
            parsed_result["wikipedia_url"] = canonicalize_url(parsed_result["wikipedia_url"])
            self._add_related_website(parsed_result, "Wikipedia", parsed_result["wikipedia_url"])

        wikibase_item = parsed_result.get("wikibase_item")
        if wikibase_item:
            wd_details = await self._wikidata.fetch_entity_details(
                wikibase_item, client, headers, query_hint=title
            )
            if wd_details:
                if not parsed_result.get("official_website_url") and wd_details.get(
                    "official_website_url"
                ):
                    parsed_result["official_website_url"] = canonicalize_url(wd_details["official_website_url"])
                if not parsed_result.get("hero_image_url") and wd_details.get("hero_image_url"):
                    parsed_result["hero_image_url"] = wd_details["hero_image_url"]
                if not parsed_result.get("latitude") and wd_details.get("latitude"):
                    parsed_result["latitude"] = wd_details["latitude"]
                    parsed_result["longitude"] = wd_details["longitude"]
                for site in wd_details.get("related_websites", []):
                    self._add_related_website(parsed_result, site["name"], site["url"])
            else:
                await self._enrich_wikidata_claims(wikibase_item, parsed_result, client, headers)

        if parsed_result.get("official_website_url"):
            parsed_result["official_website_url"] = canonicalize_url(parsed_result["official_website_url"])
            self._add_related_website(
                parsed_result, "Official Website", parsed_result["official_website_url"]
            )

        await self._enrich_from_extlinks(title, parsed_result, client, headers)

        # Ensure hero image scraper inspects <meta property="og:image"> and <meta name="twitter:image">
        # headers from official website before falling back to empty
        official_url = parsed_result.get("official_website_url")
        if official_url and not parsed_result.get("hero_image_url"):
            site_hero = await scrape_website_hero_image(
                official_url, client=client, headers=headers
            )
            if site_hero:
                parsed_result["hero_image_url"] = site_hero


class TripAdvisorAdapter(SecondarySourceAdapter):
    """Adapter for TripAdvisor destination data."""

    def __init__(
        self,
        valid_domains: list[str] | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        super().__init__(valid_domains=valid_domains, cache_repo=cache_repo)

    @property
    def domain(self) -> str:
        return "tripadvisor.com"

    async def _search_tripadvisor_url(
        self,
        query: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        poi_name: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> str | None:
        """Finds the TripAdvisor attraction review URL using search engine index fallbacks."""
        import base64
        from urllib.parse import parse_qs, urlparse

        clean_name = (poi_name or query).strip()
        c = (city or "").strip()
        co = (country or "").strip()

        search_terms: list[str] = []

        def _add(*toks: str):
            p = [clean_name]
            for t in toks:
                if t and t.lower() not in clean_name.lower():
                    p.append(t)
            q = " ".join(p).strip()
            if q and q not in search_terms:
                search_terms.append(q)

        # 1. Primary targeted: Name + City (e.g. "Zwinger Dresden")
        if c:
            _add(c)
        # 2. Name alone (e.g. "The Dresden Zwinger")
        _add()
        # 3. Name + City + Country
        if c and co:
            _add(c, co)
        # 4. Raw query if distinct
        if query.strip() not in search_terms:
            search_terms.append(query.strip())

        for term in search_terms:
            # 1. Try Bing Search index
            try:
                bing_url = f"https://www.bing.com/search?q=site%3Atripadvisor.com+{quote(term)}"
                resp = await client.get(bing_url, headers=headers, timeout=5.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for h2 in soup.find_all("h2"):
                        a = h2.find("a")
                        if not a or not a.get("href"):
                            continue
                        href = a["href"]
                        target_url = None
                        if "bing.com/ck/a" in href and "u=" in href:
                            qs = parse_qs(urlparse(href).query)
                            u_val = qs.get("u", [""])[0]
                            if u_val.startswith("a1"):
                                b64 = u_val[2:]
                                b64 += "=" * ((4 - len(b64) % 4) % 4)
                                try:
                                    decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                                    if "tripadvisor.com/Attraction_Review" in decoded:
                                        target_url = decoded
                                except Exception:
                                    pass
                        elif "tripadvisor.com/Attraction_Review" in href:
                            target_url = href

                        if target_url:
                            clean = re.sub(r"-or\d+-", "-", target_url)
                            clean = re.sub(r"ShowUserReviews-", "Attraction_Review-", clean)
                            return canonicalize_url(clean)
            except Exception as exc:
                logger.debug("TripAdvisor Bing search error for '%s': %s", term, exc)

            # 2. Try DuckDuckGo HTML fallback
            try:
                ddg_url = "https://html.duckduckgo.com/html/"
                data = {"q": f"site:tripadvisor.com {term}"}
                resp = await client.post(ddg_url, data=data, headers=headers, timeout=5.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_="result__url"):
                        href = a.get("href", "").strip()
                        if "tripadvisor.com/Attraction_Review" in href:
                            clean = re.sub(r"-or\d+-", "-", href)
                            clean = re.sub(r"ShowUserReviews-", "Attraction_Review-", clean)
                            return canonicalize_url(clean)
            except Exception as exc:
                logger.debug("TripAdvisor DuckDuckGo search error for '%s': %s", term, exc)

        return None

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        force_refresh: bool = False,
        poi_name: str | None = None,
        location: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        """Extracts TripAdvisor enrichment data."""
        if not query_title and not source_url:
            return {}

        result: dict[str, Any] = {
            "source_name": "tripadvisor.com",
            "estimated_duration_hours": 2.5,
        }

        if source_url and "tripadvisor.com" in source_url:
            clean_url = canonicalize_url(source_url)
            result["official_website_url"] = clean_url
            result["tripadvisor_url"] = clean_url
            result["related_websites"] = [{"name": "Tripadvisor", "url": clean_url}]
            return result

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=6.0)
            should_close = True

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            effective_city = city
            effective_country = country
            if location and not effective_city:
                parts = [p.strip() for p in location.split(",") if p.strip()]
                if parts:
                    effective_city = parts[0]
                    if len(parts) > 1:
                        effective_country = parts[-1]

            search_query = query_title
            if location and location.strip() and location.strip().lower() not in search_query.lower():
                search_query = f"{search_query} {location.strip()}"

            ta_url = await self._search_tripadvisor_url(
                search_query,
                client=client,
                headers=headers,
                poi_name=poi_name,
                city=effective_city,
                country=effective_country,
            )
            if ta_url:
                result["official_website_url"] = ta_url
                result["tripadvisor_url"] = ta_url
                result["related_websites"] = [{"name": "Tripadvisor", "url": ta_url}]
                logger.info("MSG   |<- Found TripAdvisor attraction: %s", ta_url)
        except Exception as exc:
            logger.debug("TripAdvisor lookup failed for '%s': %s", query_title, exc)
        finally:
            if should_close:
                await client.aclose()

        return result


class HillmanWondersAdapter(SecondarySourceAdapter):
    """Adapter for Hillman Wonders of the World (REQ-EXT-019)."""

    _index_cache: dict[str, str] | None = None
    _top_1000_names: set[str] | None = None

    def __init__(
        self,
        valid_domains: list[str] | None = None,
        cache_repo: IExternalEnrichmentCacheRepository | None = None,
    ) -> None:
        super().__init__(valid_domains=valid_domains, cache_repo=cache_repo)

    @property
    def domain(self) -> str:
        return "hillmanwonders.com"

    @classmethod
    async def _ensure_index_loaded(cls, client: httpx.AsyncClient, headers: dict[str, str]) -> None:
        if cls._index_cache is not None and cls._top_1000_names is not None:
            return
        cls._index_cache = {}
        cls._top_1000_names = set()
        index_url = "https://www.hillmanswonders.com/top-1000-sites.html"
        req_headers = dict(headers)
        req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        try:
            logger.info("MSG   |-> Loading Hillman Wonders index from %s", index_url)
            resp = await client.get(index_url, headers=req_headers, timeout=6.0)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    text = a.get_text().strip()
                    if href.endswith(".html") and not href.startswith("http") and not href.startswith("top-") and not href.startswith("index"):
                        subpage = href.lstrip("/")
                        full_url = f"https://www.hillmanswonders.com/{subpage}"
                        clean_text = text.lower()
                        if clean_text:
                            cls._index_cache[clean_text] = full_url
                        no_paren = re.sub(r"\s*\([^)]*\)", "", clean_text).strip()
                        if no_paren:
                            cls._index_cache[no_paren] = full_url
                for el in soup.find_all(["li", "p", "td", "a"]):
                    t = el.get_text().strip().lower()
                    if 3 <= len(t) <= 80:
                        no_paren = re.sub(r"\s*\([^)]*\)", "", t).strip()
                        if no_paren:
                            cls._top_1000_names.add(no_paren)
            logger.info(
                "MSG   |<- Loaded %d Hillman Wonders subpages and %d names",
                len(cls._index_cache),
                len(cls._top_1000_names),
            )
        except Exception as exc:
            logger.debug("Hillman Wonders index fetch failed: %s", exc)

    def _match_wonder(self, poi_name: str) -> tuple[str | None, str | None]:
        """Returns (wonder_url, matched_name) or (None, None)."""
        clean_name = poi_name.strip().lower()
        no_paren = re.sub(r"\s*\([^)]*\)", "", clean_name).strip()

        # 1. Exact match in subpage cache
        if clean_name in (self._index_cache or {}):
            return self._index_cache[clean_name], poi_name
        if no_paren in (self._index_cache or {}):
            return self._index_cache[no_paren], no_paren

        # 2. Substring/token match in subpage cache
        for name, url in (self._index_cache or {}).items():
            if no_paren == name or no_paren in name or name in no_paren:
                return url, name

        # 3. Match in top 1000 names (without dedicated subpage)
        top_url = "https://www.hillmanswonders.com/top-1000-sites.html"
        if no_paren in (self._top_1000_names or set()):
            return top_url, no_paren
        for name in (self._top_1000_names or set()):
            if no_paren == name or (len(no_paren) >= 4 and no_paren in name):
                return top_url, name

        return None, None

    async def augment(
        self,
        query_title: str,
        source_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Looks up a POI on Hillman Wonders and fetches its detail page description."""
        if not query_title and not source_url:
            return {}

        target_name = query_title.strip()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=4.0)
            should_close = True

        try:
            await self._ensure_index_loaded(client, headers)
            wonder_url, matched_name = self._match_wonder(target_name)
            if not wonder_url:
                return {}

            desc: str | None = None
            if wonder_url.endswith(".html") and not wonder_url.endswith("top-1000-sites.html"):
                try:
                    resp = await client.get(wonder_url, headers=headers, timeout=4.0)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        full_text = soup.get_text("\n")
                        m = re.search(
                            r"is special\s*\n+([\s\S]+?)(?:\n\s*\n|Tips|\n\s*Location|\Z)",
                            full_text,
                            re.IGNORECASE,
                        )
                        if m:
                            clean_desc = re.sub(r"\s+", " ", m.group(1)).strip()
                            if len(clean_desc) > 25:
                                desc = clean_desc
                        if not desc:
                            desc = extract_meta_description(resp.text)
                except Exception as exc:
                    logger.debug("Failed to scrape Hillman Wonder page '%s': %s", wonder_url, exc)

            res: dict[str, Any] = {
                "source_name": "hillmanwonders.com",
                "wonder_name": matched_name or target_name,
                "url": wonder_url,
                "related_websites": [{"name": "Hillman Wonders", "url": wonder_url}],
            }
            if desc:
                res["description"] = desc
                res["secondary_extracts"] = [
                    {
                        "source": "Hillman Wonders",
                        "url": wonder_url,
                        "text": desc,
                    }
                ]
            return res
        except Exception as exc:
            logger.debug("Hillman Wonders augment error for '%s': %s", target_name, exc)
            return {}
        finally:
            if should_close:
                await client.aclose()
