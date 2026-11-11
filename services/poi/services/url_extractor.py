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

"""Webpage and geohack coordinate extraction engine.

Extracts coordinates and location information from:
1. GeoHack URLs and links (e.g. Wikipedia coordinate links)
2. Google Maps URLs and embedded map links
3. HTML metadata (geo.position, ICBM, place:location:latitude/longitude)
4. Schema.org JSON-LD GeoCoordinates
5. Microformats (class="geo", class="geo-dec", class="latitude", etc.)
6. TripAdvisor and Wikipedia URL slugs with fallback forward geocoding
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from typing import Any

import httpx
from bs4 import BeautifulSoup
from vistarae_core.schemas.poi import ExtractUrlCoordinatesResponse

from services.poi.services.geocode_service import ReverseGeocodeService
from services.poi.services.geocoding_service import GeocodingService

logger = logging.getLogger("vistarae.geocoding.url_extractor")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
        "VistaraeTravelEngine/1.0 (https://vistarae.com; contact@vistarae.com)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def clean_url(url: str) -> str:
    """Strips browser text fragments like #:~:text=... from URL."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        clean_frag = re.sub(r":~:text=.*$", "", parsed.fragment)
        return urllib.parse.urlunparse(parsed._replace(fragment=clean_frag))
    except Exception:
        return url.strip()


def parse_geohack_params(params: str) -> tuple[float, float] | None:
    """Parses Wikipedia GeoHack params string into (lat, lng) decimal degrees.

    Supports:
    - Decimal degrees: 30.42188_N_108.18389_E or 30.42188;108.18389 or 30.42188_-108.18389
    - Deg + Min: 30_25.5_N_108_11.5_E
    - Deg + Min + Sec: 51_30_02_N_0_07_29_W
    """
    if not params:
        return None

    # Check directional parameters first (_N_, _S_, _E_, _W_)
    p = params.split("_")
    ns_idx = next((i for i, part in enumerate(p) if part.upper() in ("N", "S")), -1)
    ew_idx = next((i for i, part in enumerate(p) if part.upper() in ("E", "W")), -1)

    if ns_idx != -1 and ew_idx != -1 and ns_idx < ew_idx:
        try:
            lat_parts = [float(x) for x in p[:ns_idx] if x]
            lat_sign = 1.0 if p[ns_idx].upper() == "N" else -1.0
            if len(lat_parts) == 1:
                lat = lat_parts[0] * lat_sign
            elif len(lat_parts) == 2:
                lat = (lat_parts[0] + lat_parts[1] / 60.0) * lat_sign
            elif len(lat_parts) >= 3:
                lat = (lat_parts[0] + lat_parts[1] / 60.0 + lat_parts[2] / 3600.0) * lat_sign
            else:
                return None

            lon_parts = [float(x) for x in p[ns_idx + 1 : ew_idx] if x]
            lon_sign = 1.0 if p[ew_idx].upper() == "E" else -1.0
            if len(lon_parts) == 1:
                lng = lon_parts[0] * lon_sign
            elif len(lon_parts) == 2:
                lng = (lon_parts[0] + lon_parts[1] / 60.0) * lon_sign
            elif len(lon_parts) >= 3:
                lng = (lon_parts[0] + lon_parts[1] / 60.0 + lon_parts[2] / 3600.0) * lon_sign
            else:
                return None

            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
        except (ValueError, IndexError):
            pass

    # Handle decimal separated by semicolon or simple underscore (without N/S/E/W)
    m = re.match(r"^(-?\d+(?:\.\d+)?)[;_](-?\d+(?:\.\d+)?)(?:_|$)", params)
    if m:
        try:
            lat = float(m.group(1))
            lng = float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng
        except ValueError:
            pass

    return None


