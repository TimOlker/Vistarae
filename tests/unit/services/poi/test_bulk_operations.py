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


"""Unit tests for atomic bulk mutations, address preservation, and 500-batch ceiling validation (T-026).

Validates:
- POST /api/pois/bulk-edit (REQ-MAIN-027 to REQ-MAIN-033, SC-004)
- POST /api/pois/bulk-delete (REQ-MAIN-034, SC-004)
- 500-POI batch limit ceiling validation returning RFC 7807 422 (REQ-MAIN-035, SC-007)
- Non-destructive primary address updates modifying addresses[0] and preserving secondary records (REQ-MAIN-033, SC-006)
- Lifecycle recomputation on visited dates and visit again toggles (REQ-MAIN-028, REQ-MAIN-029)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.session import get_db_session
from vistarae_core.adapters.db.tables import POITable
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.domain.entities import User
from vistarae_core.domain.value_objects import VisitState
from vistarae_core.ports.repositories import IPOIRepository

from services.poi.dependencies import get_current_user, get_poi_repo
from services.poi.main import app


@pytest.fixture
def current_user() -> User:
    """Fixture providing a mock authenticated tenant user."""
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        cognito_sub="sub-traveler-1",
        email="traveler@example.com",
        full_name="Atlas Voyager",
        is_active=True,
    )


@pytest.fixture
def mock_poi_repo() -> AsyncMock:
    """Fixture providing an AsyncMock for IPOIRepository."""
    repo = AsyncMock(spec=IPOIRepository)
    repo.bulk_edit = AsyncMock(return_value=2)
    repo.bulk_delete = AsyncMock(return_value=3)
    repo.bulk_attach_tags = AsyncMock(return_value=2)
    repo.bulk_detach_tags = AsyncMock(return_value=2)
    repo.bulk_attach_lists = AsyncMock(return_value=3)
    repo.bulk_detach_lists = AsyncMock(return_value=3)
    return repo


@pytest.fixture
def client(current_user: User, mock_poi_repo: AsyncMock) -> TestClient:
    """Fixture providing a TestClient with overridden dependencies."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# Route & Contract Tests
# -----------------------------------------------------------------------------


