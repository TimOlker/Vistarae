"""Deterministic Geocoding Service using OpenStreetMap Nominatim & PostGIS Geocache."""

import asyncio
import hashlib
import logging
import re
import time
from typing import Any

import httpx
from openlocationcode import openlocationcode as olc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.middleware.telemetry import egress_span
from app.models import Geocache

logger = logging.getLogger("vistarae.geocoding")

# Global lock & timestamp for 1 req/sec rate limit enforcement
_rate_limit_lock = asyncio.Lock()
_last_request_time: float = 0.0

COORD_PATTERN = re.compile(
    r"^\s*\(?\s*(-?\d{1,2}(?:\.\d+)?)\s*[, \t/]+\s*(-?\d{1,3}(?:\.\d+)?)\s*\)?\s*$"
)

GMAPS_URL_PATTERN = re.compile(r"(?:@|[?&](?:q|ll)=)(-?\d{1,2}\.\d+)[, ]+(-?\d{1,3}\.\d+)")

PLUS_CODE_PATTERN = re.compile(
    r"\b([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3})\b",
    re.IGNORECASE,
)


def compute_query_hash(query_str: str) -> str:
    """Normalizes address string and computes SHA256 hash."""
    normalized = " ".join(query_str.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _enforce_rate_limit() -> None:
    """Enforces strict 1 req/sec delay for OpenStreetMap Nominatim compliance."""
    global _last_request_time
    async with _rate_limit_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        required_delay = settings.NOMINATIM_RATE_LIMIT_SEC
        if elapsed < required_delay:
            wait_time = required_delay - elapsed
            logger.debug(f"Nominatim rate limit pause: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        _last_request_time = time.monotonic()


async def _raw_nominatim_search(
    query_str: str,
) -> tuple[float, float, str, dict[str, Any]]:
    """Makes a rate-limited query directly to OSM Nominatim API."""
    await _enforce_rate_limit()
    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search"
    params = {
        "q": query_str,
        "format": "jsonv2",
        "addressdetails": "1",
        "extratags": "1",
        "limit": "1",
    }
    headers = {
        "User-Agent": settings.NOMINATIM_USER_AGENT,
        "Accept-Language": "en",
    }
    raw_json = {}
    lat = 0.0
    lng = 0.0
    display_name = query_str
    async with egress_span("OSM Nominatim", url, "geocode"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    results = resp.json()
                    if results and len(results) > 0:
                        top = results[0]
                        lat = float(top.get("lat", 0.0))
                        lng = float(top.get("lon", 0.0))
                        display_name = top.get("display_name", query_str)
                        raw_json = top
        except Exception as exc:
            logger.error(f"Failed to query Nominatim for '{query_str}': {exc}")
    return (lat, lng, display_name, raw_json)


async def _resolve_locality_reference(
    locality: str,
    db: AsyncSession,
) -> tuple[float | None, float | None]:
    """Finds reference coordinates for resolving a short Google Plus Code or fallback."""
    parts = [p.strip() for p in locality.split(",") if p.strip()]
    if not parts:
        return (None, None)

    country = parts[-1] if len(parts) > 1 else ""
    middle_parts = parts[:-1] if len(parts) > 1 else parts

    clean_middle: list[str] = []
    for p in middle_parts:
        cleaned = re.sub(r"\b\d{4,}\b", "", p).strip()
        if cleaned and cleaned not in clean_middle:
            clean_middle.append(cleaned)

    candidates: list[str] = []
    if clean_middle and country:
        candidates.append(", ".join(clean_middle + [country]))
    elif clean_middle:
        candidates.append(", ".join(clean_middle))

    region_keywords = {"governorate", "province", "state", "county", "region", "district"}
    city_candidates = [p for p in clean_middle if not any(k in p.lower() for k in region_keywords)]
    region_candidates = [p for p in clean_middle if any(k in p.lower() for k in region_keywords)]

    for p in reversed(city_candidates):
        candidates.append(f"{p}, {country}" if country else p)
    for p in reversed(region_candidates):
        candidates.append(f"{p}, {country}" if country else p)

    for cand in candidates:
        cand_hash = compute_query_hash(cand)
        cached = await db.scalar(select(Geocache).where(Geocache.query_hash == cand_hash))
        if cached:
            return (float(cached.latitude), float(cached.longitude))

        cand_lat, cand_lng, _, _ = await _raw_nominatim_search(cand)
        if cand_lat != 0.0 or cand_lng != 0.0:
            return (cand_lat, cand_lng)

    return (None, None)


async def geocode_query(
    query_str: str,
    db: AsyncSession,
) -> tuple[float, float, str | None, dict[str, Any]]:
    """Geocodes a search string using local PostGIS geocache first, then handles
    direct coordinates, Google Maps URLs, Google Plus Codes, and Nominatim search with fallbacks."""
    if not query_str or not query_str.strip():
        return (0.0, 0.0, "Unknown Location", {})

    cleaned_query = query_str.strip()
    query_hash = compute_query_hash(cleaned_query)

    # 1. Check local geocache table
    cached = await db.scalar(select(Geocache).where(Geocache.query_hash == query_hash))
    if cached:
        logger.info(
            f"Geocache HIT for '{cleaned_query}' -> ({cached.latitude}, {cached.longitude})"
        )
        return (
            float(cached.latitude),
            float(cached.longitude),
            cached.display_name,
            cached.raw_json or {},
        )

    # Helper to cache and return
    async def _cache_and_return(
        f_lat: float, f_lng: float, f_display: str | None, f_json: dict[str, Any]
    ):
        if f_lat != 0.0 or f_lng != 0.0:
            new_entry = Geocache(
                query_hash=query_hash,
                latitude=f_lat,
                longitude=f_lng,
                display_name=f_display,
                raw_json=f_json,
            )
            db.add(new_entry)
            try:
                await db.flush()
            except Exception as exc:
                logger.warning(f"Could not write to geocache table: {exc}")
        return (f_lat, f_lng, f_display, f_json)

    # 2. Direct coordinates check (e.g. "25.3178, 32.5517")
    coord_match = COORD_PATTERN.match(cleaned_query)
    if coord_match:
        try:
            c_lat = float(coord_match.group(1))
            c_lng = float(coord_match.group(2))
            if -90.0 <= c_lat <= 90.0 and -180.0 <= c_lng <= 180.0:
                disp, r_json = await reverse_geocode(c_lat, c_lng, db)
                disp = disp or f"{c_lat:.6f}, {c_lng:.6f}"
                return await _cache_and_return(c_lat, c_lng, disp, r_json)
        except Exception:
            pass

    # 3. Google Maps URL check
    gmaps_match = GMAPS_URL_PATTERN.search(cleaned_query)
    if gmaps_match:
        try:
            g_lat = float(gmaps_match.group(1))
            g_lng = float(gmaps_match.group(2))
            if -90.0 <= g_lat <= 90.0 and -180.0 <= g_lng <= 180.0:
                disp, r_json = await reverse_geocode(g_lat, g_lng, db)
                disp = disp or f"{g_lat:.6f}, {g_lng:.6f}"
                return await _cache_and_return(g_lat, g_lng, disp, r_json)
        except Exception:
            pass

    # 4. Google Plus Code (Open Location Code) check
    plus_match = PLUS_CODE_PATTERN.search(cleaned_query)
    if plus_match:
        code = plus_match.group(1).upper()
        locality = (
            (cleaned_query[: plus_match.start()] + " " + cleaned_query[plus_match.end() :])
            .strip()
            .strip(",")
            .strip()
        )

        # Case 4A: Full Plus Code (e.g. 7GQJ8H92+5M4)
        if olc.isFull(code):
            try:
                area = olc.decode(code)
                p_lat = float(area.latitudeCenter)
                p_lng = float(area.longitudeCenter)
                disp, r_json = await reverse_geocode(p_lat, p_lng, db)
                disp = disp or cleaned_query
                return await _cache_and_return(p_lat, p_lng, disp, r_json)
            except Exception as exc:
                logger.warning(f"Failed to decode full Plus Code '{code}': {exc}")

        # Case 4B: Short Plus Code with locality (e.g. 8H92+5M4, Nile, Esna City, Esna...)
        elif olc.isShort(code) and locality:
            ref_lat, ref_lng = await _resolve_locality_reference(locality, db)
            if ref_lat is not None and ref_lng is not None:
                try:
                    full_code = olc.recoverNearest(code, ref_lat, ref_lng)
                    area = olc.decode(full_code)
                    p_lat = float(area.latitudeCenter)
                    p_lng = float(area.longitudeCenter)
                    disp, r_json = await reverse_geocode(p_lat, p_lng, db)
                    disp = disp or cleaned_query
                    return await _cache_and_return(p_lat, p_lng, disp, r_json)
                except Exception as exc:
                    logger.warning(
                        f"Failed to recover short Plus Code '{code}' with ref ({ref_lat}, {ref_lng}): {exc}"
                    )

    # 5. Standard Nominatim search
    lat, lng, display_name, raw_json = await _raw_nominatim_search(cleaned_query)

    # 6. Progressive fallback if 0 results returned and query has commas
    if (lat == 0.0 and lng == 0.0) and ("," in cleaned_query):
        ref_lat, ref_lng = await _resolve_locality_reference(cleaned_query, db)
        if ref_lat is not None and ref_lng is not None:
            lat = ref_lat
            lng = ref_lng
            disp, r_json = await reverse_geocode(lat, lng, db)
            display_name = disp or display_name
            raw_json = r_json or raw_json

    return await _cache_and_return(lat, lng, display_name, raw_json)


async def reverse_geocode(
    lat: float,
    lng: float,
    db: AsyncSession,
) -> tuple[str | None, dict[str, Any]]:
    """Resolves address details from coordinates (reverse geocoding) using cache first, then Nominatim."""
    if lat == 0.0 and lng == 0.0:
        return (None, {})

    # Key formatted with 6 decimal places (~0.1m precision)
    query_str = f"reverse:{lat:.6f},{lng:.6f}"
    query_hash = compute_query_hash(query_str)

    # 1. Check local geocache table
    cached = await db.scalar(select(Geocache).where(Geocache.query_hash == query_hash))
    if cached:
        logger.info(f"Geocache reverse HIT for ({lat}, {lng}) -> {cached.display_name}")
        return (cached.display_name, cached.raw_json or {})

    logger.info(f"Geocache reverse MISS for ({lat}, {lng}). Calling OSM Nominatim reverse API.")

    # 2. Rate limit guard
    await _enforce_rate_limit()

    # 3. Call Nominatim reverse API wrapped in child trace span
    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/reverse"
    params = {
        "lat": str(lat),
        "lon": str(lng),
        "format": "jsonv2",
        "addressdetails": "1",
        "extratags": "1",
    }
    headers = {
        "User-Agent": settings.NOMINATIM_USER_AGENT,
        "Accept-Language": "en",
    }

    display_name = None
    raw_json = {}

    async with egress_span("OSM Nominatim Reverse", url, "reverse_geocode"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and "error" not in data:
                        display_name = data.get("display_name")
                        raw_json = data
                    else:
                        logger.warning(
                            f"Nominatim reverse returned no address for ({lat}, {lng}): {data}"
                        )
                else:
                    logger.error(f"Nominatim reverse error HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Failed to reverse geocode via Nominatim: {exc}")

    # 4. Cache result in database if address returned
    if raw_json and ("address" in raw_json or display_name):
        new_cache_entry = Geocache(
            query_hash=query_hash,
            latitude=lat,
            longitude=lng,
            display_name=display_name,
            raw_json=raw_json,
        )
        db.add(new_cache_entry)
        try:
            await db.flush()
        except Exception as exc:
            logger.warning(f"Could not write reverse geocache entry: {exc}")

    return (display_name, raw_json)


def extract_address_components(raw_geo: dict[str, Any]) -> dict[str, Any]:
    """Extracts standardized address components from geocoding raw JSON."""
    if not raw_geo or "address" not in raw_geo:
        return {}
    addr = raw_geo["address"]

    city_val = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("hamlet")
        or addr.get("municipality")
        or addr.get("county")
    )
    state_val = (
        addr.get("state")
        or addr.get("province")
        or addr.get("region")
        or addr.get("state_district")
    )
    country_code_val = addr.get("country_code", "").upper()
    postcode_val = addr.get("postcode")
    sublocation_val = (
        addr.get("road")
        or addr.get("suburb")
        or addr.get("neighbourhood")
        or addr.get("tourism")
        or addr.get("leisure")
        or addr.get("natural")
    )
    country_name_val = addr.get("country")

    return {
        "city": city_val,
        "state": state_val,
        "country_code": country_code_val,
        "postcode": postcode_val,
        "sublocation": sublocation_val,
        "country_name": country_name_val,
    }


def extract_poi_meta_from_geo(raw_geo: dict[str, Any]) -> dict[str, Any]:
    """Extracts website, phone, opening_hours, and category tags from Nominatim raw_json."""
    if not isinstance(raw_geo, dict):
        return {}
    extratags = raw_geo.get("extratags")
    if not isinstance(extratags, dict):
        extratags = {}
    website = extratags.get("website") or extratags.get("contact:website") or extratags.get("url")
    phone = extratags.get("phone") or extratags.get("contact:phone")
    opening_hours = extratags.get("opening_hours")

    tags = []
    category = raw_geo.get("category")
    geo_type = raw_geo.get("type")
    tag_mapping = {
        "viewpoint": "viewpoint",
        "museum": "museum",
        "attraction": "scenic",
        "theme_park": "experience",
        "zoo": "wildlife",
        "aquarium": "wildlife",
        "artwork": "historic",
        "monument": "monument",
        "memorial": "memorial",
        "castle": "castle",
        "ruins": "historic",
        "archaeological_site": "historic",
        "park": "park",
        "nature_reserve": "nature",
        "garden": "nature",
        "beach": "beach",
        "peak": "mountain",
        "volcano": "mountain",
        "waterfall": "waterfall",
        "cave_entrance": "cave",
        "lighthouse": "lighthouse",
        "bridge": "bridge",
    }
    for val in (geo_type, category):
        if val and str(val).lower() in tag_mapping:
            tag_mapped = tag_mapping[str(val).lower()]
            if tag_mapped not in tags:
                tags.append(tag_mapped)

    return {
        "website": website,
        "phone": phone,
        "opening_hours": opening_hours,
        "category_tags": tags,
    }


def enrich_candidate_from_address(candidate: Any, raw_geo: dict[str, Any]) -> None:
    """Enriches candidate IPTC and geographic fields from geocoding raw address dictionary."""
    comps = extract_address_components(raw_geo)
    if comps:
        city_val = comps.get("city")
        state_val = comps.get("state")
        country_code_val = comps.get("country_code")
        postcode_val = comps.get("postcode")
        sublocation_val = comps.get("sublocation")
        country_name_val = comps.get("country_name")

        city_needs_resolution = (
            not candidate.iptc_city
            or candidate.iptc_city.lower() in ("unknown", "unknown city")
            or (
                candidate.iptc_province_state
                and candidate.iptc_city.strip().lower()
                == candidate.iptc_province_state.strip().lower()
            )
        )
        if city_needs_resolution and city_val:
            candidate.iptc_city = city_val

        if (
            not candidate.iptc_province_state
            or candidate.iptc_province_state.lower() in ("unknown", "unknown state")
        ) and state_val:
            candidate.iptc_province_state = state_val
        if country_code_val:
            raw_allowed = (
                getattr(candidate, "raw_data", {}).get("_allowed_country_codes")
                if hasattr(candidate, "raw_data") and isinstance(candidate.raw_data, dict)
                else None
            )
            if (
                not candidate.iptc_country_code
                or candidate.iptc_country_code.lower() in ("unknown", "unknown country")
                or raw_allowed
                and country_code_val in raw_allowed
            ):
                candidate.iptc_country_code = country_code_val
        if not candidate.iptc_zip_code and postcode_val:
            candidate.iptc_zip_code = postcode_val
        if not candidate.iptc_sublocation and sublocation_val:
            candidate.iptc_sublocation = sublocation_val
        if (
            hasattr(candidate, "iptc_world_region")
            and not candidate.iptc_world_region
            and country_name_val
        ):
            candidate.iptc_world_region = country_name_val

    meta = extract_poi_meta_from_geo(raw_geo)
    if not getattr(candidate, "website_official", None) and meta.get("website"):
        candidate.website_official = meta["website"]
    if not getattr(candidate, "phone_number", None) and meta.get("phone"):
        candidate.phone_number = meta["phone"]
    if meta.get("category_tags"):
        existing_tags = getattr(candidate, "category_tags", []) or []
        for t in meta["category_tags"]:
            if t not in existing_tags:
                existing_tags.append(t)
        candidate.category_tags = existing_tags
