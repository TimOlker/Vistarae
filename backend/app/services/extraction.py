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

import asyncio
import json
import logging
import re
import shutil
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from app.config import settings
from app.middleware.telemetry import egress_span
from app.schemas.extraction import ExtractAndCheckRequest, POIExtractionCandidate

logger = logging.getLogger("vistarae.extraction")

BLACKLISTED_OFFICIAL_WEBSITE_DOMAINS = (
    "google.",
    "bing.com",
    "yahoo.com",
    "duckduckgo.com",
    "baidu.com",
    "yandex.com",
    "tripadvisor.",
    "roadsideamerica.com",
    "locationscout.net",
    "shothotspot.com",
    "atlasobscura.com",
    "wikipedia.org",
    "wikimedia.org",
    "yelp.com",
    "facebook.com",
    "instagram.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "pinterest.com",
    "threads.net",
    "youtube.com",
)


def sanitize_official_website(url: str | None) -> str | None:
    """Validates and sanitizes official website URL, stripping search engine and aggregator links."""
    if not url or not isinstance(url, str):
        return None
    url_str = url.strip()
    if not url_str:
        return None

    try:
        parsed = urlparse(url_str)
        # Unwrap Google redirect URLs (/url?q=... or /url?url=...)
        if "google." in parsed.netloc and parsed.path.startswith("/url"):
            qs = parse_qs(parsed.query)
            target = qs.get("q", [None])[0] or qs.get("url", [None])[0]
            if target and (target.startswith("http://") or target.startswith("https://")):
                url_str = unquote(target).strip()
                parsed = urlparse(url_str)

        if not parsed.scheme or parsed.scheme.lower() not in ("http", "https"):
            return None

        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]

        for b_domain in BLACKLISTED_OFFICIAL_WEBSITE_DOMAINS:
            if b_domain in netloc:
                return None

        return url_str
    except Exception:
        return None


MAP_OR_PLACEHOLDER_IMAGE_PATTERNS = (
    "staticmap",
    "/static_map",
    "maps.google.com/maps/api",
    "maps.googleapis.com/maps/api",
    "streetviewpixels",
    "maps.gstatic.com",
    "google.com/maps/vt",
    "tile.openstreetmap.org",
    "tile.openstreetmap",
    "tile.mapbox",
    "data:image/gif",
    "data:image/svg",
    "default_avatar",
    "branding/googlelogo",
    "cleardot.gif",
    "grey_header_tile",
    "transparent.png",
    "/tactile/omnibox/",
)


def is_map_or_placeholder_image(url: str | None) -> bool:
    """Detects whether an image URL points to a static map tile, streetview tile, or placeholder icon."""
    if not url or not isinstance(url, str):
        return True
    u = url.strip().lower()
    if not u or not (u.startswith("http://") or u.startswith("https://")):
        return True
    return any(p in u for p in MAP_OR_PLACEHOLDER_IMAGE_PATTERNS)


def sanitize_image_url(url: str | None) -> str | None:
    """Returns None if URL is a static map or placeholder, else clean URL."""
    if is_map_or_placeholder_image(url):
        return None
    return url.strip()


EXTRACTION_SYSTEM_PROMPT = """You are Vistarae's Travel Entity Extractor.
Extract structured Point of Interest (POI) data from the user-selected text, page title, URL, and category.
Focus on identifying scenic overlooks, trails, iconic viewpoints, museums, historic vessels, military sites, natural landmarks, or notable sites.
Generate a deterministic, high-accuracy `search_address_query` suitable for OpenStreetMap Nominatim geocoding.
Ensure IPTC geographic metadata (city, province/state, 2-letter country code) is accurately populated.

For `category_tags`, provide 3-7 comprehensive, relevant lowercase tags reflecting the POI's themes, features, and exhibits:
- Ships, warships, or naval sites: 'ship', 'military', 'museum', 'historic', 'aviation', 'airplane', 'space'
- Parks or outdoor landmarks: 'scenic', 'viewpoint', 'hiking', 'nature', 'monument', 'NPS'
- Cultural or heritage sites: 'historic', 'museum', 'architecture', 'art'
- Food & dining: 'food', 'restaurant', 'wine', 'historic'

CRITICAL: The `description` field MUST contain ONLY narrative description or highlights of the location.
DO NOT include prefixes like 'Point of Interest:', coordinates, website URLs, phone numbers, or addresses in the description.

Visit Details (physical_effort, indoor_outdoor, booking_lead_time, estimated_duration, cost_tier, best_time_to_visit):
Do best effort to extract these based on site text, reviews, or social media context.
If no reliable information is available or can be reasonably inferred from the content, leave these fields as null/blank.
"""


