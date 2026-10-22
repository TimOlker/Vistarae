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

"""SQLAlchemy AST query compiler for POI visual query builder (T-010).

Translates recursive QueryTree AST nodes into SQLAlchemy binary expressions
enforcing:
- Strict tenant isolation: WHERE user_id = :current_user_id
- Spatial bounding box integration (ST_MakeEnvelope and ST_Intersects)
- All 10 filter dimensions and comparison operators from REQ-MAIN-009
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import and_, cast, func, or_, select, true
from sqlalchemy.sql.elements import ColumnElement
from vistarae_core.adapters.db.tables import (
    POIListTable,
    POITable,
    POITagTable,
    TagTable,
)
from vistarae_core.domain.value_objects import FilterConjunction, FilterOperator
from vistarae_core.schemas.filter_rule import QueryTreeSchema, RuleClauseSchema


class FilterQueryTranslator:
    """Translates visual filter builder QueryTree AST nodes into SQLAlchemy predicates."""

    def __init__(self, user_id: UUID) -> None:
        """Initializes translator with current tenant context.

        Args:
            user_id: Authenticated user UUID for tenant isolation.
        """
        self.user_id = user_id

    def _translate_city(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates city dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        if op_norm in (FilterOperator.EQUALS, "equals", "="):
            return func.lower(POITable.city) == str(value).lower()
        if op_norm in (FilterOperator.NOT_EQUALS, "not_equals", "!="):
            return or_(
                POITable.city.is_(None),
                func.lower(POITable.city) != str(value).lower(),
            )
        if op_norm in (FilterOperator.CONTAINS, "contains"):
            return POITable.city.ilike(f"%{value}%")
        if op_norm in (FilterOperator.IS_EMPTY, "is_empty"):
            return or_(POITable.city.is_(None), POITable.city == "")
        if op_norm in (FilterOperator.IS_NOT_EMPTY, "is_not_empty"):
            return and_(POITable.city.isnot(None), POITable.city != "")
        return None

    def _translate_states(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates state_province dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        if op_norm in (FilterOperator.EQUALS, "equals", "="):
            return POITable.states.contains([str(value)])
        if op_norm in (FilterOperator.NOT_EQUALS, "not_equals", "!="):
            return ~POITable.states.contains([str(value)])
        if op_norm in (FilterOperator.CONTAINS, "contains"):
            return cast(POITable.states, sa.String).ilike(f"%{value}%")
        if op_norm in (FilterOperator.IS_EMPTY, "is_empty"):
            return or_(
                POITable.states.is_(None),
                func.jsonb_array_length(POITable.states) == 0,
            )
        if op_norm in (FilterOperator.IS_NOT_EMPTY, "is_not_empty"):
            return and_(
                POITable.states.isnot(None),
                func.jsonb_array_length(POITable.states) > 0,
            )
        return None

    def _translate_countries(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates country dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        if op_norm in (FilterOperator.EQUALS, "equals", "="):
            return POITable.countries.contains([str(value)])
        if op_norm in (FilterOperator.NOT_EQUALS, "not_equals", "!="):
            return ~POITable.countries.contains([str(value)])
        return None

    def _translate_rating(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates rating dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        try:
            int_val = int(value) if value is not None else 0
        except (ValueError, TypeError):
            int_val = 0
        if op_norm in (FilterOperator.EQUALS, "equals", "="):
            return POITable.rating == int_val
        if op_norm in (FilterOperator.NOT_EQUALS, "not_equals", "!="):
            return or_(POITable.rating.is_(None), POITable.rating != int_val)
        if op_norm in (FilterOperator.GREATER_THAN, "greater_than", ">"):
            return POITable.rating > int_val
        if op_norm in (FilterOperator.LESS_THAN, "less_than", "<"):
            return POITable.rating < int_val
        if op_norm in (FilterOperator.GREATER_THAN_OR_EQUAL, "greater_than_or_equal", ">="):
            return POITable.rating >= int_val
        if op_norm in (FilterOperator.LESS_THAN_OR_EQUAL, "less_than_or_equal", "<="):
            return POITable.rating <= int_val
        return None

    def _translate_list(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates list_id dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        try:
            list_uuid = UUID(str(value))
        except (ValueError, TypeError):
            return None
        list_subquery = (
            select(POIListTable.poi_id).where(POIListTable.list_id == list_uuid).scalar_subquery()
        )
        if op_norm in (FilterOperator.IN_LIST, "in_list", "in"):
            return POITable.id.in_(list_subquery)
        if op_norm in (FilterOperator.NOT_IN_LIST, "not_in_list", "not_in"):
            return POITable.id.not_in(list_subquery)
        return None

    def _translate_tag(self, op_norm: str, value: Any) -> ColumnElement[bool] | None:
        """Translates tag dimension operators.

        Args:
            op_norm: Lowercase normalized operator string.
            value: Filter value.

        Returns:
            SQLAlchemy predicate or None.
        """
        tag_name = str(value)
        tag_subquery = (
            select(POITagTable.poi_id)
            .join(TagTable, POITagTable.tag_id == TagTable.id)
            .where(
                func.lower(TagTable.name) == tag_name.lower(),
                TagTable.user_id == self.user_id,
            )
            .scalar_subquery()
        )
        if op_norm in (FilterOperator.HAS_TAG, "has_tag", "contains"):
            return POITable.id.in_(tag_subquery)
        if op_norm in (FilterOperator.LACKS_TAG, "lacks_tag"):
            return POITable.id.not_in(tag_subquery)
        return None

    def translate_clause(
        self, clause: RuleClauseSchema | dict[str, Any]
    ) -> ColumnElement[bool] | None:
        """Translates a single leaf RuleClause into a SQLAlchemy predicate.

        Args:
            clause: RuleClauseSchema or dict with field, operator, value.

        Returns:
            SQLAlchemy binary expression, or None if clause is invalid.
        """
        if isinstance(clause, RuleClauseSchema):
            field = clause.field
            operator = str(
                clause.operator.value if hasattr(clause.operator, "value") else clause.operator
            )
            value = clause.value
        elif isinstance(clause, dict):
            field = clause.get("field", "")
            raw_op = clause.get("operator", "")
            operator = str(raw_op.value if hasattr(raw_op, "value") else raw_op)
            value = clause.get("value")
        else:
            return None

        # Normalize operator
        op_norm = operator.lower()

        # Dispatch to dimension-specific handlers
        if field == "city":
            return self._translate_city(op_norm, value)
        if field in ("state_province", "state", "states"):
            return self._translate_states(op_norm, value)
        if field in ("country", "countries"):
            return self._translate_countries(op_norm, value)
        if field == "has_parent":
            is_parent = bool(value) if value is not None else False
            return (
                POITable.parent_poi_id.isnot(None)
                if is_parent
                else POITable.parent_poi_id.is_(None)
            )
        if field == "visit_pending":
            val = bool(value) if value is not None else False
            return POITable.visit_pending == val
        if field == "already_visited":
            val = bool(value) if value is not None else False
            return POITable.already_visited == val
        if field == "rating":
            return self._translate_rating(op_norm, value)
        if field in ("list_id", "list"):
            return self._translate_list(op_norm, value)
        if field == "visit_state":
            str_val = str(value)
            if op_norm in (FilterOperator.EQUALS, "equals", "="):
                return POITable.visit_state == str_val
            if op_norm in (FilterOperator.NOT_EQUALS, "not_equals", "!="):
                return POITable.visit_state != str_val
            return None
        if field in ("tag", "tags"):
            return self._translate_tag(op_norm, value)

        return None

    def translate_tree(self, tree: QueryTreeSchema | dict[str, Any] | None) -> ColumnElement[bool]:
        """Recursively translates a QueryTree AST node into a boolean SQL expression.

        Args:
            tree: QueryTreeSchema or dictionary representing the AST tree.

        Returns:
            SQLAlchemy boolean predicate expression.
        """
        if not tree:
            return true()

        if isinstance(tree, QueryTreeSchema):
            conjunction = tree.conjunction
            rules = tree.rules
        elif isinstance(tree, dict):
            conjunction = tree.get("conjunction", FilterConjunction.AND)
            rules = tree.get("rules", [])
        else:
            return true()

        conj_str = str(conjunction.value if hasattr(conjunction, "value") else conjunction).upper()

        compiled_predicates: list[ColumnElement[bool]] = []

        for rule in rules:
            # Check if this rule is a nested tree (has conjunction or rules)
            is_sub_tree = False
            if (
                isinstance(rule, QueryTreeSchema)
                or isinstance(rule, dict)
                and ("rules" in rule or "conjunction" in rule)
            ):
                is_sub_tree = True

            if is_sub_tree:
                sub_expr = self.translate_tree(rule)
                if sub_expr is not None:
                    compiled_predicates.append(sub_expr)
            else:
                pred = self.translate_clause(rule)  # type: ignore[arg-type]
                if pred is not None:
                    compiled_predicates.append(pred)

        if not compiled_predicates:
            return true()

        if conj_str == "OR":
            return or_(*compiled_predicates)
        return and_(*compiled_predicates)

    def translate(
        self,
        query_tree: QueryTreeSchema | dict[str, Any] | None,
        bbox: str | None = None,
    ) -> ColumnElement[bool]:
        """Translates QueryTree AST and spatial bounding box into a combined SQL predicate.

        Enforces tenant isolation by always prepending: POITable.user_id == self.user_id.

        Args:
            query_tree: Root query tree AST.
            bbox: Optional bounding box string ("minLng,minLat,maxLng,maxLat").

        Returns:
            SQLAlchemy boolean predicate expression for WHERE clause.
        """
        predicates: list[ColumnElement[bool]] = [POITable.user_id == self.user_id]

        if query_tree:
            tree_expr = self.translate_tree(query_tree)
            predicates.append(tree_expr)

        if bbox:
            try:
                coords = [float(c.strip()) for c in bbox.split(",")]
                if len(coords) == 4:
                    min_lng, min_lat, max_lng, max_lat = coords
                    if min_lng > max_lng:
                        # Crosses antimeridian: union of two bounding boxes
                        bbox_predicate = or_(
                            func.ST_Intersects(
                                cast(POITable.geom, Geometry),
                                func.ST_MakeEnvelope(min_lng, min_lat, 180.0, max_lat, 4326),
                            ),
                            func.ST_Intersects(
                                cast(POITable.geom, Geometry),
                                func.ST_MakeEnvelope(-180.0, min_lat, max_lng, max_lat, 4326),
                            ),
                        )
                    else:
                        bbox_predicate = func.ST_Intersects(
                            cast(POITable.geom, Geometry),
                            func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326),
                        )
                    predicates.append(bbox_predicate)
            except Exception:
                pass

        return and_(*predicates)

    @classmethod
    def compile(
        cls,
        query_tree: QueryTreeSchema | dict[str, Any] | None,
        user_id: UUID,
        bbox: str | None = None,
    ) -> ColumnElement[bool]:
        """Convenience factory compiling AST nodes directly.

        Args:
            query_tree: QueryTree AST node or dict.
            user_id: Authenticated user UUID.
            bbox: Optional bounding box string.

        Returns:
            SQLAlchemy boolean predicate expression.
        """
        return cls(user_id=user_id).translate(query_tree=query_tree, bbox=bbox)
