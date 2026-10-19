"""Unit tests for scanned photo paths and POI disassociation / merge endpoints."""

import io
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import get_db
from app.main import app
from app.models import POI, ScannedPath, User
from app.services.auth import get_current_user

TEST_USER = User(
    id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
    email="testuser@vistarae.com",
    hashed_password="fakehashedpassword",
    full_name="Test Traveler",
    is_active=True,
)


@pytest.mark.asyncio
async def test_list_scanned_paths():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Mock count query
    mock_db.scalar = AsyncMock(return_value=1)

    # Mock select query
    mock_path = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        poi_id=None,
        folder_path="D:/Photos/2023/Japan/Tokyo",
        folder_name="Tokyo",
        parent_folder="D:/Photos/2023/Japan",
        status="identified",
        site_name="Tokyo Tower",
        city="Tokyo",
        state="Tokyo",
        country="Japan",
        country_code="JP",
        latitude=35.6586,
        longitude=139.7454,
        confidence="high",
        reasoning="Identified iconic landmark",
        photo_count=25,
        earliest_date=date(2023, 4, 1),
        latest_date=date(2023, 4, 5),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    mock_results = [(mock_path, "Tokyo Tower POI")]
    mock_execute = MagicMock()
    mock_execute.all.return_value = mock_results
    mock_db.execute = AsyncMock(return_value=mock_execute)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/scanned-paths?status=identified")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["folder_name"] == "Tokyo"
    assert data["items"][0]["poi_name"] == "Tokyo Tower POI"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_batch_update_scanned_paths():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    path1 = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        folder_path="D:/Photos/2023/Unknown1",
        folder_name="Unknown1",
        status="pending",
    )
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [path1]
    mock_db.scalars = AsyncMock(return_value=mock_scalars)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/scanned-paths/batch-update",
            json={
                "path_ids": [str(path1.id)],
                "status": "skipped",
                "city": "Batavia",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1
    assert path1.status == "skipped"
    assert path1.city == "Batavia"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disassociate_and_split():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    old_poi_id = uuid.uuid4()
    path_id = uuid.uuid4()
    sp = ScannedPath(
        id=path_id,
        user_id=TEST_USER.id,
        poi_id=old_poi_id,
        folder_path="D:/Photos/2023/Park Walk",
        folder_name="Park Walk",
        site_name="Walk at Park",
        status="identified",
    )

    mock_db.scalar = AsyncMock(return_value=sp)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/api/v1/scanned-paths/{path_id}/disassociate-and-split")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["old_poi_id"] == str(old_poi_id)
    assert data["new_poi_name"] == "Walk at Park"
    assert sp.status == "location unknown"
    assert sp.poi_id != old_poi_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_merge_pois():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    source_id = uuid.uuid4()
    target_id = uuid.uuid4()

    source_poi = POI(
        id=source_id,
        user_id=TEST_USER.id,
        name="Source Place",
        category_tags=["nature"],
        visit_dates=[date(2023, 1, 1)],
    )
    target_poi = POI(
        id=target_id,
        user_id=TEST_USER.id,
        name="Target Place",
        category_tags=["hiking"],
        visit_dates=[date(2023, 2, 1)],
    )

    async def mock_scalar_side_effect(stmt):
        stmt_str = str(stmt)
        if str(source_id) in stmt_str or "source" in stmt_str:
            return source_poi
        return target_poi

    mock_db.scalar = AsyncMock(side_effect=[source_poi, target_poi])
    mock_exec = MagicMock()
    mock_exec.rowcount = 2
    mock_db.execute = AsyncMock(return_value=mock_exec)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/merge",
            json={"source_poi_id": str(source_id), "target_poi_id": str(target_id)},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["target_poi_name"] == "Target Place"
    assert data["paths_reassigned_count"] == 2
    assert "nature" in target_poi.category_tags
    assert "hiking" in target_poi.category_tags

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_granular_poi_merge():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    kept_id = uuid.uuid4()
    deleted_id = uuid.uuid4()
    list_id = uuid.uuid4()
    path_id = uuid.uuid4()

    deleted_poi = POI(
        id=deleted_id,
        user_id=TEST_USER.id,
        name="Deleted Place",
        poi_type="lodging",
        personal_rating=5,
        category_tags=["tag-from-deleted"],
        visit_dates=[date(2022, 5, 10)],
    )
    kept_poi = POI(
        id=kept_id,
        user_id=TEST_USER.id,
        name="Kept Place",
        poi_type="site to see",
        personal_rating=2,
        category_tags=["tag-from-kept"],
        visit_dates=[date(2021, 1, 1)],
    )

    mock_db.scalar = AsyncMock(side_effect=[deleted_poi, kept_poi])
    mock_exec = MagicMock()
    mock_exec.rowcount = 1
    mock_db.execute = AsyncMock(return_value=mock_exec)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/pois/merge",
            json={
                "kept_poi_id": str(kept_id),
                "deleted_poi_id": str(deleted_id),
                "name": "Unified Place Name",
                "personal_rating": 5,
                "poi_type": "experience",
                "latitude": 41.9028,
                "longitude": 12.4964,
                "iptc_city": "Rome",
                "iptc_country_code": "IT",
                "visit_dates": ["2022-05-10", "2024-07-15"],
                "category_tags": ["tag-from-deleted", "custom-tag"],
                "list_ids": [str(list_id)],
                "selected_scanned_path_ids": [str(path_id)],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["target_poi_name"] == "Unified Place Name"
    assert data["kept_poi_id"] == str(kept_id)
    assert data["deleted_poi_id"] == str(deleted_id)

    # Check updated fields on kept_poi
    assert kept_poi.name == "Unified Place Name"
    assert kept_poi.personal_rating == 5
    assert kept_poi.poi_type == "experience"
    assert kept_poi.iptc_city == "Rome"
    assert kept_poi.iptc_country_code == "IT"
    assert kept_poi.visit_dates == [date(2022, 5, 10), date(2024, 7, 15)]
    assert kept_poi.visited is True
    assert kept_poi.category_tags == ["tag-from-deleted", "custom-tag"]
    assert "POINT(12.4964 41.9028)" in str(kept_poi.location)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scanned_path_hidden_status_and_patch():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    path_id = uuid.uuid4()
    mock_path = ScannedPath(
        id=path_id,
        user_id=TEST_USER.id,
        folder_path="D:/Photos/2023/IgnoredFolder",
        folder_name="IgnoredFolder",
        status="skipped",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    mock_db.scalar = AsyncMock(return_value=mock_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Patch status to hidden
        resp = await client.patch(f"/api/v1/scanned-paths/{path_id}", json={"status": "hidden"})
        assert resp.status_code == 200
        assert mock_path.status == "hidden"

        # Patch status back to skipped
        resp = await client.patch(f"/api/v1/scanned-paths/{path_id}", json={"status": "skipped"})
        assert resp.status_code == 200
        assert mock_path.status == "skipped"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lookup_scanned_path_details():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    path_id = uuid.uuid4()
    mock_path = ScannedPath(
        id=path_id,
        user_id=TEST_USER.id,
        folder_path="D:/Photos/2002-04-15_Museum",
        folder_name="2002-04-15_Museum",
        site_name="Art Museum",
        city="Chicago",
        state="Illinois",
        country="United States",
        latitude=41.8796,
        longitude=-87.6237,
        earliest_date=None,
        status="skipped",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    mock_db.scalar = AsyncMock(return_value=mock_path)

    with patch(
        "app.routers.scanned_paths.lookup_and_enrich_place",
        new=AsyncMock(
            return_value={
                "place_name": "Art Museum",
                "category_tags": ["museum", "historic", "art"],
                "website_official": "https://www.artic.edu",
                "phone_number": "+1 312-443-3600",
                "description": "Renowned art institute in Chicago",
                "poi_type": "site to see",
                "indoor_outdoor": "Indoor",
                "cost_tier": "$$",
                "city": "Chicago",
                "state": "Illinois",
                "country": "United States",
                "country_code": "US",
                "latitude": 41.8796,
                "longitude": -87.6237,
            }
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/scanned-paths/{path_id}/lookup-details")

    assert resp.status_code == 200
    data = resp.json()
    assert data["path_id"] == str(path_id)
    assert data["website_official"] == "https://www.artic.edu"
    assert data["phone_number"] == "+1 312-443-3600"
    assert "museum" in data["category_tags"]
    # Photo date resolved from folder path regex 2002-04-15
    assert data["visit_date_formatted"] == "2002-04-15"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lookup_generic_poi_details():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with patch(
        "app.routers.scanned_paths.lookup_and_enrich_place",
        new=AsyncMock(
            return_value={
                "place_name": "Field Museum",
                "category_tags": ["museum", "natural history"],
                "website_official": "https://www.fieldmuseum.org",
                "phone_number": "+1 312-922-9410",
                "description": "World-class natural history museum",
                "poi_type": "site to see",
                "indoor_outdoor": "Indoor",
                "cost_tier": "$$",
                "city": "Chicago",
                "state": "Illinois",
                "country": "United States",
                "country_code": "US",
                "latitude": 41.8663,
                "longitude": -87.6170,
            }
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/pois/lookup-details",
                json={
                    "place_name": "Field Museum",
                    "city": "Chicago",
                    "state": "Illinois",
                    "country": "United States",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["place_name"] == "Field Museum"
    assert data["website_official"] == "https://www.fieldmuseum.org"
    assert data["phone_number"] == "+1 312-922-9410"
    assert "natural history" in data["category_tags"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_poi_disassociates_scanned_paths():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi_id = uuid.uuid4()
    mock_poi = MagicMock(id=poi_id, user_id=TEST_USER.id, name="Test National Park")
    mock_db.scalar = AsyncMock(return_value=mock_poi)

    sp1 = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        poi_id=poi_id,
        folder_path="D:/Photos/2023-08-01_Park",
        folder_name="2023-08-01_Park",
        status="identified",
        latitude=37.77,
        longitude=-119.5,
    )
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sp1]
    mock_db.scalars = AsyncMock(return_value=mock_scalars)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/pois/{poi_id}")

    assert resp.status_code == 204
    mock_db.delete.assert_called_once_with(mock_poi)
    assert sp1.poi_id is None
    assert sp1.status == "location unknown"
    assert sp1.latitude is None
    assert sp1.longitude is None
    assert "Test National Park" in sp1.reasoning

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_photo_folder_conflict_detection():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1_id = uuid.uuid4()
    poi2_id = uuid.uuid4()
    poi1 = POI(
        id=poi1_id, user_id=TEST_USER.id, name="POI One", source_url="", poi_type="site to see"
    )
    poi2 = POI(
        id=poi2_id,
        user_id=TEST_USER.id,
        name="POI Two",
        source_url="D:/Photos/SharedTrip",
        poi_type="site to see",
    )

    # Scanned path exists and is linked to POI Two
    sp = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        poi_id=poi2_id,
        folder_path="D:/Photos/SharedTrip",
        folder_name="SharedTrip",
        status="identified",
    )

    # 1. Test check action detecting conflict
    # When querying for POI 1:
    async def mock_scalar(query, *args, **kwargs):
        q_str = str(query)
        if "pois.id = :id_1" in q_str or "WHERE pois.id = " in q_str:
            return poi1
        if "scanned_paths.user_id = " in q_str:
            return sp
        return None

    async def mock_execute(query, *args, **kwargs):
        m = MagicMock()
        # other pois with source url
        m.scalars.return_value.all.return_value = [poi2]
        return m

    mock_db.scalar = AsyncMock(side_effect=mock_scalar)
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check action (default)
        resp = await client.post(
            f"/api/v1/pois/{poi1_id}/photo-folder",
            json={"folder_path": "D:/Photos/SharedTrip", "action": "check"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conflict"] is True
        assert data["success"] is False
        assert len(data["conflicting_pois"]) >= 1
        assert data["conflicting_pois"][0]["name"] == "POI Two"

        # 2. Test share_and_flag action
        resp_flag = await client.post(
            f"/api/v1/pois/{poi1_id}/photo-folder",
            json={"folder_path": "D:/Photos/SharedTrip", "action": "share_and_flag"},
        )
        assert resp_flag.status_code == 200
        data_flag = resp_flag.json()
        assert data_flag["success"] is True
        assert data_flag["conflict"] is True
        assert sp.has_conflict is True
        assert poi1_id in sp.conflict_poi_ids

        # 3. Test reassign action
        resp_reassign = await client.post(
            f"/api/v1/pois/{poi1_id}/photo-folder",
            json={"folder_path": "D:/Photos/SharedTrip", "action": "reassign"},
        )
        assert resp_reassign.status_code == 200
        data_reassign = resp_reassign.json()
        assert data_reassign["success"] is True
        assert data_reassign["conflict"] is False
        assert sp.poi_id == poi1_id
        assert poi1_id not in sp.conflict_poi_ids

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disassociate_scanned_path():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1_id = uuid.uuid4()
    poi2_id = uuid.uuid4()
    path_id = uuid.uuid4()

    sp = ScannedPath(
        id=path_id,
        user_id=TEST_USER.id,
        poi_id=poi1_id,
        conflict_poi_ids=[poi2_id],
        has_conflict=True,
        conflict_note="Conflict between 1 and 2",
        folder_path="D:/Photos/Trip",
        folder_name="Trip",
    )
    mock_db.scalar = AsyncMock(return_value=sp)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Disassociate from primary POI 1 -> should promote POI 2 and resolve conflict
        resp = await client.post(
            f"/api/v1/scanned-paths/{path_id}/disassociate", json={"poi_id": str(poi1_id)}
        )
        assert resp.status_code == 200
        assert sp.poi_id == poi2_id
        assert sp.has_conflict is False
        assert len(sp.conflict_poi_ids) == 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspect_photo_path_duplicate_aborted():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi1_id = uuid.uuid4()
    poi2_id = uuid.uuid4()
    path_id = uuid.uuid4()

    sp = ScannedPath(
        id=path_id,
        user_id=TEST_USER.id,
        poi_id=poi2_id,
        folder_path="D:/Photos/ExistingTrip",
        folder_name="ExistingTrip",
    )
    conflicting_poi = POI(
        id=poi2_id,
        user_id=TEST_USER.id,
        name="Existing Rome Place",
        poi_type="site to see",
        iptc_city="Rome",
        iptc_country_code="IT",
    )

    # First execute call: find ScannedPath
    # Second execute call: find POI by source_url (empty)
    # Third execute call: find POI details for conflicting_poi_ids
    mock_res_sp = MagicMock()
    mock_res_sp.scalars.return_value.all.return_value = [sp]

    mock_res_url = MagicMock()
    mock_res_url.scalars.return_value.all.return_value = []

    mock_res_cp = MagicMock()
    mock_res_cp.scalars.return_value.all.return_value = [conflicting_poi]

    mock_db.execute = AsyncMock(side_effect=[mock_res_sp, mock_res_url, mock_res_cp])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/pois/{poi1_id}/inspect-photo-path",
            json={"file_path": "D:/Photos/ExistingTrip/photo1.jpg"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["status"] == "duplicate_aborted"
        assert len(data["conflicting_pois"]) == 1
        assert data["conflicting_pois"][0]["name"] == "Existing Rome Place"
        assert "already in use" in data["message"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspect_photo_upload_with_exif():
    import io

    from PIL import ExifTags, Image

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Create image in memory with EXIF date, GPS, and XPKeywords tags
    img = Image.new("RGB", (50, 50), color="blue")
    exif = img.getexif()
    exif[ExifTags.Base.DateTimeOriginal] = "2024:05:20 10:15:00"

    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps_ifd[1] = "N"
    gps_ifd[2] = (41.0, 53.0, 31.0)
    gps_ifd[3] = "E"
    gps_ifd[4] = (12.0, 29.0, 32.0)

    # XPKeywords (tag 40094, UTF-16LE)
    exif[40094] = "Colosseum;Ancient Rome;History".encode("utf-16le")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    buf.seek(0)

    poi_id = uuid.uuid4()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/pois/{poi_id}/inspect-photo-upload",
            files={"file": ("colosseum_test.jpg", buf, "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "metadata_found"
        assert data["date_taken"] == "2024-05-20"
        assert round(data["latitude"], 2) == 41.89
        assert round(data["longitude"], 2) == 12.49
        assert "Colosseum" in data["tags"]
        assert "History" in data["tags"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_photo_folder_file_normalization():
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    poi_id = uuid.uuid4()
    poi = POI(id=poi_id, user_id=TEST_USER.id, name="Test Park", source_url=None)
    mock_db.scalar.side_effect = [poi, None]

    async def mock_execute(query, *args, **kwargs):
        m = MagicMock()
        m.scalars.return_value.all.return_value = []
        return m

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Supply path to a specific photo inside a folder
        resp = await client.post(
            f"/api/v1/pois/{poi_id}/photo-folder",
            json={"folder_path": "D:/Photos/Yellowstone/IMG_0042.jpg", "action": "check"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Verify it normalized to parent directory
        assert "IMG_0042.jpg" not in data["folder_path"]
        assert "Yellowstone" in data["folder_path"]
        assert data["folder_name"] == "Yellowstone"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspect_photo_upload_auto_locates_folder(tmp_path):
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Create dummy folder with a photo inside on disk
    test_folder = tmp_path / "Trip2024"
    test_folder.mkdir()
    photo_file = test_folder / "test_photo.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    poi_id = uuid.uuid4()
    sp = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        poi_id=poi_id,
        folder_path=str(test_folder),
        folder_name="Trip2024",
        status="identified",
    )

    # Mock DB query for scanned_paths to return test_folder for paths query, and sp for entity query
    async def mock_execute(query, *args, **kwargs):
        m = MagicMock()
        q_str = str(query).lower()
        if q_str.startswith("select scanned_paths.folder_path"):
            m.scalars.return_value.all.return_value = [str(test_folder)]
        elif "from scanned_paths" in q_str:
            m.scalars.return_value.all.return_value = [sp]
        else:
            m.scalars.return_value.all.return_value = []
        return m

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload photo without folder_path; system should discover it
        resp = await client.post(
            f"/api/v1/pois/{poi_id}/inspect-photo-upload",
            files={
                "file": (
                    "test_photo.jpg",
                    io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 20),
                    "image/jpeg",
                )
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["folder_path"] == str(test_folder).rstrip("\\/")
        assert data["file_name"] == "test_photo.jpg"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_inspect_photo_upload_resolves_nested_directory_and_already_linked(tmp_path):
    import io

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    # Parent root folder scanned
    root_folder = tmp_path / "2021" / "Trip"
    nested_subfolder = root_folder / "SubPlace"
    nested_subfolder.mkdir(parents=True)
    photo_file = nested_subfolder / "nested_photo.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    poi_id = uuid.uuid4()
    sp = ScannedPath(
        id=uuid.uuid4(),
        user_id=TEST_USER.id,
        poi_id=poi_id,
        folder_path=str(nested_subfolder),
        folder_name="SubPlace",
        status="identified",
    )

    async def mock_execute(query, *args, **kwargs):
        m = MagicMock()
        q_str = str(query).lower()
        if q_str.startswith("select scanned_paths.folder_path"):
            m.scalars.return_value.all.return_value = [str(root_folder)]
        elif "from scanned_paths" in q_str:
            m.scalars.return_value.all.return_value = [sp]
        else:
            m.scalars.return_value.all.return_value = []
        return m

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.get = AsyncMock(return_value=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/pois/{poi_id}/inspect-photo-upload",
            files={
                "file": (
                    "nested_photo.jpg",
                    io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 20),
                    "image/jpeg",
                )
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["folder_path"] == str(nested_subfolder).rstrip("\\/")
        assert data["already_linked"] is True

    app.dependency_overrides.clear()
