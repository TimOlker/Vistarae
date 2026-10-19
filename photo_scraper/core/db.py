"""Database operations for POI upsert and multi-visit tracking."""

import logging
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from photo_scraper.core.config import settings
from photo_scraper.core.geocoder import GeocodedLocation

logger = logging.getLogger("vistarae.photo_scraper.db")


class ScraperDatabase:
    """Manages database connections, user resolution, and POI upserts."""

    def __init__(self, db_url: str | None = None):
        url = db_url or settings.DATABASE_URL_SYNC
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        self.engine: Engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self._user_id: uuid.UUID | None = None

    def validate_user(self, identifier: str | None = None) -> tuple[uuid.UUID, str]:
        """Validates that target user exists and is active in the database.

        Raises ValueError if user is missing, inactive, or not found.
        Returns:
            (user_id, email)
        """
        target = (identifier or settings.target_db_user).strip()
        if not target:
            raise ValueError(
                "No database user specified. Please set PHOTOSCRAPER_DB_USER in .env or pass --db-user."
            )

        with self.SessionFactory() as session:
            # Check by email or UUID
            is_uuid = False
            try:
                val_uuid = uuid.UUID(target)
                is_uuid = True
            except ValueError:
                pass

            if is_uuid:
                row = session.execute(
                    text("SELECT id, email, is_active FROM users WHERE id = :uid LIMIT 1"),
                    {"uid": val_uuid},
                ).first()
            else:
                row = session.execute(
                    text("SELECT id, email, is_active FROM users WHERE lower(email) = lower(:email) LIMIT 1"),
                    {"email": target},
                ).first()

            if not row:
                raise ValueError(
                    f"Target user '{target}' does not exist in the database users table. "
                    "Make sure PHOTOSCRAPER_DB_USER is a valid registered user."
                )

            user_id, email, is_active = row[0], row[1], row[2]
            if is_active is False:
                raise ValueError(f"Target user '{target}' ({user_id}) is marked as inactive in the database.")

            self._user_id = user_id
            logger.info(f"Verified valid database user: '{email}' (UUID: {user_id})")
            return user_id, email

    def get_or_resolve_user_id(self, email: str | None = None) -> uuid.UUID:
        """Finds or resolves the target user UUID for saved POIs."""
        if self._user_id:
            return self._user_id

        user_id, _ = self.validate_user(email)
        return user_id

    def upsert_poi_visit(
        self,
        geo: GeocodedLocation | None,
        visit_dates: list[date],
        user_id: uuid.UUID | None = None,
        radius_meters: float = 500.0,
        folder: str | None = None,
        fallback_name: str | None = None,
    ) -> tuple[bool, uuid.UUID, str]:
        """Upserts a visited location into the database.

        If coordinates are present, checks for collision within radius_meters.
        If coordinates are absent, checks for match by exact name.
        Inserts new POI record with location=NULL if not matched and coordinates absent.

        Returns:
            (is_duplicate, poi_id, place_name)
        """
        uid = user_id or self.get_or_resolve_user_id()

        # Format unique dates sorted
        unique_dates = sorted({d for d in visit_dates if d is not None})
        primary_date = unique_dates[0] if unique_dates else None

        cand_name = (geo.name if geo and geo.name else fallback_name) or "Unknown Location"
        disk_path = str(Path(folder).resolve()) if folder else f"file://{cand_name}"
        has_coords = bool(
            geo is not None
            and geo.latitude is not None
            and geo.longitude is not None
            and (geo.latitude != 0.0 or geo.longitude != 0.0)
        )

        with self.SessionFactory() as session:
            matched_poi_id: uuid.UUID | None = None
            matched_poi_name: str = cand_name

            if has_coords:
                # 1a. Check for existing POI match using PostGIS spatial radius & name similarity
                collision_query = text("""
                    SELECT
                        p.id,
                        p.name,
                        p.visit_date,
                        p.visit_dates,
                        ST_Distance(p.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_meters,
                        similarity(p.name, :cand_name) AS name_similarity
                    FROM pois p
                    WHERE p.location IS NOT NULL
                      AND ST_DWithin(p.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_meters)
                      AND (p.user_id = :user_id OR :user_id IS NULL)
                    ORDER BY distance_meters ASC
                    LIMIT 5;
                """)

                rows = session.execute(
                    collision_query,
                    {
                        "lng": geo.longitude,
                        "lat": geo.latitude,
                        "cand_name": cand_name,
                        "radius_meters": radius_meters,
                        "user_id": uid,
                    },
                ).mappings().all()

                for row in rows:
                    dist = float(row["distance_meters"])
                    sim = float(row["name_similarity"])
                    existing_name = str(row["name"]).lower()
                    c_name_lower = cand_name.lower()
                    is_name_match = (
                        sim >= 0.60
                        or c_name_lower in existing_name
                        or existing_name in c_name_lower
                    )

                    if dist <= radius_meters and is_name_match:
                        matched_poi_id = row["id"]
                        matched_poi_name = row["name"]
                        break
            else:
                # 1b. Check for existing unlocated POI with exact name
                collision_query = text("""
                    SELECT id, name, visit_date, visit_dates
                    FROM pois
                    WHERE lower(name) = lower(:cand_name)
                      AND (user_id = :user_id OR :user_id IS NULL)
                    LIMIT 1;
                """)
                row = session.execute(
                    collision_query,
                    {"cand_name": cand_name, "user_id": uid},
                ).mappings().first()
                if row:
                    matched_poi_id = row["id"]
                    matched_poi_name = row["name"]

            if matched_poi_id:
                # 2. Existing Entry: Update visit_dates array and ensure visited=True, upgrading source_url if needed
                update_query = text("""
                    UPDATE pois
                    SET
                        visited = TRUE,
                        visit_date = COALESCE(visit_date, :primary_date),
                        source_url = CASE WHEN (source_url IS NULL OR source_url LIKE 'file://%') AND :source_url != '' THEN :source_url ELSE source_url END,
                        visit_dates = ARRAY(
                            SELECT DISTINCT d
                            FROM unnest(array_cat(COALESCE(visit_dates, CAST(ARRAY[] AS date[])), CAST(:new_dates AS date[]))) AS d
                            ORDER BY d ASC
                        )
                    WHERE id = :poi_id
                    RETURNING id, name;
                """)

                session.execute(
                    update_query,
                    {
                        "poi_id": matched_poi_id,
                        "primary_date": primary_date,
                        "source_url": disk_path,
                        "new_dates": unique_dates,
                    },
                )
                session.commit()
                logger.info(f"Duplicate location updated: '{matched_poi_name}' (ID: {matched_poi_id}) with {len(unique_dates)} dates - {folder}")
                return (True, matched_poi_id, matched_poi_name)

            # 3. New Entry: Insert new POI record
            new_id = uuid.uuid4()
            insert_query = text("""
                INSERT INTO pois (
                    id,
                    user_id,
                    name,
                    location,
                    source_url,
                    source_type,
                    iptc_sublocation,
                    iptc_city,
                    iptc_province_state,
                    iptc_country_code,
                    iptc_world_region,
                    iptc_zip_code,
                    visited,
                    visit_date,
                    visit_dates,
                    poi_type,
                    created_at
                )
                VALUES (
                    :id,
                    :user_id,
                    :name,
                    CASE WHEN :has_coords THEN ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography ELSE NULL END,
                    :source_url,
                    :source_type,
                    :sublocation,
                    :city,
                    :state,
                    :country_code,
                    :country,
                    :zip_code,
                    TRUE,
                    :visit_date,
                    :visit_dates,
                    'site to see',
                    NOW()
                )
                RETURNING id;
            """)

            session.execute(
                insert_query,
                {
                    "id": new_id,
                    "user_id": uid,
                    "name": cand_name,
                    "has_coords": has_coords,
                    "lat": geo.latitude if has_coords else 0.0,
                    "lng": geo.longitude if has_coords else 0.0,
                    "source_url": disk_path,
                    "source_type": "photo",
                    "sublocation": geo.street if geo else None,
                    "city": geo.city if geo else None,
                    "state": geo.state if geo else None,
                    "country_code": (geo.country_code or "US") if geo else None,
                    "country": geo.country if geo else None,
                    "zip_code": geo.postal_code if geo else None,
                    "visit_date": primary_date,
                    "visit_dates": unique_dates,
                },
            )
            session.commit()
            coord_str = f"at ({geo.latitude}, {geo.longitude})" if has_coords else "(without location)"
            logger.info(f"New POI created: '{cand_name}' (ID: {new_id}) {coord_str} - {folder}")
            return (False, new_id, cand_name)

    def get_scanned_path(self, user_id: uuid.UUID, folder_path: str) -> dict | None:
        """Retrieves scanned path record if exists."""
        clean_path = str(Path(folder_path).resolve())
        with self.SessionFactory() as session:
            stmt = text("""
                SELECT id, user_id, poi_id, folder_path, status, site_name, city, state, country, latitude, longitude, confidence, reasoning
                FROM scanned_paths
                WHERE user_id = :uid AND (folder_path = :clean_path OR folder_path = :raw_path)
                LIMIT 1;
            """)
            row = session.execute(stmt, {"uid": user_id, "clean_path": clean_path, "raw_path": folder_path}).mappings().first()
            if row:
                return dict(row)
        return None

    def upsert_scanned_path(
        self,
        user_id: uuid.UUID,
        folder_path: str,
        folder_name: str,
        status: str = "pending",
        parent_folder: str | None = None,
        site_name: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        country_code: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        confidence: str = "medium",
        reasoning: str | None = None,
        raw_llm_json: str | None = None,
        nominatim_raw: str | None = None,
        photo_count: int = 0,
        earliest_date: date | None = None,
        latest_date: date | None = None,
        poi_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Upserts a record into scanned_paths."""
        clean_path = str(Path(folder_path).resolve())
        parent_dir = parent_folder or (str(Path(clean_path).parent) if Path(clean_path).parent else None)
        path_uuid = uuid.uuid4()

        with self.SessionFactory() as session:
            stmt = text("""
                INSERT INTO scanned_paths (
                    id, user_id, poi_id, folder_path, folder_name, parent_folder,
                    status, site_name, city, state, country, country_code,
                    latitude, longitude, confidence, reasoning, raw_llm_json,
                    nominatim_raw, photo_count, earliest_date, latest_date,
                    created_at, updated_at
                ) VALUES (
                    :id, :user_id, :poi_id, :folder_path, :folder_name, :parent_folder,
                    :status, :site_name, :city, :state, :country, :country_code,
                    :latitude, :longitude, :confidence, :reasoning, CAST(:raw_llm_json AS jsonb),
                    CAST(:nominatim_raw AS jsonb), :photo_count, :earliest_date, :latest_date,
                    NOW(), NOW()
                )
                ON CONFLICT (user_id, folder_path) DO UPDATE SET
                    poi_id = COALESCE(EXCLUDED.poi_id, scanned_paths.poi_id),
                    status = EXCLUDED.status,
                    site_name = COALESCE(EXCLUDED.site_name, scanned_paths.site_name),
                    city = COALESCE(EXCLUDED.city, scanned_paths.city),
                    state = COALESCE(EXCLUDED.state, scanned_paths.state),
                    country = COALESCE(EXCLUDED.country, scanned_paths.country),
                    country_code = COALESCE(EXCLUDED.country_code, scanned_paths.country_code),
                    latitude = COALESCE(EXCLUDED.latitude, scanned_paths.latitude),
                    longitude = COALESCE(EXCLUDED.longitude, scanned_paths.longitude),
                    confidence = EXCLUDED.confidence,
                    reasoning = COALESCE(EXCLUDED.reasoning, scanned_paths.reasoning),
                    raw_llm_json = COALESCE(EXCLUDED.raw_llm_json, scanned_paths.raw_llm_json),
                    nominatim_raw = COALESCE(EXCLUDED.nominatim_raw, scanned_paths.nominatim_raw),
                    photo_count = GREATEST(EXCLUDED.photo_count, scanned_paths.photo_count),
                    earliest_date = COALESCE(EXCLUDED.earliest_date, scanned_paths.earliest_date),
                    latest_date = COALESCE(EXCLUDED.latest_date, scanned_paths.latest_date),
                    updated_at = NOW()
                RETURNING id;
            """)
            row = session.execute(
                stmt,
                {
                    "id": path_uuid,
                    "user_id": user_id,
                    "poi_id": poi_id,
                    "folder_path": clean_path,
                    "folder_name": folder_name,
                    "parent_folder": parent_dir,
                    "status": status,
                    "site_name": site_name,
                    "city": city,
                    "state": state,
                    "country": country,
                    "country_code": country_code,
                    "latitude": latitude,
                    "longitude": longitude,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "raw_llm_json": raw_llm_json,
                    "nominatim_raw": nominatim_raw,
                    "photo_count": photo_count,
                    "earliest_date": earliest_date,
                    "latest_date": latest_date,
                },
            ).first()
            session.commit()
            return row[0] if row else path_uuid