def test_bulk_edit_set_rating(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk set_rating modifies records and returns modified count."""
    poi_ids = [str(uuid4()), str(uuid4())]
    payload = {
        "poi_ids": poi_ids,
        "action": "set_rating",
        "payload": {"rating": 5},
    }

    res = client.post("/api/pois/bulk-edit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["modified_count"] == 2
    mock_poi_repo.bulk_edit.assert_awaited_once()


def test_bulk_edit_add_visit_date(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk add_visit_date passes date payload to repository."""
    poi_ids = [str(uuid4())]
    payload = {
        "poi_ids": poi_ids,
        "action": "add_visit_date",
        "payload": {"visit_date": "2026-10-15"},
    }

    res = client.post("/api/pois/bulk-edit", json=payload)
    assert res.status_code == 200
    assert res.json()["modified_count"] == 2
    mock_poi_repo.bulk_edit.assert_awaited_once()


def test_bulk_edit_set_visit_again(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk set_visit_again passes boolean flag."""
    poi_ids = [str(uuid4())]
    payload = {
        "poi_ids": poi_ids,
        "action": "set_visit_again",
        "payload": {"want_to_visit_again": True},
    }

    res = client.post("/api/pois/bulk-edit", json=payload)
    assert res.status_code == 200
    mock_poi_repo.bulk_edit.assert_awaited_once()


def test_bulk_edit_tags(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk add_tag and remove_tag route correctly."""
    poi_ids = [str(uuid4())]
    # Add tag
    res_add = client.post(
        "/api/pois/bulk-edit",
        json={
            "poi_ids": poi_ids,
            "action": "add_tag",
            "payload": {"tag_name": "historical"},
        },
    )
    assert res_add.status_code == 200

    # Remove tag
    res_rem = client.post(
        "/api/pois/bulk-edit",
        json={
            "poi_ids": poi_ids,
            "action": "remove_tag",
            "payload": {"tag_name": "historical"},
        },
    )
    assert res_rem.status_code == 200


def test_bulk_edit_lists(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk add_to_list and remove_from_list pass list_id."""
    poi_ids = [str(uuid4())]
    list_id = str(uuid4())
    res_add = client.post(
        "/api/pois/bulk-edit",
        json={
            "poi_ids": poi_ids,
            "action": "add_to_list",
            "payload": {"list_id": list_id},
        },
    )
    assert res_add.status_code == 200


def test_bulk_edit_update_address(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk update_address routes address parameters."""
    poi_ids = [str(uuid4())]
    res = client.post(
        "/api/pois/bulk-edit",
        json={
            "poi_ids": poi_ids,
            "action": "update_address",
            "payload": {
                "address": {
                    "city": "Kyoto",
                    "state_province": "Kyoto",
                    "country": "Japan",
                    "clear_fields": [],
                }
            },
        },
    )
    assert res.status_code == 200
    assert res.json()["modified_count"] == 2


def test_bulk_edit_500_ceiling_validation(client: TestClient):
    """Asserts batch ceiling of 500 is strictly enforced with HTTP 422 (REQ-MAIN-035)."""
    # 501 items exceeds ceiling
    poi_ids = [str(uuid4()) for _ in range(501)]
    payload = {
        "poi_ids": poi_ids,
        "action": "set_rating",
        "payload": {"rating": 5},
    }

    res = client.post("/api/pois/bulk-edit", json=payload)
    assert res.status_code == 422


def test_bulk_delete_500_ceiling_validation(client: TestClient):
    """Asserts bulk delete ceiling of 500 is strictly enforced with HTTP 422 (REQ-MAIN-035)."""
    poi_ids = [str(uuid4()) for _ in range(501)]
    res = client.post("/api/pois/bulk-delete", json={"poi_ids": poi_ids})
    assert res.status_code == 422


def test_bulk_delete_success(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts bulk delete succeeds within limits (REQ-MAIN-034)."""
    poi_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    res = client.post("/api/pois/bulk-delete", json={"poi_ids": poi_ids})
    assert res.status_code == 200
    assert res.json()["deleted_count"] == 3
    mock_poi_repo.bulk_delete.assert_awaited_once()


def test_bulk_tags_attach_and_detach(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts POST /api/pois/bulk-tags executes attach and detach actions."""
    poi_ids = [str(uuid4())]
    tag_ids = [str(uuid4())]

    # Attach
    res = client.post(
        "/api/pois/bulk-tags",
        json={"poi_ids": poi_ids, "tag_ids": tag_ids, "action": "attach"},
    )
    assert res.status_code == 200
    assert res.json()["modified_count"] == 2
    mock_poi_repo.bulk_attach_tags.assert_awaited_once()

    # Detach
    res = client.post(
        "/api/pois/bulk-tags",
        json={"poi_ids": poi_ids, "tag_ids": tag_ids, "action": "detach"},
    )
    assert res.status_code == 200
    assert res.json()["modified_count"] == 2
    mock_poi_repo.bulk_detach_tags.assert_awaited_once()


def test_bulk_lists_attach_and_detach(client: TestClient, mock_poi_repo: AsyncMock):
    """Asserts POST /api/pois/bulk-lists executes attach and detach actions."""
    poi_ids = [str(uuid4())]
    list_ids = [str(uuid4())]

    # Attach
    res = client.post(
        "/api/pois/bulk-lists",
        json={"poi_ids": poi_ids, "list_ids": list_ids, "action": "attach"},
    )
    assert res.status_code == 200
    assert res.json()["modified_count"] == 3
    mock_poi_repo.bulk_attach_lists.assert_awaited_once()

    # Detach
    res = client.post(
        "/api/pois/bulk-lists",
        json={"poi_ids": poi_ids, "list_ids": list_ids, "action": "detach"},
    )
    assert res.status_code == 200
    assert res.json()["modified_count"] == 3
    mock_poi_repo.bulk_detach_lists.assert_awaited_once()


# -----------------------------------------------------------------------------
# SqlAlchemyPOIRepository.bulk_edit Execution Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_bulk_edit_set_rating(current_user: User):
    """Asserts repository updates rating on target rows."""
    p1 = POITable(
        id=uuid4(),
        user_id=current_user.id,
        name="POI 1",
        rating=2,
        geom=MagicMock(),
    )
    p2 = POITable(
        id=uuid4(),
        user_id=current_user.id,
        name="POI 2",
        rating=3,
        geom=MagicMock(),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1, p2]
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyPOIRepository(mock_session)
    count = await repo.bulk_edit(
        user_id=current_user.id,
        poi_ids=[p1.id, p2.id],
        action="set_rating",
        payload={"rating": 5},
    )

    assert count == 2
    assert p1.rating == 5
    assert p2.rating == 5


@pytest.mark.asyncio
async def test_repo_bulk_edit_add_visit_date_lifecycle(current_user: User):
    """Asserts repository appends visit date, sets already_visited=True and updates lifecycle."""
    p1 = POITable(
        id=uuid4(),
        user_id=current_user.id,
        name="POI 1",
        already_visited=False,
        visit_pending=True,
        want_to_visit_again=None,
        visit_state=VisitState.NOT_VISITED.value,
        visited_dates=[],
        geom=MagicMock(),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1]
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyPOIRepository(mock_session)
    count = await repo.bulk_edit(
        user_id=current_user.id,
        poi_ids=[p1.id],
        action="add_visit_date",
        payload={"visit_date": "2026-10-15"},
    )

    assert count == 1
    assert p1.already_visited is True
    assert "2026-10-15" in p1.visited_dates
    assert p1.visit_state == VisitState.VISITED_DO_NOT_RETURN.value
    assert p1.visit_pending is False


@pytest.mark.asyncio
async def test_repo_bulk_edit_update_address_preservation(current_user: User):
    """Asserts non-destructive address update modifies addresses[0] and preserves secondary records (REQ-MAIN-033, SC-006)."""
    primary_addr = {
        "city": "Old City",
        "state_province": "Old State",
        "country": "France",
        "raw_address": "123 Rue de Rivoli",
    }
    secondary_addr = {
        "city": "Lyon",
        "state_province": "Rhône",
        "country": "France",
        "raw_address": "456 Place Bellecour",
    }
    p1 = POITable(
        id=uuid4(),
        user_id=current_user.id,
        name="Multi Location POI",
        addresses=[primary_addr, secondary_addr],
        states=["Old State", "Rhône"],
        countries=["France"],
        geom=MagicMock(),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1]
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyPOIRepository(mock_session)
    count = await repo.bulk_edit(
        user_id=current_user.id,
        poi_ids=[p1.id],
        action="update_address",
        payload={
            "address": {
                "city": "Kyoto",
                "state_province": "Kyoto",
                "country": "Japan",
                "clear_fields": [],
            }
        },
    )

    assert count == 1
    assert len(p1.addresses) == 2
    # addresses[0] is modified with normalized values
    assert p1.addresses[0]["city"] == "Kyoto"
    assert p1.addresses[0]["state_province"] == "Kyoto"
    assert p1.addresses[0]["country"] == "Japan"
    # raw_address on addresses[0] preserved
    assert p1.addresses[0]["raw_address"] == "123 Rue de Rivoli"
    # addresses[1] is completely preserved and untouched!
    assert p1.addresses[1]["city"] == "Lyon"
    assert p1.addresses[1]["state_province"] == "Rhône"
    assert p1.addresses[1]["country"] == "France"


@pytest.mark.asyncio
async def test_repo_bulk_edit_update_address_clear_fields(current_user: User):
    """Asserts clear_fields sets targeted address components to None."""
    primary_addr = {
        "city": "Tokyo",
        "state_province": "Tokyo",
        "country": "Japan",
    }
    p1 = POITable(
        id=uuid4(),
        user_id=current_user.id,
        name="POI to Clear",
        addresses=[primary_addr],
        states=["Tokyo"],
        countries=["Japan"],
        geom=MagicMock(),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1]
    mock_session.execute.return_value = mock_result

    repo = SqlAlchemyPOIRepository(mock_session)
    count = await repo.bulk_edit(
        user_id=current_user.id,
        poi_ids=[p1.id],
        action="update_address",
        payload={
            "address": {
                "city": None,
                "state_province": None,
                "country": None,
                "clear_fields": ["city", "state_province"],
            }
        },
    )

    assert count == 1
    assert p1.addresses[0]["city"] is None
    assert p1.addresses[0]["state_province"] is None
    assert p1.addresses[0]["country"] == "Japan"