def parse_atlas_obscura_html(html: str, url: str) -> dict:
    """Parses Atlas Obscura HTML extracting JSON-LD schema, DOM coordinates, tags, and visit details."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Search for Place / TouristAttraction in application/ld+json
    place_json = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "{}")
            types = data.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if any(
                t
                in (
                    "Place",
                    "TouristAttraction",
                    "Restaurant",
                    "LandmarksOrHistoricalBuildings",
                    "CivicStructure",
                )
                for t in types
            ):
                place_json = data
                break
        except Exception:
            continue

    # Name
    name = (place_json.get("name") or "").strip()
    description = (place_json.get("description") or "").strip()

    # Geo Coordinates
    geo = place_json.get("geo") or {}
    lat = geo.get("latitude")
    lng = geo.get("longitude")
    if lat is not None:
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            lat, lng = None, None

    # Address
    addr = place_json.get("address") or {}
    street = addr.get("streetAddress")
    city = addr.get("addressLocality")
    state = addr.get("addressRegion")
    country = addr.get("addressCountry")
    postal_code = addr.get("postalCode")

    # Website
    same_as = place_json.get("sameAs") or []
    official_website = (
        same_as[0]
        if (isinstance(same_as, list) and same_as)
        else (same_as if isinstance(same_as, str) else None)
    )

    # Image
    image_url = place_json.get("image")
    if isinstance(image_url, list) and image_url:
        image_url = image_url[0]

    # DOM Fallbacks
    if not name:
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)

    if not name and soup.title:
        name = re.sub(r"\s*[-–—|]\s*Atlas Obscura.*$", "", soup.title.get_text(strip=True)).strip()

    # Coordinates fallback from DOM
    if lat is None or lng is None:
        coord_div = soup.find(
            lambda el: (
                el.name in ["div", "span", "p"]
                and re.search(r"^\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*$", el.get_text())
            )
        )
        if coord_div:
            m = re.search(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)", coord_div.get_text())
            if m:
                lat = float(m.group(1))
                lng = float(m.group(2))

    if lat is None or lng is None:
        map_link = soup.find(
            "a", href=lambda h: h and ("maps.google" in h or "google.com/maps" in h)
        )
        if map_link:
            m = re.search(
                r"(?:q|query)=(-?\d+(?:\.\d+)?)(?:%2C|,)(-?\d+(?:\.\d+)?)", map_link.get("href")
            )
            if m:
                lat = float(m.group(1))
                lng = float(m.group(2))

    # Extract tags
    tags = []
    for tag_el in soup.select(
        "a[href*='/categories/'], a[href*='/tags/'], .item-tags a, div.flex.flex-wrap.gap-4 a"
    ):
        t_text = tag_el.get_text(strip=True)
        if t_text and t_text not in tags and len(t_text) < 40:
            tags.append(t_text)

    if not tags:
        rel_tags_h = soup.find(
            lambda el: el.name in ["h2", "h3", "h4"] and "Related Tags" in el.get_text()
        )
        if rel_tags_h:
            container = rel_tags_h.find_next_sibling()
            if container:
                for el in container.find_all(["a", "span", "div"]):
                    t = el.get_text(strip=True)
                    if t and t not in tags and len(t) < 40:
                        tags.append(t)

    # Extract Know Before You Go
    kbyg_text = ""
    kbyg_h = soup.find(
        lambda el: el.name in ["h2", "h3", "h4"] and "Know Before You Go" in el.get_text()
    )
    if kbyg_h:
        sib = kbyg_h.find_next_sibling()
        if sib:
            kbyg_text = sib.get_text(separator=" ", strip=True)

    # Body text
    body_div = soup.find(class_=lambda c: c and ("place-body" in c or "item-body" in c))
    body_text = body_div.get_text(separator=" ", strip=True) if body_div else ""

    # POI Type & Visit details inferencing
    all_context = (f"{name} {' '.join(tags)} {description} {body_text[:500]}").lower()
    is_food = any(
        w in all_context
        for w in ["restaurant", "food", "bar", "wine", "cafe", "bakery", "dining", "creole"]
    )
    poi_type = "food/drink" if is_food else "site to see"

    best_time = None
    cost_tier = None
    booking_lead = None
    environment = "Indoor" if is_food else None
    effort = "paved walk" if is_food else None

    if kbyg_text:
        hours_m = re.search(
            r"((?:Lunch|Dinner|Open|Hours)[^.\n]+(?:\.|\n|$))", kbyg_text, re.IGNORECASE
        )
        if hours_m:
            best_time = hours_m.group(1).strip()
        if "reservation" in kbyg_text.lower():
            booking_lead = "reservations recommended"
        elif "walk-in" in kbyg_text.lower():
            booking_lead = "walk-in ok"
        if any(w in kbyg_text.lower() for w in ["business casual", "fine dining", "upscale"]):
            cost_tier = "$$$"
        elif "free" in kbyg_text.lower() or "no admission" in kbyg_text.lower():
            cost_tier = "Free"

    return {
        "name": name,
        "description": description or (body_text[:300] + "..." if body_text else None),
        "body_text": body_text,
        "latitude": lat,
        "longitude": lng,
        "street_address": street,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "country": country,
        "website": official_website,
        "image_url": image_url,
        "tags": tags,
        "poi_type": poi_type,
        "kbyg_text": kbyg_text,
        "best_time": best_time,
        "cost_tier": cost_tier,
        "booking_lead": booking_lead,
        "environment": environment,
        "effort": effort,
    }


async def fetch_atlas_obscura_page(url: str) -> dict | None:
    """Fetches an Atlas Obscura place page via curl subprocess or httpx and parses structured data."""
    try:
        curl_bin = shutil.which("curl") or shutil.which("curl.exe")
        if not curl_bin:
            logger.warning("curl binary not found. Falling back to httpx.")
            import httpx

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            async with httpx.AsyncClient(
                headers=headers, follow_redirects=True, timeout=10.0
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return parse_atlas_obscura_html(resp.text, url)
                return None

        cmd = [
            curl_bin,
            "-s",
            "-L",
            "-A",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "-H",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        html = stdout.decode("utf-8", errors="ignore")
        if html and ("schema.org" in html or "atlasobscura" in html or "aon-" in html):
            return parse_atlas_obscura_html(html, url)
        return None
    except Exception as e:
        logger.error(f"Error fetching Atlas Obscura URL {url}: {e}")
        return None


def _apply_payload_enrichment(
    cand: POIExtractionCandidate, payload: ExtractAndCheckRequest
) -> None:
    """Applies direct attributes from ExtractAndCheckRequest onto POIExtractionCandidate."""
    if payload.place_name:
        cand.name = payload.place_name
    cand.website_official = sanitize_official_website(cand.website_official)
    sanitized_payload_web = sanitize_official_website(payload.website)
    if sanitized_payload_web and not cand.website_official:
        cand.website_official = sanitized_payload_web
    payload.og_image_url = sanitize_image_url(payload.og_image_url)
    if payload.phone_number and not cand.phone_number:
        cand.phone_number = payload.phone_number
    if payload.city:
        cand.iptc_city = payload.city
    if payload.state:
        cand.iptc_province_state = payload.state
    if payload.country:
        cand.iptc_country_code = payload.country
    if payload.postal_code:
        cand.iptc_zip_code = payload.postal_code
    if payload.category_tags:
        for t in payload.category_tags:
            clean_t = t.lower().strip()
            if clean_t and clean_t not in cand.category_tags:
                cand.category_tags.append(clean_t)
    if payload.category in [
        "photo location",
        "site to see",
        "experience",
        "food/drink",
        "lodging",
        "transit",
    ]:
        cand.poi_type = payload.category
    elif payload.category == "food/drink" or any(
        w in cand.name.lower() for w in ["restaurant", "cafe", "bistro", "bakery"]
    ):
        cand.poi_type = "food/drink"
        if "food" not in cand.category_tags:
            cand.category_tags.append("food")
    elif (
        payload.source_type in ["LocationScout", "ShotHotspot"]
        or "photo location" in cand.category_tags
    ):
        cand.poi_type = "photo location"

    if payload.physical_effort:
        cand.physical_effort = payload.physical_effort
    if payload.booking_lead_time:
        cand.booking_lead_time = payload.booking_lead_time
    if payload.indoor_outdoor:
        cand.indoor_outdoor = payload.indoor_outdoor
    if payload.estimated_duration:
        cand.estimated_duration = payload.estimated_duration
    if payload.cost_tier:
        cand.cost_tier = payload.cost_tier
    if payload.best_time_to_visit:
        cand.best_time_to_visit = payload.best_time_to_visit


async def extract_candidate_from_text(
    payload: ExtractAndCheckRequest,
) -> POIExtractionCandidate:
    """Extracts a structured POI candidate using Google Gemini Flash-Lite with zero thinking budget."""
    # Check if Atlas Obscura URL is detected in page_url or selected_text and needs fetching
    ao_url_match = re.search(
        r"https?://(?:www\.)?atlasobscura\.com/places/([a-zA-Z0-9_-]+)",
        f"{payload.page_url} {payload.selected_text}",
    )
    if ao_url_match and (payload.latitude is None or not payload.place_name):
        ao_data = await fetch_atlas_obscura_page(ao_url_match.group(0))
        if ao_data:
            if not payload.place_name and ao_data.get("name"):
                payload.place_name = ao_data["name"]
            if payload.latitude is None and ao_data.get("latitude") is not None:
                payload.latitude = ao_data["latitude"]
                payload.longitude = ao_data["longitude"]
            if not payload.website and ao_data.get("website"):
                payload.website = ao_data["website"]
            if not payload.city and ao_data.get("city"):
                payload.city = ao_data["city"]
            if not payload.state and ao_data.get("state"):
                payload.state = ao_data["state"]
            if not payload.country and ao_data.get("country"):
                payload.country = ao_data["country"]
            if not payload.postal_code and ao_data.get("postal_code"):
                payload.postal_code = ao_data["postal_code"]
            if not payload.category_tags and ao_data.get("tags"):
                payload.category_tags = ao_data["tags"]
            if not payload.cost_tier and ao_data.get("cost_tier"):
                payload.cost_tier = ao_data["cost_tier"]
            if not payload.best_time_to_visit and ao_data.get("best_time"):
                payload.best_time_to_visit = ao_data["best_time"]
            if not payload.indoor_outdoor and ao_data.get("environment"):
                payload.indoor_outdoor = ao_data["environment"]
            if not payload.physical_effort and ao_data.get("effort"):
                payload.physical_effort = ao_data["effort"]
            if not payload.booking_lead_time and ao_data.get("booking_lead"):
                payload.booking_lead_time = ao_data["booking_lead"]
            if not payload.selected_text and ao_data.get("description"):
                payload.selected_text = ao_data["description"]
            if not payload.og_image_url and ao_data.get("image_url"):
                payload.og_image_url = ao_data["image_url"]

    # Check TripAdvisor URL
    if "tripadvisor." in payload.page_url and not payload.place_name:
        ta_m = re.search(
            r"Reviews-([^_]+(?:_[^_]+)*?)-([^_]+(?:_[^_]+)*?)\.html", payload.page_url, re.I
        )
        if ta_m:
            payload.place_name = ta_m.group(1).replace("_", " ").strip()
            loc_parts = ta_m.group(2).replace("_", " ").strip().split(" ")
            if len(loc_parts) >= 2 and not payload.city:
                payload.city = " ".join(loc_parts[:-1])
                payload.state = loc_parts[-1]
            elif not payload.city:
                payload.city = " ".join(loc_parts)

    # Check RoadsideAmerica URL
    if "roadsideamerica.com" in payload.page_url and not payload.city:
        title_parts = [p.strip() for p in payload.page_title.split(",") if p.strip()]
        if len(title_parts) >= 3:
            if not payload.place_name:
                payload.place_name = title_parts[0]
            payload.city = title_parts[1]
            payload.state = title_parts[2]
        elif len(title_parts) == 2:
            if not payload.place_name:
                payload.place_name = title_parts[0]
            payload.city = title_parts[1]

    # Check LocationScout URL
    if "locationscout.net" in payload.page_url:
        if not payload.category:
            payload.category = "photo location"
        ls_m = re.search(r"locationscout\.net/([^/]+)/(\d+-[^/?#]+)", payload.page_url, re.I)
        if ls_m:
            country_slug = ls_m.group(1).replace("-", " ").title()
            if not payload.country:
                payload.country = country_slug
            if not payload.place_name:
                name_slug = re.sub(r"^\d+-", "", ls_m.group(2)).replace("-", " ").title()
                payload.place_name = name_slug

    # Check ShotHotspot URL
    if "shothotspot.com" in payload.page_url:
        if not payload.category:
            payload.category = "photo location"
        sh_m = re.search(r"shothotspot\.com/hotspot/([^/]+)/([^/?#]+)", payload.page_url, re.I)
        if sh_m:
            country_slug = sh_m.group(1).replace("-", " ").title()
            if not payload.country:
                payload.country = country_slug
            if not payload.place_name:
                payload.place_name = sh_m.group(2).replace("-", " ").title()

    gemini_api_key = settings.GEMINI_API_KEY

    # Check if API key is present
    if not gemini_api_key or gemini_api_key.strip() in ("", "your_gemini_api_key_here"):
        logger.warning("GEMINI_API_KEY not configured. Falling back to heuristic extractor.")
        return _fallback_heuristic_extraction(payload)

    extra_context = ""
    if payload.place_name:
        extra_context += f"Place Name: {payload.place_name}\n"
    if payload.latitude is not None and payload.longitude is not None:
        extra_context += f"Exact Coordinates: {payload.latitude}, {payload.longitude}\n"
    if payload.website:
        extra_context += f"Official Website: {payload.website}\n"
    if payload.phone_number:
        extra_context += f"Phone Number: {payload.phone_number}\n"
    if payload.category:
        extra_context += f"Category / Classification: {payload.category}\n"
    if payload.city or payload.state:
        extra_context += (
            f"Location: {payload.city or ''}, {payload.state or ''}, {payload.country or ''}\n"
        )

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"Web Page Title: {payload.page_title}\n"
        f"Web Page URL: {payload.page_url}\n"
        f"{extra_context}"
        f'Highlighted Content / Context:\n"""{payload.selected_text or (payload.place_name or "Atlas Obscura Place")}"""\n'
    )

    async with egress_span(
        "Google Gemini Flash-Lite", "https://generativelanguage.googleapis.com", "generate_content"
    ):
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_api_key)

            # thinking_budget set to 0 for ultra-low latency & minimal token consumption
            # Disable automatic function calling (AFC) since this is a direct single-turn structured call without tools.
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": POIExtractionCandidate,
                "temperature": 0.1,
                "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            }
            if (
                "thinking" in settings.GEMINI_MODEL.lower()
                or "flash-lite" not in settings.GEMINI_MODEL.lower()
            ):
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

            config = types.GenerateContentConfig(**config_kwargs)

            # Synchronous SDK call wrapped in executor if necessary
            try:
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
            except Exception as call_err:
                if "thinking_config" in config_kwargs and "INVALID_ARGUMENT" in str(call_err):
                    config_kwargs.pop("thinking_config", None)
                    config = types.GenerateContentConfig(**config_kwargs)
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config=config,
                    )
                else:
                    raise call_err

            if response and response.text:
                candidate_data = json.loads(response.text)
                cand = POIExtractionCandidate.model_validate(candidate_data)
                cand.website_official = sanitize_official_website(cand.website_official)
                _apply_payload_enrichment(cand, payload)
                infer_category_tags(cand, payload)
                cand.website_official = sanitize_official_website(cand.website_official)
                return cand
            else:
                raise ValueError("Empty response received from Gemini Flash-Lite.")

        except Exception as exc:
            logger.error(f"Gemini Flash-Lite extraction error: {exc}. Using heuristic fallback.")
            return _fallback_heuristic_extraction(payload)


NPS_KEYWORDS = (
    "national park",
    "national monument",
    "national battlefield",
    "national military park",
    "national historic site",
    "national historical park",
    "national recreation area",
    "national seashore",
    "national lakeshore",
    "national preserve",
    "national memorial",
    "national river",
    "national parkway",
    "national wild and scenic river",
    "national scenic trail",
    "national heritage area",
    "national park service",
)


TAG_RULES: dict[str, list[str]] = {
    "ship": [
        "uss ",
        "hms ",
        "ship",
        "warship",
        "battleship",
        "aircraft carrier",
        "vessel",
        "submarine",
        "boat",
        "ferry",
        "naval ship",
        "fleet",
    ],
    "military": [
        "military",
        "war",
        "warship",
        "battlefield",
        "battle",
        "fort",
        "fortress",
        "citadel",
        "bunker",
        "uss ",
        "veteran",
        "naval",
        "navy",
        "army",
        "marines",
        "air force",
        "armory",
        "garrison",
    ],
    "airplane": [
        "airplane",
        "aircraft",
        "aviation",
        "air and space",
        "flight",
        "aerospace",
        "hangar",
        "aerodrome",
        "bomber",
        "fighter jet",
    ],
    "aviation": [
        "aviation",
        "airplane",
        "aircraft",
        "air and space",
        "flight",
        "aerospace",
        "pilot",
        "hangar",
        "aerodrome",
    ],
    "space": [
        "space",
        "aerospace",
        "nasa",
        "rocket",
        "astronaut",
        "satellite",
        "spacecraft",
        "observatory",
        "planetarium",
        "sea, air and space",
    ],
    "historic": [
        "historic",
        "history",
        "historical",
        "heritage",
        "ancient",
        "museum",
        "uss ",
        "century",
        "monument",
        "memorial",
        "ruins",
        "castle",
        "mission",
        "presidio",
        "landmark",
    ],
    "museum": ["museum", "gallery", "exhibit", "collection"],
    "viewpoint": ["viewpoint", "lookout", "overlook", "vista", "panorama", "scenic view"],
    "waterfall": ["waterfall", "falls", "cascade"],
    "hiking": ["hiking", "hike", "trail", "trek"],
    "island": ["island", "isle", "archipelago", "atoll"],
    "lighthouse": ["lighthouse", "light station"],
    "castle": ["castle", "palace", "chateau", "fortress"],
    "bridge": ["bridge", "viaduct", "suspension bridge"],
    "canyon": ["canyon", "gorge", "ravine"],
    "cave": ["cave", "cavern", "grotto"],
    "beach": ["beach", "cove", "seashore", "coast"],
    "mountain": ["mountain", "mount", "peak", "summit", "ridge"],
    "wildlife": ["wildlife", "safari", "animals", "birds", "sanctuary", "refuge"],
    "monument": ["monument", "memorial", "statue"],
    "food": [
        "restaurant",
        "food",
        "dining",
        "bar",
        "wine",
        "cafe",
        "bakery",
        "cocktail",
        "culinary",
        "oysters",
        "bistro",
        "eatery",
        "creole",
        "gastro",
    ],
}


def infer_category_tags(candidate: POIExtractionCandidate, payload: ExtractAndCheckRequest) -> None:
    """Enriches category tags based on semantic rules from place name, category, description, and context."""
    text_corpus = (
        f"{candidate.name} {candidate.description or ''} {' '.join(candidate.category_tags)} "
        f"{payload.selected_text or ''} {payload.category or ''} {payload.page_title or ''} "
        f"{payload.website or ''} {candidate.website_official or ''}"
    ).lower()

    for tag, patterns in TAG_RULES.items():
        if any(p in text_corpus for p in patterns) and tag not in candidate.category_tags:
            candidate.category_tags.append(tag)

    ensure_nps_tag(candidate, payload)


def ensure_nps_tag(candidate: POIExtractionCandidate, payload: ExtractAndCheckRequest) -> None:
    """Detects National Park Service units and automatically adds 'NPS' to category_tags."""
    combined_text = (
        f"{candidate.name} {candidate.description or ''} {' '.join(candidate.category_tags)} "
        f"{candidate.website_official or ''} {payload.website or ''} {payload.category or ''} "
        f"{payload.page_title} {payload.page_url} {payload.selected_text} {payload.place_name or ''}"
    ).lower()

    if (
        "nps.gov" in combined_text or any(kw in combined_text for kw in NPS_KEYWORDS)
    ) and "NPS" not in candidate.category_tags:
        candidate.category_tags.append("NPS")


def _fallback_heuristic_extraction(payload: ExtractAndCheckRequest) -> POIExtractionCandidate:
    """Heuristic fallback parser when Gemini API is unavailable or unconfigured."""
    text_snippet = payload.selected_text.strip() if payload.selected_text else ""
    first_line = text_snippet.split("\n")[0].strip() if text_snippet else ""

    # Derive clean narrative description (strip away any structured tags)
    clean_desc_lines = []
    for line in text_snippet.splitlines():
        line_str = line.strip()
        lower_line = line_str.lower()
        if lower_line.startswith("description:"):
            clean_desc_lines.append(line_str[len("description:") :].strip())
        elif any(
            lower_line.startswith(prefix)
            for prefix in [
                "point of interest:",
                "category:",
                "address:",
                "coordinates:",
                "official website:",
                "phone:",
            ]
        ):
            continue
        else:
            clean_desc_lines.append(line_str)
    clean_desc = " ".join([line for line in clean_desc_lines if line]).strip()

    # Derive name candidate from explicit place_name, first line, or page title
    if payload.place_name:
        name_candidate = payload.place_name.strip()
    elif first_line and not any(
        first_line.lower().startswith(p) for p in ["point of interest:", "description:"]
    ):
        name_candidate = first_line[:60]
    else:
        name_candidate = payload.page_title.split("|")[0].split("-")[0].strip()

    if not name_candidate:
        name_candidate = "Scenic Point of Interest"

    loc_parts = [p for p in [payload.city, payload.state, payload.country] if p]
    if loc_parts:
        search_query = f"{name_candidate}, {', '.join(loc_parts)}"
    elif payload.page_title:
        search_query = f"{name_candidate}, {payload.page_title.split('|')[-1].strip()}"
    else:
        search_query = name_candidate

    initial_tags = ["travel", "scenic"]
    if payload.category:
        cat_lower = payload.category.lower()
        for kw in [
            "historic",
            "museum",
            "viewpoint",
            "waterfall",
            "hiking",
            "beach",
            "trail",
            "nature",
            "wildlife",
            "overlook",
            "food",
            "lodging",
        ]:
            if kw in cat_lower and kw not in initial_tags:
                initial_tags.append(kw)

    # Best-effort inferencing for visit details
    combined_lower = f"{name_candidate} {text_snippet} {payload.category or ''}".lower()

    env = None
    if any(w in combined_lower for w in ["indoor", "museum", "gallery", "aquarium", "theater"]):
        env = "Indoor"
    elif any(
        w in combined_lower
        for w in [
            "outdoor",
            "park",
            "trail",
            "hike",
            "beach",
            "overlook",
            "viewpoint",
            "waterfall",
            "canyon",
            "mountain",
        ]
    ):
        env = "Outdoor"
    elif any(w in combined_lower for w in ["ship", "aircraft carrier", "castle", "ruins", "zoo"]):
        env = "Mixed"

    effort = None
    if any(
        w in combined_lower for w in ["strenuous", "hard hike", "difficult hike", "steep climb"]
    ):
        effort = "strenuous"
    elif any(w in combined_lower for w in ["moderate hike", "hike", "trail"]):
        effort = "moderate hike"
    elif any(w in combined_lower for w in ["paved walk", "stroll", "stairs"]):
        effort = "paved walk"
    elif any(w in combined_lower for w in ["drive-up", "lookout", "viewpoint", "overlook"]):
        effort = "drive-up"

    duration = None
    if any(w in combined_lower for w in ["all day", "full day"]):
        duration = "full day"
    elif any(w in combined_lower for w in ["half day", "3-4 hours", "few hours"]):
        duration = "half day"
    elif any(
        w in combined_lower for w in ["1-2 hours", "1 to 2 hours", "couple hours", "museum", "tour"]
    ):
        duration = "1-2 hours"
    elif any(w in combined_lower for w in ["quick stop", "30 mins"]):
        duration = "30 mins"

    cost = None
    if "free" in combined_lower or "no admission" in combined_lower:
        cost = "Free"
    elif any(w in combined_lower for w in ["$$$$", "luxury", "expensive"]):
        cost = "$$$$"
    elif any(w in combined_lower for w in ["$$$", "fine dining"]):
        cost = "$$$"
    elif any(w in combined_lower for w in ["$$", "tickets", "admission", "entrance fee"]):
        cost = "$$"
    elif "$" in combined_lower:
        cost = "$"

    best_time = None
    if "sunrise" in combined_lower:
        best_time = "Sunrise"
    elif "sunset" in combined_lower:
        best_time = "Sunset"
    elif "golden hour" in combined_lower:
        best_time = "Golden Hour"
    elif "morning" in combined_lower:
        best_time = "Morning"
    elif "night" in combined_lower or "stargazing" in combined_lower:
        best_time = "Night"

    lead_time = None
    if any(w in combined_lower for w in ["permit lottery", "lottery"]):
        lead_time = "permit lottery"
    elif any(w in combined_lower for w in ["months ahead", "reserve months"]):
        lead_time = "months ahead"
    elif any(
        w in combined_lower for w in ["reservation required", "book in advance", "book ahead"]
    ):
        lead_time = "1-3 days ahead"
    elif any(w in combined_lower for w in ["walk-in", "no reservation", "open daily"]):
        lead_time = "walk-in ok"

    cand = POIExtractionCandidate(
        name=name_candidate,
        name_aliases=[],
        poi_type="site to see",
        personal_rating=4,
        description=clean_desc[:300] if clean_desc else f"Captured location: {name_candidate}.",
        category_tags=initial_tags,
        physical_effort=effort,
        booking_lead_time=lead_time,
        indoor_outdoor=env,
        estimated_duration=duration,
        cost_tier=cost,
        hours_seasonality=None,
        best_time_to_visit=best_time,
        website_official=sanitize_official_website(payload.website),
        phone_number=payload.phone_number,
        search_address_query=search_query,
        iptc_sublocation=name_candidate,
        iptc_city=None,
        iptc_province_state=None,
        iptc_country_code=None,
        iptc_world_region=None,
    )
    _apply_payload_enrichment(cand, payload)
    infer_category_tags(cand, payload)
    cand.website_official = sanitize_official_website(cand.website_official)
    return cand
