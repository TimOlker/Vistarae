"""Deterministic Geocoding Service using OpenStreetMap Nominatim & PostGIS Geocache."""

import asyncio
import hashlib
import logging
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.middleware.telemetry import egress_span
from app.models import Geocache

logger = logging.getLogger("vistarae.geocoding")

# Global lock & timestamp for 1 req/sec rate limit enforcement
_rate_limit_lock = asyncio.Lock()
_last_request_time: float = 0.0


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


async def geocode_query(
    query_str: str,
    db: AsyncSession,
) -> tuple[float, float, str | None, dict[str, Any]]:
    """Geocodes a search string using local PostGIS geocache first, then Nominatim."""
    if not query_str or not query_str.strip():
        # Default fallback coordinates
        return (0.0, 0.0, "Unknown Location", {})

    query_hash = compute_query_hash(query_str)

    # 1. Check local geocache table
    cached = await db.scalar(select(Geocache).where(Geocache.query_hash == query_hash))
    if cached:
        logger.info(f"Geocache HIT for '{query_str}' -> ({cached.latitude}, {cached.longitude})")
        return (float(cached.latitude), float(cached.longitude), cached.display_name, cached.raw_json or {})

    logger.info(f"Geocache MISS for '{query_str}'. Calling OSM Nominatim API.")

    # 2. Rate limit guard
    await _enforce_rate_limit()

    # 3. Call Nominatim API wrapped in child trace span
    url = f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search"
    params = {
        "q": query_str,
        "format": "jsonv2",
        "addressdetails": "1",
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
                    else:
                        logger.warning(f"Nominatim returned 0 results for query: '{query_str}'")
                else:
                    logger.error(f"Nominatim error HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"Failed to query Nominatim: {exc}")

    # 4. Cache result in database if valid coordinates found
    if lat != 0.0 or lng != 0.0:
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
            logger.warning(f"Could not write to geocache table: {exc}")

    return (lat, lng, display_name, raw_json)
