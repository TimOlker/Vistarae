"""Spatial collision and deduplication engine using PostGIS & pg_trgm."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.poi import CollisionStatus, POICollisionMatch

logger = logging.getLogger("vistarae.deduplication")

FEET_TO_METERS = 0.3048


async def check_spatial_collision(
    cand_name: str,
    cand_lat: float | None,
    cand_lng: float | None,
    radius_ft: int,
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> tuple[CollisionStatus, POICollisionMatch | None, POICollisionMatch | None]:
    """Performs PostGIS spatial radius & trigram similarity search scoped to user.

    Returns:
        (collision_status, matched_duplicate, nearby_parent_candidate)
    """
    if cand_lat is None or cand_lng is None or (cand_lat == 0.0 and cand_lng == 0.0):
        return (CollisionStatus.UNIQUE_LOCATION, None, None)

    radius_meters = float(radius_ft) * FEET_TO_METERS

    # Query existing POIs within spatial radius using ST_DWithin and compute similarity
    sql = text("""
        SELECT
            p.id,
            p.name,
            p.name_aliases,
            p.poi_type,
            p.personal_rating,
            p.description,
            p.iptc_city,
            p.iptc_province_state,
            p.geofence_radius_ft,
            p.parent_poi_id,
            p.category_tags,
            ST_Distance(p.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_meters,
            similarity(p.name, :cand_name) AS name_similarity
        FROM pois p
        WHERE ST_DWithin(p.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_meters)
          AND (p.user_id = :user_id OR :user_id IS NULL)
        ORDER BY distance_meters ASC
        LIMIT 10;
    """)

    try:
        result = await db.execute(
            sql,
            {
                "lng": cand_lng,
                "lat": cand_lat,
                "cand_name": cand_name,
                "radius_meters": radius_meters,
                "user_id": user_id,
            },
        )
        rows = result.mappings().all()
    except Exception as exc:
        logger.error(f"Error querying PostGIS spatial collisions: {exc}")
        # If database table is empty or error occurs, default safely to UNIQUE_LOCATION
        return (CollisionStatus.UNIQUE_LOCATION, None, None)

    if not rows:
        return (CollisionStatus.UNIQUE_LOCATION, None, None)

    # Evaluate matches
    potential_duplicate: POICollisionMatch | None = None
    nearby_parent: POICollisionMatch | None = None

    for row in rows:
        sim = float(row["name_similarity"])
        aliases = row["name_aliases"] or []

        # Check aliases similarity in python or if primary name match is high
        for alias in aliases:
            # Simple length/substring or approximate token overlap if pg_trgm didn't evaluate array
            if cand_name.lower() in alias.lower() or alias.lower() in cand_name.lower():
                sim = max(sim, 0.85)

        match_item = POICollisionMatch(
            id=row["id"],
            name=row["name"],
            name_aliases=aliases,
            poi_type=row["poi_type"],
            personal_rating=row["personal_rating"],
            distance_meters=round(float(row["distance_meters"]), 1),
            name_similarity=round(sim, 3),
            description=row["description"],
            iptc_city=row["iptc_city"],
            iptc_province_state=row["iptc_province_state"],
            parent_poi_id=row["parent_poi_id"],
            category_tags=row.get("category_tags") or [],
        )

        # 1. Collision / Potential Duplicate: Distance <= radius AND similarity >= 0.60
        if sim >= 0.60 and potential_duplicate is None:
            potential_duplicate = match_item

        # 2. Nearby Parent / Nesting Candidate:
        # Distance <= radius, similarity < 0.60 AND existing POI is a macro-site
        geofence_ft = row["geofence_radius_ft"] or 500
        is_macro = (
            geofence_ft >= 2000
            or row["poi_type"] in ("site to see", "experience")
            or any(k in row["name"].lower() for k in ["park", "forest", "reserve", "campus", "district", "valley", "canyon", "island"])
        )

        if sim < 0.60 and is_macro and nearby_parent is None and row["parent_poi_id"] is None:
            nearby_parent = match_item

    if potential_duplicate:
        return (CollisionStatus.POTENTIAL_DUPLICATE, potential_duplicate, nearby_parent)
    elif nearby_parent:
        return (CollisionStatus.NEARBY_PARENT, None, nearby_parent)
    else:
        return (CollisionStatus.UNIQUE_LOCATION, None, None)
