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

"""Unit tests for Filter Rules CRUD, AST Compilation, and Query Evaluation (T-015).

Tests:
- FilterQueryTranslator: all 10 filter dimensions, comparison operators, and bbox integration
- SqlAlchemyFilterRuleRepository: tenant isolation, CRUD operations
- Filter Rules router: GET, POST (with 409 Conflict), PUT, DELETE with RFC 7807 problem details
- POST /api/pois/query: hybrid query evaluation
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from vistarae_core.adapters.db.tables import FilterRuleTable
from vistarae_core.adapters.repositories.filter_rule_repo import (
    SqlAlchemyFilterRuleRepository,
)
from vistarae_core.domain.entities import POI, FilterRuleEntity, TagEntity, User
from vistarae_core.domain.value_objects import (
    FilterConjunction,
    FilterOperator,
    VisitState,
    WGS84Point,
)
from vistarae_core.ports.repositories import (
    IFilterRuleRepository,
    IPOIRepository,
    ITagRepository,
)
from vistarae_core.schemas.filter_rule import (
    QueryTreeSchema,
    RuleClauseSchema,
)

from services.poi.dependencies import (
    get_current_user,
    get_filter_rule_repo,
    get_poi_repo,
    get_tag_repo,
)
from services.poi.main import app
from services.poi.services.filter_evaluator import FilterQueryTranslator


class TestFilterQueryTranslator:
    """Tests for FilterQueryTranslator AST compiler."""

    def test_tenant_isolation_always_present(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)
        predicate = translator.translate(None)
        sql_str = str(predicate)
        assert "pois.user_id =" in sql_str

    def test_city_operators(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        # equals
        p_eq = translator.translate_clause(
            {"field": "city", "operator": "equals", "value": "Tokyo"}
        )
        assert "lower(pois.city)" in str(p_eq)

        # contains
        p_cont = translator.translate_clause(
            {"field": "city", "operator": "contains", "value": "Tok"}
        )
        assert "pois.city" in str(p_cont) and "like" in str(p_cont).lower()

        # is_empty
        p_empty = translator.translate_clause(
            {"field": "city", "operator": "is_empty", "value": None}
        )
        assert "pois.city IS NULL" in str(p_empty)

        # is_not_empty
        p_not_empty = translator.translate_clause(
            {"field": "city", "operator": "is_not_empty", "value": None}
        )
        assert "pois.city IS NOT NULL" in str(p_not_empty)

    def test_state_and_country_operators(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        # state equals
        p_state = translator.translate_clause(
            {"field": "state_province", "operator": "equals", "value": "California"}
        )
        assert "pois.states" in str(p_state)

        # country equals
        p_country = translator.translate_clause(
            {"field": "country", "operator": "equals", "value": "Japan"}
        )
        assert "pois.countries" in str(p_country)

    def test_boolean_and_rating_operators(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        # has_parent true
        p_parent = translator.translate_clause(
            {"field": "has_parent", "operator": "equals", "value": True}
        )
        assert "pois.parent_poi_id IS NOT NULL" in str(p_parent)

        # has_parent false
        p_no_parent = translator.translate_clause(
            {"field": "has_parent", "operator": "equals", "value": False}
        )
        assert "pois.parent_poi_id IS NULL" in str(p_no_parent)

        # already_visited
        p_visited = translator.translate_clause(
            {"field": "already_visited", "operator": "equals", "value": True}
        )
        assert "pois.already_visited =" in str(p_visited)

        # rating >= 4
        p_rating = translator.translate_clause({"field": "rating", "operator": ">=", "value": 4})
        assert "pois.rating >=" in str(p_rating)

    def test_list_and_tag_operators(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        list_id = uuid4()
        p_list = translator.translate_clause(
            {"field": "list_id", "operator": "in_list", "value": str(list_id)}
        )
        assert "poi_lists.list_id =" in str(p_list)

        p_tag = translator.translate_clause(
            {"field": "tag", "operator": "has_tag", "value": "scenic"}
        )
        assert "lower(tags.name) =" in str(p_tag)

    def test_nested_tree_and_conjunction(self) -> None:
        user_id = uuid4()
        tree = QueryTreeSchema(
            conjunction=FilterConjunction.AND,
            rules=[
                RuleClauseSchema(field="city", operator=FilterOperator.EQUALS, value="Kyoto"),
                RuleClauseSchema(
                    field="rating", operator=FilterOperator.GREATER_THAN_OR_EQUAL, value=4
                ),
            ],
        )
        predicate = FilterQueryTranslator.compile(tree, user_id)
        sql_str = str(predicate)
        assert "pois.user_id =" in sql_str
        assert "lower(pois.city)" in sql_str
        assert "pois.rating >=" in sql_str

    def test_bounding_box_compilation(self) -> None:
        user_id = uuid4()
        # Normal bounding box
        pred = FilterQueryTranslator.compile(None, user_id, bbox="139.0,35.0,140.0,36.0")
        sql_str = str(pred)
        assert "ST_MakeEnvelope" in sql_str

        # Antimeridian crossing (minLng > maxLng)
        pred_cross = FilterQueryTranslator.compile(None, user_id, bbox="179.0,-20.0,-179.0,-10.0")
        assert "ST_MakeEnvelope" in str(pred_cross)

    def test_all_operator_branches_and_fallbacks(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        # city not_equals
        p_c_ne = translator.translate_clause(
            {"field": "city", "operator": "not_equals", "value": "Paris"}
        )
        assert "lower(pois.city) !=" in str(p_c_ne)

        # state operators: not_equals, contains, is_empty, is_not_empty
        p_s_ne = translator.translate_clause(
            {"field": "state_province", "operator": "not_equals", "value": "Tokyo"}
        )
        assert "NOT" in str(p_s_ne) or "~" in str(p_s_ne)
        p_s_cont = translator.translate_clause(
            {"field": "state_province", "operator": "contains", "value": "Tok"}
        )
        assert "like" in str(p_s_cont).lower()
        p_s_empty = translator.translate_clause(
            {"field": "state_province", "operator": "is_empty", "value": None}
        )
        assert "jsonb_array_length" in str(p_s_empty)
        p_s_not_empty = translator.translate_clause(
            {"field": "state_province", "operator": "is_not_empty", "value": None}
        )
        assert "jsonb_array_length" in str(p_s_not_empty)

        # country not_equals
        p_co_ne = translator.translate_clause(
            {"field": "country", "operator": "not_equals", "value": "France"}
        )
        assert "NOT" in str(p_co_ne) or "~" in str(p_co_ne)

        # visit_pending false, already_visited false
        p_vp_f = translator.translate_clause(
            {"field": "visit_pending", "operator": "equals", "value": False}
        )
        assert "pois.visit_pending = false" in str(p_vp_f).lower()
        p_av_f = translator.translate_clause(
            {"field": "already_visited", "operator": "equals", "value": False}
        )
        assert "pois.already_visited = false" in str(p_av_f).lower()

        # visit_state equals & not_equals
        p_vs_eq = translator.translate_clause(
            {"field": "visit_state", "operator": "equals", "value": "visited_return"}
        )
        assert "pois.visit_state =" in str(p_vs_eq)
        p_vs_ne = translator.translate_clause(
            {"field": "visit_state", "operator": "not_equals", "value": "not_visited"}
        )
        assert "pois.visit_state !=" in str(p_vs_ne)

        # rating operators: =, !=, <, <=, >, >=, invalid
        assert "pois.rating =" in str(
            translator.translate_clause({"field": "rating", "operator": "=", "value": 3})
        )
        assert "pois.rating !=" in str(
            translator.translate_clause({"field": "rating", "operator": "!=", "value": 3})
        )
        assert "pois.rating <" in str(
            translator.translate_clause({"field": "rating", "operator": "<", "value": 4})
        )
        assert "pois.rating <=" in str(
            translator.translate_clause({"field": "rating", "operator": "<=", "value": 4})
        )
        assert "pois.rating >" in str(
            translator.translate_clause({"field": "rating", "operator": ">", "value": 2})
        )
        assert "pois.rating =" in str(
            translator.translate_clause(
                {"field": "rating", "operator": "equals", "value": "invalid"}
            )
        )

        # list_id not_in_list & tag lacks_tag
        list_id = uuid4()
        p_list_not = translator.translate_clause(
            {"field": "list_id", "operator": "not_in_list", "value": str(list_id)}
        )
        assert "NOT IN" in str(p_list_not)
        p_tag_lacks = translator.translate_clause(
            {"field": "tag", "operator": "lacks_tag", "value": "touristy"}
        )
        assert "NOT IN" in str(p_tag_lacks)

        # Invalid clauses / unknown fields
        assert translator.translate_clause("not-a-dict") is None
        assert (
            translator.translate_clause(
                {"field": "unknown_dimension", "operator": "equals", "value": "x"}
            )
            is None
        )
        assert (
            translator.translate_clause({"field": "city", "operator": "unknown_op", "value": "x"})
            is None
        )

        # OR conjunction tree
        or_tree = QueryTreeSchema(
            conjunction=FilterConjunction.OR,
            rules=[
                RuleClauseSchema(field="city", operator=FilterOperator.EQUALS, value="Kyoto"),
                RuleClauseSchema(field="city", operator=FilterOperator.EQUALS, value="Osaka"),
            ],
        )
        or_pred = FilterQueryTranslator.compile(or_tree, user_id)
        assert "OR" in str(or_pred)


class TestSqlAlchemyFilterRuleRepository:
    """Tests for SqlAlchemyFilterRuleRepository adapter."""

    @pytest.mark.asyncio
    async def test_create_and_get_by_name(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        user_id = uuid4()
        rule = FilterRuleEntity(
            id=uuid4(),
            user_id=user_id,
            name="Japan Top Picks",
            query_tree={"conjunction": "AND", "rules": []},
            table_config={"visible_columns": ["name", "city"]},
            pin_color_scheme={"mode": "rating"},
        )
        created = await repo.create(rule)
        assert created.name == "Japan Top Picks"
        assert session.add.called
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_get_by_id_scoped(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        rule_id = uuid4()
        user_id = uuid4()

        row = MagicMock(spec=FilterRuleTable)
        row.id = rule_id
        row.user_id = user_id
        row.name = "Test Rule"
        row.query_tree = {}
        row.table_config = {}
        row.pin_color_scheme = {}
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        session.execute.return_value = result_mock

        found = await repo.get_by_id(rule_id, user_id)
        assert found is not None
        assert found.id == rule_id

    @pytest.mark.asyncio
    async def test_list_by_user(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        user_id = uuid4()

        row = MagicMock(spec=FilterRuleTable)
        row.id = uuid4()
        row.user_id = user_id
        row.name = "Rule 1"
        row.query_tree = {}
        row.table_config = {}
        row.pin_color_scheme = {}
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [row]
        session.execute.return_value = result_mock

        rules = await repo.list_by_user(user_id)
        assert len(rules) == 1
        assert rules[0].name == "Rule 1"

    @pytest.mark.asyncio
    async def test_get_by_name(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        user_id = uuid4()

        row = MagicMock(spec=FilterRuleTable)
        row.id = uuid4()
        row.user_id = user_id
        row.name = "My Rule"
        row.query_tree = {}
        row.table_config = {}
        row.pin_color_scheme = {}
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        session.execute.return_value = result_mock

        found = await repo.get_by_name("My Rule", user_id)
        assert found is not None
        assert found.name == "My Rule"

        # Not found case
        result_mock.scalar_one_or_none.return_value = None
        not_found = await repo.get_by_name("Nonexistent", user_id)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_update_rule(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        rule_id = uuid4()
        user_id = uuid4()

        row = MagicMock(spec=FilterRuleTable)
        row.id = rule_id
        row.user_id = user_id
        row.name = "Old Name"
        row.query_tree = {}
        row.table_config = {}
        row.pin_color_scheme = {}
        row.created_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = row
        session.execute.return_value = result_mock

        rule_to_update = FilterRuleEntity(
            id=rule_id,
            user_id=user_id,
            name="New Name",
            query_tree={"conjunction": "OR", "rules": []},
            table_config={"visible_columns": ["name", "city"]},
            pin_color_scheme={"mode": "rating"},
        )
        updated = await repo.update(rule_to_update)
        assert updated.name == "New Name"
        assert row.name == "New Name"
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(ValueError, match="not found"):
            await repo.update(
                FilterRuleEntity(
                    id=uuid4(),
                    user_id=uuid4(),
                    name="X",
                    query_tree={},
                    table_config={},
                    pin_color_scheme={},
                )
            )

    @pytest.mark.asyncio
    async def test_delete_rule(self) -> None:
        session = AsyncMock()
        repo = SqlAlchemyFilterRuleRepository(session)
        rule_id = uuid4()
        user_id = uuid4()

        result_mock = MagicMock()
        result_mock.rowcount = 1
        session.execute.return_value = result_mock

        deleted = await repo.delete(rule_id, user_id)
        assert deleted is True

    def test_filter_evaluator_nested_subtrees_and_fallbacks(self) -> None:
        user_id = uuid4()
        translator = FilterQueryTranslator(user_id)

        # Empty tree and invalid tree fallbacks
        assert str(translator.translate_tree(None)) == "true"
        assert str(translator.translate_tree("not-a-tree")) == "true"
        assert str(translator.translate_tree({"rules": []})) == "true"

        # Nested subtree (QueryTreeSchema inside rules)
        sub_tree = QueryTreeSchema(
            conjunction=FilterConjunction.OR,
            rules=[RuleClauseSchema(field="city", operator=FilterOperator.EQUALS, value="Kyoto")],
        )
        parent_tree = QueryTreeSchema(
            conjunction=FilterConjunction.AND,
            rules=[sub_tree],
        )
        pred = translator.translate_tree(parent_tree)
        assert "lower(pois.city)" in str(pred)

        # Nested subtree as dict
        dict_tree = {
            "conjunction": "AND",
            "rules": [
                {
                    "conjunction": "OR",
                    "rules": [{"field": "city", "operator": "equals", "value": "Tokyo"}],
                }
            ],
        }
        pred_dict = translator.translate_tree(dict_tree)
        assert "lower(pois.city)" in str(pred_dict)

        # Invalid bbox format triggers exception handler gracefully
        pred_invalid_bbox = translator.translate(None, bbox="invalid,bbox,format")
        assert "pois.user_id =" in str(pred_invalid_bbox)


class TestFilterRulesRouter:
    """Tests for Filter Rules FastAPI endpoints."""

    def test_list_filter_rules(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_rule = FilterRuleEntity(
            id=uuid4(),
            user_id=mock_user.id,
            name="Kyoto Temples",
            query_tree={"conjunction": "AND", "rules": []},
            table_config={"visible_columns": ["name"]},
            pin_color_scheme={"mode": "uniform"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.list_by_user.return_value = [mock_rule]

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        try:
            client = TestClient(app)
            res = client.get("/api/pois/filter-rules")
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["name"] == "Kyoto Temples"
        finally:
            app.dependency_overrides.clear()

    def test_create_filter_rule_success(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_repo.get_by_name.return_value = None
        mock_repo.create.side_effect = lambda entity: entity

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        payload = {
            "name": "France Top Gems",
            "query_tree": {
                "conjunction": "AND",
                "rules": [{"field": "country", "operator": "equals", "value": "France"}],
            },
            "table_config": {
                "visible_columns": ["name", "city", "rating"],
                "column_order": ["name", "city", "rating"],
                "sort": {"column": "rating", "direction": "desc"},
            },
            "pin_color_scheme": {
                "mode": "rating",
                "default_color": "#2563eb",
                "palette": {"5": "#eab308", "4": "#3b82f6"},
                "rule_mappings": [],
            },
        }

        try:
            client = TestClient(app)
            res = client.post("/api/pois/filter-rules", json=payload)
            assert res.status_code == 201
            data = res.json()
            assert data["name"] == "France Top Gems"
        finally:
            app.dependency_overrides.clear()

    def test_create_filter_rule_conflict_409(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        existing_rule = FilterRuleEntity(
            id=uuid4(),
            user_id=mock_user.id,
            name="Duplicate Rule",
            query_tree={},
            table_config={},
            pin_color_scheme={},
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_repo.get_by_name.return_value = existing_rule

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        payload = {
            "name": "Duplicate Rule",
            "query_tree": {"conjunction": "AND", "rules": []},
            "table_config": {
                "visible_columns": ["name"],
                "column_order": ["name"],
                "sort": {"column": "name", "direction": "asc"},
            },
            "pin_color_scheme": {
                "mode": "uniform",
                "default_color": "#2563eb",
                "palette": {},
                "rule_mappings": [],
            },
        }

        try:
            client = TestClient(app)
            res = client.post("/api/pois/filter-rules", json=payload)
            assert res.status_code == 409
        finally:
            app.dependency_overrides.clear()

    def test_get_filter_rule_by_id(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        rule_id = uuid4()
        mock_rule = FilterRuleEntity(
            id=rule_id,
            user_id=mock_user.id,
            name="Found Rule",
            query_tree={"conjunction": "AND", "rules": []},
            table_config={"visible_columns": ["name"]},
            pin_color_scheme={"mode": "uniform"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_repo.get_by_id.side_effect = lambda r_id, u_id: mock_rule if r_id == rule_id else None

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        try:
            client = TestClient(app)
            # Success
            res = client.get(f"/api/pois/filter-rules/{rule_id}")
            assert res.status_code == 200
            assert res.json()["name"] == "Found Rule"

            # 404
            res_nf = client.get(f"/api/pois/filter-rules/{uuid4()}")
            assert res_nf.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_update_filter_rule(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        rule_id = uuid4()
        existing = FilterRuleEntity(
            id=rule_id,
            user_id=mock_user.id,
            name="Original Name",
            query_tree={"conjunction": "AND", "rules": []},
            table_config={"visible_columns": ["name"]},
            pin_color_scheme={"mode": "uniform"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_repo.get_by_id.side_effect = lambda r_id, u_id: existing if r_id == rule_id else None
        mock_repo.get_by_name.return_value = None
        mock_repo.update.side_effect = lambda entity: entity

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        payload = {
            "name": "Updated Name",
            "query_tree": {"conjunction": "OR", "rules": []},
            "table_config": {
                "visible_columns": ["name", "city"],
                "column_order": ["name", "city"],
                "sort": {"column": "city", "direction": "asc"},
            },
            "pin_color_scheme": {
                "mode": "uniform",
                "default_color": "#ff0000",
                "palette": {},
                "rule_mappings": [],
            },
        }

        try:
            client = TestClient(app)
            # Success
            res = client.put(f"/api/pois/filter-rules/{rule_id}", json=payload)
            assert res.status_code == 200
            assert res.json()["name"] == "Updated Name"

            # 404 Not Found
            unknown_id = uuid4()
            res_nf = client.put(f"/api/pois/filter-rules/{unknown_id}", json=payload)
            assert res_nf.status_code == 404

            # 409 Conflict when name belongs to another rule
            conflicting_rule = FilterRuleEntity(
                id=uuid4(),
                user_id=mock_user.id,
                name="Updated Name",
                query_tree={},
                table_config={},
                pin_color_scheme={},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            mock_repo.get_by_name.return_value = conflicting_rule
            res_conf = client.put(f"/api/pois/filter-rules/{rule_id}", json=payload)
            assert res_conf.status_code == 409
        finally:
            app.dependency_overrides.clear()

    def test_delete_filter_rule_success_and_not_found(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        mock_repo = AsyncMock(spec=IFilterRuleRepository)
        mock_repo.delete.side_effect = lambda r_id, u_id: (
            r_id == UUID("00000000-0000-0000-0000-000000000001")
        )

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_filter_rule_repo] = lambda: mock_repo

        try:
            client = TestClient(app)
            # Success
            res = client.delete("/api/pois/filter-rules/00000000-0000-0000-0000-000000000001")
            assert res.status_code == 204

            # Not found
            res_nf = client.delete("/api/pois/filter-rules/00000000-0000-0000-0000-000000000002")
            assert res_nf.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_query_pois_endpoint(self) -> None:
        mock_user = User(
            id=uuid4(),
            cognito_sub="sub-test",
            email="traveler@example.com",
            is_active=True,
        )
        mock_poi_repo = AsyncMock(spec=IPOIRepository)
        mock_tag_repo = AsyncMock(spec=ITagRepository)

        test_poi = POI(
            id=uuid4(),
            user_id=mock_user.id,
            name="Tokyo Skytree",
            geom=WGS84Point(lon=139.8107, lat=35.7100),
            city="Tokyo",
            countries=["Japan"],
            rating=5,
            visit_state=VisitState.NOT_VISITED,
        )
        mock_poi_repo.query_pois_by_predicate.return_value = ([test_poi], 1)
        mock_tag_repo.get_tags_for_poi.return_value = [
            TagEntity(id=uuid4(), user_id=mock_user.id, name="tower")
        ]

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_poi_repo] = lambda: mock_poi_repo
        app.dependency_overrides[get_tag_repo] = lambda: mock_tag_repo

        payload = {
            "query_tree": {
                "conjunction": "AND",
                "rules": [{"field": "country", "operator": "equals", "value": "Japan"}],
            },
            "bbox": "139.0,35.0,140.0,36.0",
        }

        try:
            client = TestClient(app)
            res = client.post("/api/pois/query", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["name"] == "Tokyo Skytree"
            assert data["items"][0]["tags"][0]["name"] == "tower"

            # Invalid bounding box parameter raises 422 on list_pois
            res_bad_bbox = client.get("/api/pois?bbox=1,2,3")
            assert res_bad_bbox.status_code == 422
        finally:
            app.dependency_overrides.clear()


class TestRepositoryReExports:
    """Verifies repository adapter exports in services.poi.repositories."""

    def test_repository_re_exports(self) -> None:
        from services.poi.repositories import FilterRuleRepository as FR1
        from services.poi.repositories import POIRepository as PR1
        from services.poi.repositories.filter_rule_repository import FilterRuleRepository as FR2

        assert FR1 is SqlAlchemyFilterRuleRepository
        assert FR2 is SqlAlchemyFilterRuleRepository
        assert PR1 is not None


class TestFilterQueryTranslatorEdgeCases:
    """Covers edge cases and uncovered branches in FilterQueryTranslator."""

    def test_states_operators(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        # states contains
        p_cont = translator.translate_clause(
            {"field": "states", "operator": "contains", "value": "Cal"}
        )
        assert "pois.states" in str(p_cont)
        # states is_empty
        p_empty = translator.translate_clause(
            {"field": "states", "operator": "is_empty", "value": None}
        )
        assert "jsonb_array_length" in str(p_empty)
        # states is_not_empty
        p_not_empty = translator.translate_clause(
            {"field": "states", "operator": "is_not_empty", "value": None}
        )
        assert "jsonb_array_length" in str(p_not_empty)

    def test_country_not_equals(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_neq = translator.translate_clause(
            {"field": "country", "operator": "not_equals", "value": "Japan"}
        )
        assert "pois.countries" in str(p_neq)

    def test_rating_comparison_operators(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_lte = translator.translate_clause({"field": "rating", "operator": "<=", "value": 3})
        assert "<=" in str(p_lte)
        p_lt = translator.translate_clause({"field": "rating", "operator": "<", "value": 3})
        assert "<" in str(p_lt)
        p_gte = translator.translate_clause({"field": "rating", "operator": ">=", "value": 4})
        assert ">=" in str(p_gte)
        p_gt = translator.translate_clause({"field": "rating", "operator": ">", "value": 4})
        assert ">" in str(p_gt)
        p_neq = translator.translate_clause({"field": "rating", "operator": "!=", "value": 2})
        assert "!=" in str(p_neq)
        p_invalid = translator.translate_clause(
            {"field": "rating", "operator": "equals", "value": "not-a-number"}
        )
        assert "pois.rating =" in str(p_invalid)

    def test_list_id_and_invalid_uuid(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        valid_id = str(uuid4())
        p_notin = translator.translate_clause(
            {"field": "list_id", "operator": "not_in_list", "value": valid_id}
        )
        assert "pois.id NOT IN" in str(p_notin)
        p_invalid = translator.translate_clause(
            {"field": "list_id", "operator": "in_list", "value": "not-a-uuid"}
        )
        assert p_invalid is None

    def test_visit_state_not_equals(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_neq = translator.translate_clause(
            {"field": "visit_state", "operator": "!=", "value": "visited"}
        )
        assert "!=" in str(p_neq)

    def test_tag_lacks_tag(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_lacks = translator.translate_clause(
            {"field": "tag", "operator": "lacks_tag", "value": "temple"}
        )
        assert "pois.id NOT IN" in str(p_lacks)

    def test_unknown_field_and_empty_tree(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_none = translator.translate_clause(
            {"field": "unknown_dim", "operator": "equals", "value": "x"}
        )
        assert p_none is None
        assert (
            translator.translate_clause({"field": "city", "operator": "bad_op", "value": "x"})
            is None
        )
        assert (
            translator.translate_clause({"field": "states", "operator": "bad_op", "value": "x"})
            is None
        )
        assert (
            translator.translate_clause({"field": "country", "operator": "bad_op", "value": "x"})
            is None
        )
        assert (
            translator.translate_clause({"field": "rating", "operator": "bad_op", "value": 4})
            is None
        )
        assert (
            translator.translate_clause(
                {"field": "list_id", "operator": "bad_op", "value": str(uuid4())}
            )
            is None
        )
        assert (
            translator.translate_clause({"field": "tag", "operator": "bad_op", "value": "x"})
            is None
        )
        assert (
            translator.translate_clause(
                {"field": "visit_state", "operator": "bad_op", "value": "x"}
            )
            is None
        )

        # empty tree
        p_empty = translator.translate_tree(None)
        assert str(p_empty) == "true"
        p_empty2 = translator.translate_tree({"conjunction": "AND", "rules": []})
        assert str(p_empty2) == "true"

    def test_antimeridian_bbox(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        p_anti = translator.translate(None, bbox="175.0,-10.0,-175.0,10.0")
        assert "ST_MakeEnvelope" in str(p_anti)

    def test_nested_subtree_evaluation(self) -> None:
        translator = FilterQueryTranslator(uuid4())
        nested_tree = {
            "conjunction": "OR",
            "rules": [
                {
                    "conjunction": "AND",
                    "rules": [
                        {"field": "city", "operator": "equals", "value": "Tokyo"},
                        {"field": "rating", "operator": ">=", "value": 4},
                    ],
                },
                {"field": "country", "operator": "equals", "value": "Japan"},
            ],
        }
        expr = translator.translate_tree(nested_tree)
        sql_str = str(expr)
        assert "pois.city" in sql_str
        assert "pois.countries" in sql_str


class TestPOISchemaHelpers:
    """Covers alias coalescence in POICreateRequest and POIUpdateRequest."""

    def test_create_and_update_state_country_aliases(self) -> None:
        from vistarae_core.schemas.poi import POICreateRequest, POIUpdateRequest

        req_create = POICreateRequest(
            name="Test POI",
            lat=35.0,
            lon=135.0,
            state="California",
            states=["New York"],
            country="United States",
            countries=["Canada"],
        )
        assert "California" in req_create.states
        assert "New York" in req_create.states
        assert "United States" in req_create.countries
        assert "Canada" in req_create.countries

        req_update = POIUpdateRequest(state="California", country="USA")
        assert req_update.states == ["California"]
        assert req_update.countries == ["USA"]
