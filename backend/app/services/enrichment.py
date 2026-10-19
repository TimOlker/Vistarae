"""Service for resolving photo dates and enriching place details (category tags, website, phone, etc.)."""

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.extraction import ExtractAndCheckRequest
from app.services.countries import map_country_to_code
from app.services.extraction import extract_candidate_from_text, sanitize_official_website
from app.services.geocoding import (
    extract_address_components,
    extract_poi_meta_from_geo,
    geocode_query,
    reverse_geocode,
)

logger = logging.getLogger("vistarae.enrichment")

# Optional import of photo scraper EXIF extractor
try:
    from photo_scraper.core.exif import extract_image_metadata
except ImportError:
    extract_image_metadata = None


def resolve_folder_photo_date(folder_path_str: str | None) -> date | None:
    """Attempts to resolve the earliest photo date from a folder path:
    1. If the path exists on disk, inspects image files for EXIF date_taken or earliest mtime.
    2. Fallback: parses full ISO date (YYYY-MM-DD) or 4-digit year (YYYY) from folder path string.
    """
    if not folder_path_str:
        return None

    try:
        p = Path(folder_path_str)
        if p.exists() and p.is_dir():
            image_exts = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}
            exif_dates: list[date] = []
            file_mtimes: list[date] = []
            try:
                for item in p.iterdir():
                    if item.is_file() and item.suffix.lower() in image_exts:
                        if extract_image_metadata:
                            try:
                                meta = extract_image_metadata(item)
                                if meta and meta.date_taken:
                                    exif_dates.append(meta.date_taken)
                            except Exception:
                                pass
                        try:
                            st = item.stat()
                            mdate = date.fromtimestamp(st.st_mtime)
                            if 1990 <= mdate.year <= date.today().year:
                                file_mtimes.append(mdate)
                        except Exception:
                            pass
            except Exception as read_err:
                logger.debug(f"Failed iterating folder '{folder_path_str}': {read_err}")

            if exif_dates:
                return min(exif_dates)
            if file_mtimes:
                return min(file_mtimes)
    except Exception as path_err:
        logger.debug(f"Path access error for '{folder_path_str}': {path_err}")

    # Fallback: Parse date or year from directory path
    parts = re.split(r"[\\/]", folder_path_str)
    full_date_regex = re.compile(r"(19\d\d|20\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")
    for part in reversed(parts):
        m = full_date_regex.search(part)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

    # Check for standalone 4-digit year
    year_regex = re.compile(r"^(19\d\d|20\d\d)$")
    for part in parts:
        m = year_regex.match(part.strip())
        if m:
            return date(int(m.group(1)), 1, 1)

    return None


async def lookup_and_enrich_place(
    place_name: str,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    db: AsyncSession | None = None,
    folder_context: str | None = None,
) -> dict[str, Any]:
    """Combines OpenStreetMap Nominatim extratags with Google Gemini Flash-Lite
    to look up category tags, official website, phone number, and logistics details.
    """
    category_tags: list[str] = []
    website_official: str | None = None
    phone_number: str | None = None
    description: str | None = None
    poi_type: str = "site to see"
    physical_effort: str | None = None
    indoor_outdoor: str | None = None
    estimated_duration: str | None = None
    cost_tier: str | None = None
    best_time_to_visit: str | None = None
    hours_seasonality: str | None = None
    resolved_lat = latitude
    resolved_lng = longitude

    # 1. Geocoding / Reverse geocoding with extratags
    raw_geo: dict[str, Any] = {}
    if db:
        try:
            if (
                resolved_lat is not None
                and resolved_lng is not None
                and (resolved_lat != 0.0 or resolved_lng != 0.0)
            ):
                _, raw_geo = await reverse_geocode(resolved_lat, resolved_lng, db)
            else:
                query_parts = [place_name]
                if city:
                    query_parts.append(city)
                if state:
                    query_parts.append(state)
                if country:
                    query_parts.append(country)
                q_str = ", ".join([p.strip() for p in query_parts if p and p.strip()])
                n_lat, n_lng, _, raw_geo = await geocode_query(q_str, db)
                if n_lat != 0.0 or n_lng != 0.0:
                    resolved_lat = n_lat
                    resolved_lng = n_lng
        except Exception as geo_err:
            logger.warning(f"Geocoding lookup error for '{place_name}': {geo_err}")

    # Extract metadata from OSM Nominatim extratags
    if raw_geo:
        geo_meta = extract_poi_meta_from_geo(raw_geo)
        website_official = geo_meta.get("website")
        phone_number = geo_meta.get("phone")
        hours_seasonality = geo_meta.get("opening_hours")
        for tag in geo_meta.get("category_tags", []):
            if tag and tag not in category_tags:
                category_tags.append(tag)

        # Address components fallback
        addr_comps = extract_address_components(raw_geo)
        if not city and addr_comps.get("city"):
            city = addr_comps["city"]
        if not state and addr_comps.get("state"):
            state = addr_comps["state"]
        if not country and addr_comps.get("country_name"):
            country = addr_comps["country_name"]

    # 2. Gemini Flash-Lite LLM Enrichment
    if settings.GEMINI_API_KEY:
        try:
            text_context = f"{place_name}"
            if city or state or country:
                loc_str = ", ".join([p for p in (city, state, country) if p])
                text_context += f" in {loc_str}"
            if folder_context:
                text_context += f" (photo context: {folder_context})"

            req = ExtractAndCheckRequest(
                selected_text=text_context,
                page_title=place_name,
                page_url=f"enrichment://{place_name}",
                place_name=place_name,
                city=city,
                state=state,
                country=country,
                latitude=resolved_lat,
                longitude=resolved_lng,
            )
            cand = await extract_candidate_from_text(req)
            if cand:
                if cand.category_tags:
                    for t in cand.category_tags:
                        clean_t = t.strip()
                        if clean_t and clean_t not in category_tags:
                            category_tags.append(clean_t)
                if not website_official and cand.website_official:
                    website_official = cand.website_official
                if not phone_number and cand.phone_number:
                    phone_number = cand.phone_number
                if cand.description:
                    description = cand.description
                if cand.poi_type:
                    poi_type = cand.poi_type
                if cand.physical_effort:
                    physical_effort = cand.physical_effort
                if cand.indoor_outdoor:
                    indoor_outdoor = cand.indoor_outdoor
                if cand.estimated_duration:
                    estimated_duration = cand.estimated_duration
                if cand.cost_tier:
                    cost_tier = cand.cost_tier
                if cand.best_time_to_visit:
                    best_time_to_visit = cand.best_time_to_visit
                if not hours_seasonality and cand.hours_seasonality:
                    hours_seasonality = cand.hours_seasonality
        except Exception as llm_err:
            logger.warning(f"Gemini enrichment failed for '{place_name}': {llm_err}")

    country_code = map_country_to_code(country) if country else None

    return {
        "place_name": place_name,
        "category_tags": category_tags,
        "website_official": sanitize_official_website(website_official),
        "phone_number": phone_number,
        "description": description,
        "poi_type": poi_type,
        "physical_effort": physical_effort,
        "indoor_outdoor": indoor_outdoor,
        "estimated_duration": estimated_duration,
        "cost_tier": cost_tier,
        "best_time_to_visit": best_time_to_visit,
        "hours_seasonality": hours_seasonality,
        "city": city,
        "state": state,
        "country": country,
        "country_code": country_code,
        "latitude": resolved_lat,
        "longitude": resolved_lng,
    }