def parse_geohack_url(url: str) -> tuple[float, float, str | None] | None:
    """Parses a GeoHack URL, returning (lat, lng, pagename)."""
    try:
        parsed = urllib.parse.urlparse(url)
        if "geohack" not in parsed.netloc and "geohack" not in parsed.path:
            return None
        qs = urllib.parse.parse_qs(parsed.query)
        pagename = qs.get("pagename", [None])[0]
        params = qs.get("params", [None])[0]
        if params:
            coords = parse_geohack_params(params)
            if coords:
                name = urllib.parse.unquote(pagename).replace("_", " ") if pagename else None
                return coords[0], coords[1], name
    except Exception as exc:
        logger.debug("Failed parsing geohack URL '%s': %s", url, exc)
    return None


def parse_google_maps_url_py(url: str) -> tuple[float, float, str | None] | None:
    """Extracts coordinates and place name from a Google Maps URL."""
    try:
        # 1. Place name
        place_match = re.search(r"/maps/place/([^/@?]+)", url, re.IGNORECASE)
        place_name = None
        if place_match:
            raw = urllib.parse.unquote(place_match.group(1).replace("+", " "))
            if not re.match(r"^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$", raw.strip()):
                place_name = raw.strip()

        # 2. Pin data parameter (!3d<lat>!4d<lng>)
        pin = re.search(r"!3d(-?\d+(?:\.\d+)?).*?!4d(-?\d+(?:\.\d+)?)", url)
        if pin:
            lat, lng = float(pin.group(1)), float(pin.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng, place_name

        # 3. Viewport center (@<lat>,<lng>)
        at_m = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", url)
        if at_m:
            lat, lng = float(at_m.group(1)), float(at_m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng, place_name

        # 4. Query parameter q=<lat>,<lng> or ll=<lat>,<lng>
        q_m = re.search(
            r"[?&](?:q|query|ll|sll|center|destination|daddr)=(?:loc:)?(-?\d+(?:\.\d+)?)(?:%20|\+|,)+(-?\d+(?:\.\d+)?)",
            url,
            re.IGNORECASE,
        )
        if q_m:
            lat, lng = float(q_m.group(1)), float(q_m.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng, place_name
    except Exception as exc:
        logger.debug("Failed parsing google maps url '%s': %s", url, exc)
    return None


def extract_tripadvisor_slug(url: str) -> str | None:
    """Extracts human-readable attraction and locality from TripAdvisor review URL."""
    m = re.search(
        r"(?:Attraction|Restaurant|Hotel|Tourism|VacationRental)_Review-g\d+-d\d+-Reviews-(.+?)\.html",
        url,
        re.IGNORECASE,
    )
    if m:
        slug = m.group(1)
        # Convert "Shi_Bao_Zhai-Zhong_County" -> "Shi Bao Zhai, Zhong County"
        parts = [p.replace("_", " ").strip() for p in slug.split("-") if p.strip()]
        if parts:
            return ", ".join(parts)
    return None


class UrlCoordinateExtractor:
    """High-level service coordinating webpage body coordinate extraction and address enrichment."""

    def __init__(
        self,
        reverse_geocode_service: ReverseGeocodeService,
        geocoding_service: GeocodingService | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._reverse_service = reverse_geocode_service
        self._geocoding_service = geocoding_service
        self._client = http_client
        self._timeout_seconds = timeout_seconds

    async def extract_coordinates_from_url(self, raw_url: str) -> ExtractUrlCoordinatesResponse:
        """Extracts coordinates and enriched address from a webpage or map/geohack URL."""
        url = clean_url(raw_url)
        if not url.startswith(("http://", "https://")):
            return ExtractUrlCoordinatesResponse(
                extraction_source="invalid_url",
            )

        # 1. Direct GeoHack URL check
        gh = parse_geohack_url(url)
        if gh:
            return await self._build_enriched_response(
                lat=gh[0],
                lng=gh[1],
                place_name=gh[2],
                source="geohack_url",
            )

        # 2. Direct Google Maps URL check
        gmaps = parse_google_maps_url_py(url)
        if gmaps:
            return await self._build_enriched_response(
                lat=gmaps[0],
                lng=gmaps[1],
                place_name=gmaps[2],
                source="google_maps_url",
            )

        # 3. Check TripAdvisor specific slug for fast forward geocode if fetching fails or is blocked
        ta_slug = extract_tripadvisor_slug(url)

        # 4. Fetch the webpage content
        html_text = ""
        fetch_succeeded = False
        try:
            if self._client:
                resp = await self._client.get(
                    url,
                    headers=REQUEST_HEADERS,
                    follow_redirects=True,
                    timeout=self._timeout_seconds,
                )
                if resp.status_code == 200:
                    html_text = resp.text
                    fetch_succeeded = True
            else:
                async with httpx.AsyncClient(
                    headers=REQUEST_HEADERS,
                    follow_redirects=True,
                    timeout=self._timeout_seconds,
                ) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        html_text = resp.text
                        fetch_succeeded = True
        except Exception as exc:
            logger.warning("MSG   |<- Webpage fetch failed for '%s': %s", url, exc)

        # 5. If HTML was retrieved, parse with BeautifulSoup
        extracted_lat: float | None = None
        extracted_lng: float | None = None
        extracted_name: str | None = None
        extraction_source = "unknown"

        if fetch_succeeded and html_text:
            soup = BeautifulSoup(html_text, "html.parser")

            # Extract title / place name
            title_tag = soup.find("title")
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                extracted_name = og_title["content"].strip()
            elif title_tag and title_tag.string:
                raw_t = title_tag.string.strip()
                # Clean suffixes like " - Wikipedia", " | TripAdvisor", etc.
                cleaned_t = re.split(r"\s+[-–|]\s+", raw_t)[0].strip()
                extracted_name = cleaned_t

            # A. GeoHack Link in page (common in Wikipedia)
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "geohack" in href:
                    gh_link_res = parse_geohack_url(href)
                    if gh_link_res:
                        extracted_lat, extracted_lng = gh_link_res[0], gh_link_res[1]
                        extracted_name = extracted_name or gh_link_res[2]
                        extraction_source = "geohack_link"
                        break

            # B. Google Maps link in page
            if extracted_lat is None:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "google.com/maps" in href or "maps.google." in href:
                        gm_res = parse_google_maps_url_py(href)
                        if gm_res:
                            extracted_lat, extracted_lng = gm_res[0], gm_res[1]
                            extracted_name = extracted_name or gm_res[2]
                            extraction_source = "google_maps_link"
                            break

            # C. Microformat <span class="geo">lat; lng</span>
            if extracted_lat is None:
                geo_span = soup.find(class_="geo")
                if geo_span and geo_span.text:
                    m_geo = re.search(r"(-?\d+(?:\.\d+)?)\s*[;,]\s*(-?\d+(?:\.\d+)?)", geo_span.text)
                    if m_geo:
                        extracted_lat = float(m_geo.group(1))
                        extracted_lng = float(m_geo.group(2))
                        extraction_source = "microformat_geo"

            # D. Schema.org JSON-LD GeoCoordinates
            if extracted_lat is None:
                for s in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(s.string or "{}")
                        items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                        for item in items:
                            if isinstance(item, dict):
                                geo = item.get("geo")
                                if isinstance(geo, dict):
                                    g_lat = geo.get("latitude")
                                    g_lng = geo.get("longitude")
                                    if g_lat is not None and g_lng is not None:
                                        extracted_lat = float(g_lat)
                                        extracted_lng = float(g_lng)
                                        extracted_name = extracted_name or item.get("name")
                                        extraction_source = "json_ld"
                                        break
                                graph = item.get("@graph")
                                if isinstance(graph, list):
                                    for g_node in graph:
                                        if isinstance(g_node, dict) and "geo" in g_node:
                                            g_lat = g_node["geo"].get("latitude")
                                            g_lng = g_node["geo"].get("longitude")
                                            if g_lat is not None and g_lng is not None:
                                                extracted_lat = float(g_lat)
                                                extracted_lng = float(g_lng)
                                                extracted_name = extracted_name or g_node.get("name")
                                                extraction_source = "json_ld"
                                                break
                    except Exception:
                        pass
                    if extracted_lat is not None:
                        break

            # E. Meta tags (geo.position, ICBM, place:location:latitude)
            if extracted_lat is None:
                for meta in soup.find_all("meta"):
                    prop = (meta.get("property") or meta.get("name") or "").lower()
                    content = meta.get("content") or ""
                    if prop in ("geo.position", "icbm"):
                        m_pos = re.search(r"(-?\d+(?:\.\d+)?)\s*[;,]\s*(-?\d+(?:\.\d+)?)", content)
                        if m_pos:
                            extracted_lat = float(m_pos.group(1))
                            extracted_lng = float(m_pos.group(2))
                            extraction_source = f"meta_{prop}"
                            break

            # F. Page body regex fallback
            if extracted_lat is None:
                m_lat = re.search(r'["\'](?:latitude|lat)["\']\s*:\s*(-?\d+\.\d+)', html_text)
                m_lng = re.search(r'["\'](?:longitude|lng)["\']\s*:\s*(-?\d+\.\d+)', html_text)
                if m_lat and m_lng:
                    lat_cand = float(m_lat.group(1))
                    lng_cand = float(m_lng.group(1))
                    if -90 <= lat_cand <= 90 and -180 <= lng_cand <= 180 and not (lat_cand == 0 and lng_cand == 0):
                        extracted_lat = lat_cand
                        extracted_lng = lng_cand
                        extraction_source = "page_body_regex"

        # 6. Fallback forward geocoding if coordinates not directly in HTML or fetch failed
        if (extracted_lat is None or extracted_lng is None) and self._geocoding_service:
            search_query = ta_slug or extracted_name
            if not search_query and "/wiki/" in url:
                wiki_slug = url.split("/wiki/")[-1].split("?")[0].split("#")[0]
                search_query = urllib.parse.unquote(wiki_slug).replace("_", " ")

            if search_query:
                try:
                    f_lat, f_lon, addrs, _ = await self._geocoding_service.geocode(search_query)
                    if f_lat is not None and f_lon is not None:
                        extracted_lat = f_lat
                        extracted_lng = f_lon
                        extracted_name = extracted_name or search_query
                        extraction_source = "fallback_geocoded"
                except Exception as exc:
                    logger.debug("Fallback geocoding failed for '%s': %s", search_query, exc)

        # 7. If coordinates were successfully resolved, enrich with reverse geocoding
        if extracted_lat is not None and extracted_lng is not None:
            return await self._build_enriched_response(
                lat=extracted_lat,
                lng=extracted_lng,
                place_name=extracted_name or ta_slug,
                source=extraction_source,
            )

        return ExtractUrlCoordinatesResponse(
            place_name=extracted_name or ta_slug,
            extraction_source="no_coordinates_found",
        )

    async def _build_enriched_response(
        self,
        lat: float,
        lng: float,
        place_name: str | None,
        source: str,
    ) -> ExtractUrlCoordinatesResponse:
        """Enriches coordinates with reverse geocoded address fields."""
        street = None
        city = None
        state_province = None
        country = None
        postal_code = None
        country_code = None

        try:
            rev = await self._reverse_service.reverse_geocode(lat=lat, lng=lng)
            street = rev.street
            city = rev.city or rev.locality
            state_province = rev.state_province or rev.admin_level_1
            country = rev.country
            postal_code = rev.postal_code
            country_code = rev.country_code
        except Exception as exc:
            logger.debug("Failed reverse geocoding (%s, %s): %s", lat, lng, exc)

        return ExtractUrlCoordinatesResponse(
            latitude=lat,
            longitude=lng,
            place_name=place_name,
            extraction_source=source,
            street=street,
            city=city,
            state_province=state_province,
            country=country,
            postal_code=postal_code,
            country_code=country_code,
        )
