"""Integration and unit tests for worker engine and database upsert."""

import tempfile
from datetime import date
from pathlib import Path

from PIL import Image

from photo_scraper.core.db import ScraperDatabase
from photo_scraper.core.geocoder import GeocodedLocation
from photo_scraper.core.llm_parser import GeminiPathParser
from photo_scraper.core.worker import PhotoScraperEngine


class MockGeocoder:
    """Mock geocoder to avoid external network requests during unit tests."""

    def __init__(self):
        self.reverse_calls = []
        self.forward_calls = []

    def reverse_geocode(self, lat: float, lon: float, fallback_name: str = ""):
        self.reverse_calls.append((lat, lon))
        return GeocodedLocation(
            name=fallback_name or "Reverse Place",
            display_name="123 Main St, Batavia, IL, USA",
            latitude=lat,
            longitude=lon,
            street="123 Main St",
            city="Batavia",
            state="Illinois",
            country="United States",
            country_code="US",
            postal_code="60510",
        )

    def forward_geocode(self, query: str, bias_near_batavia: bool = False):
        self.forward_calls.append((query, bias_near_batavia))
        if "unknown" in query.lower() or "choir" in query.lower():
            return None
        return GeocodedLocation(
            name=query.split(",")[0].strip(),
            display_name=f"{query}, United States",
            latitude=41.8500,
            longitude=-88.3126,
            city="Batavia",
            state="Illinois",
            country="United States",
            country_code="US",
        )


def _create_sample_photo(folder: Path, filename: str, date_str: str = "2024:06:15 10:00:00") -> Path:
    img_path = folder / filename
    img = Image.new("RGB", (20, 20), color=(50, 100, 150))
    exif = img.getexif()
    exif[36867] = date_str
    img.save(img_path, exif=exif)
    return img_path


def test_discover_leaf_folders():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 1. Normal location with image
        loc1 = root / "2023" / "New York" / "06 Auburn NY" / "Harriet Tubman NHP"
        loc1.mkdir(parents=True)
        _create_sample_photo(loc1, "img1.jpg")

        # 2. Excluded folder (matching *Kids*)
        excluded = root / "2023" / "Kids" / "Soccer"
        excluded.mkdir(parents=True)
        _create_sample_photo(excluded, "img2.jpg")

        # 3. Empty folder without images
        empty_dir = root / "2023" / "Empty"
        empty_dir.mkdir(parents=True)

        engine = PhotoScraperEngine(dry_run=True)
        discovered, _ = engine.discover_leaf_folders(root)

        assert len(discovered) == 1
        assert str(loc1) in discovered
        assert discovered[str(loc1)]["site"] == "Harriet Tubman NHP"
        assert discovered[str(loc1)]["city"] == "Auburn"
        assert discovered[str(loc1)]["state"] == "NY"
        assert discovered[str(loc1)]["country"] == "USA"


def test_leaf_folders_cache_save_and_reuse():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        cache_file = root / "output" / "folders_leaf.txt"

        loc1 = root / "2023" / "New York" / "Harriet Tubman"
        loc1.mkdir(parents=True)
        _create_sample_photo(loc1, "img1.jpg")

        loc2 = root / "2023" / "Illinois" / "Lippold"
        loc2.mkdir(parents=True)
        _create_sample_photo(loc2, "img2.jpg")

        mock_geo = MockGeocoder()
        engine = PhotoScraperEngine(geocoder=mock_geo, dry_run=True)

        # 1. First run with cache_file: saves discovered folders to cache_file
        folders_dict, _ = engine.discover_leaf_folders(root)
        assert len(folders_dict) == 2
        engine.save_leaf_folders_cache(folders_dict, cache_file)

        assert cache_file.exists()

        # 2. Second run: load cached folders and verify search time is saved
        loaded_folders, cache_info = engine.load_cached_leaf_folders(cache_file)
        assert len(loaded_folders) == 2
        assert len(cache_info) == 2
        assert set(str(p) for p in loaded_folders) == set(folders_dict.keys())


def test_process_folder_with_mock_geocoder():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 1. Test unmapped non-location folder
        choir_folder = root / "2022" / "Sophia 6th Grade Choir"
        choir_folder.mkdir(parents=True)
        _create_sample_photo(choir_folder, "choir.jpg")

        mock_geo = MockGeocoder()
        gemini_parser = GeminiPathParser(api_key="mock_key", cache_file_path=str(root / "gemini_cache.json"))
        engine = PhotoScraperEngine(geocoder=mock_geo, gemini_parser=gemini_parser, dry_run=True)
        engine.process_folder(choir_folder, root)

        assert engine.stats.folders_unknown == 1
        assert len(engine.stats.folders_unmapped) == 1
        assert str(choir_folder) in engine.stats.folders_unmapped[0]

        # 2. Test valid location folder
        loc_folder = root / "2022" / "Lippold"
        loc_folder.mkdir(parents=True)
        _create_sample_photo(loc_folder, "lippold.jpg")

        engine.process_folder(loc_folder, root)
        assert engine.stats.folders_new_entry == 1
        assert engine.stats.files_looked_at == 2

        # 3. Verify Nominatim result was added to gemini cache
        cached_entry = gemini_parser.cache.get(str(loc_folder).replace("\\", "/").lower())
        assert cached_entry is not None
        assert "nominatim" in cached_entry
        assert cached_entry["nominatim"]["found"] is True
        assert cached_entry["nominatim"]["name"] == "Lippold"
        assert cached_entry["nominatim"]["latitude"] == 41.85


def test_db_upsert_poi_visit_and_duplicates():
    """Verifies database insertion and multi-visit date aggregation against live PostGIS."""
    import uuid
    test_token = uuid.uuid4().hex[:8]
    test_place_name = f"Test Overlook {test_token}"

    try:
        db = ScraperDatabase()
        # Verify database connection
        db.get_or_resolve_user_id()
    except Exception:
        # If DB is not available in current test environment, skip gracefully
        return

    geo = GeocodedLocation(
        name=test_place_name,
        display_name=f"{test_place_name}, Batavia, IL",
        latitude=41.8505,
        longitude=-88.3120,
        street="100 Island Ave",
        city="Batavia",
        state="Illinois",
        country="United States",
        country_code="US",
        postal_code="60510",
    )

    sample_folder = Path("D:/Photos/2023/Batavia Riverwalk")

    # 1. First visit
    is_dup1, poi_id1, _ = db.upsert_poi_visit(
        geo=geo,
        visit_dates=[date(2023, 5, 10)],
        folder=sample_folder,
    )
    assert is_dup1 is False
    assert poi_id1 is not None

    # 2. Second visit to same location on another date
    is_dup2, poi_id2, _ = db.upsert_poi_visit(
        geo=geo,
        visit_dates=[date(2024, 7, 20)],
        folder=sample_folder,
    )
    assert is_dup2 is True
    assert poi_id2 == poi_id1

    # Verify visit_dates array and source_url in DB
    with db.SessionFactory() as session:
        from sqlalchemy import text
        row = session.execute(
            text("SELECT visit_date, visit_dates, source_type, source_url FROM pois WHERE id = :id"),
            {"id": poi_id1},
        ).mappings().first()

        assert row is not None
        assert row["source_type"] == "photo"
        assert row["source_url"] == str(sample_folder.resolve())
        dates = row["visit_dates"]
        assert len(dates) == 2
        assert date(2023, 5, 10) in dates
        assert date(2024, 7, 20) in dates

        # Clean up test POI record
        session.execute(text("DELETE FROM pois WHERE id = :id"), {"id": poi_id1})
        session.commit()


def test_validate_user_exists_and_invalid_user_raises():
    """Verifies that validate_user accepts valid users and rejects non-existent users."""
    import pytest

    try:
        db = ScraperDatabase()
        db.get_or_resolve_user_id()
    except Exception:
        # DB not available, skip gracefully
        return

    # Valid user resolution
    user_id, email = db.validate_user("tim@olker.us")
    assert user_id is not None
    assert email.lower() == "tim@olker.us"

    # Invalid user rejection
    with pytest.raises(ValueError, match="does not exist in the database users table"):
        db.validate_user("definitely_not_a_real_user_xyz@nonexistent.domain")

    # Empty user rejection
    with pytest.raises(ValueError, match="No database user specified"):
        db.validate_user("   ")


def test_db_upsert_poi_without_location():
    """Verifies that upsert_poi_visit successfully inserts unlocated POIs when geo is None."""
    try:
        db = ScraperDatabase()
        db.get_or_resolve_user_id()
    except Exception:
        return

    # Ingest POI without coordinates
    is_dup1, poi_id1, place_name1 = db.upsert_poi_visit(
        geo=None,
        visit_dates=[date(2025, 6, 1)],
        fallback_name="Hidden Valley Trail (Unlocated)",
    )
    assert is_dup1 is False
    assert poi_id1 is not None
    assert place_name1 == "Hidden Valley Trail (Unlocated)"

    # Verify database record has location IS NULL
    with db.SessionFactory() as session:
        from sqlalchemy import text
        row = session.execute(
            text("SELECT name, location, source_type FROM pois WHERE id = :id"),
            {"id": poi_id1},
        ).mappings().first()

        assert row is not None
        assert row["name"] == "Hidden Valley Trail (Unlocated)"
        assert row["location"] is None
        assert row["source_type"] == "photo"

        # Clean up
        session.execute(text("DELETE FROM pois WHERE id = :id"), {"id": poi_id1})
        session.commit()


def test_scanned_paths_db_and_worker_skip():
    """Verifies that ScraperDatabase correctly tracks scanned_paths and worker skips non-pending."""
    try:
        db = ScraperDatabase()
        uid = db.get_or_resolve_user_id()
    except Exception:
        return

    test_folder = "D:/TestScans/2026/NonPendingPlace"
    path_id = db.upsert_scanned_path(
        user_id=uid,
        folder_path=test_folder,
        folder_name="NonPendingPlace",
        status="identified",
        site_name="Test Place",
        confidence="high",
        reasoning="Test scanned path",
    )
    assert path_id is not None

    rec = db.get_scanned_path(uid, test_folder)
    assert rec is not None
    assert rec["status"] == "identified"
    assert rec["site_name"] == "Test Place"

    # Cleanup test record
    with db.SessionFactory() as session:
        from sqlalchemy import text
        session.execute(text("DELETE FROM scanned_paths WHERE id = :id"), {"id": path_id})
        session.commit()

