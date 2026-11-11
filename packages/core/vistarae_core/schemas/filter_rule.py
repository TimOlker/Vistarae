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

"""Filter Rule Pydantic v2 schemas for visual search query trees and display settings.

Implements Constitution Principle 5:
- Inherits StrictBaseModel with extra='forbid'
- Enforces strict data types and constraints
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from vistarae_core.domain.value_objects import (
    FilterConjunction,
    FilterOperator,
    PinColorMode,
    SortDirection,
)
from vistarae_core.schemas.base import StrictBaseModel

OPERATOR_ALIASES: dict[str, FilterOperator] = {
    ">=": FilterOperator.GREATER_THAN_OR_EQUAL,
    "<=": FilterOperator.LESS_THAN_OR_EQUAL,
    ">": FilterOperator.GREATER_THAN,
    "<": FilterOperator.LESS_THAN,
    "=": FilterOperator.EQUALS,
    "==": FilterOperator.EQUALS,
    "!=": FilterOperator.NOT_EQUALS,
    "in": FilterOperator.IN_LIST,
    "not_in": FilterOperator.NOT_IN_LIST,
}


class RuleClauseSchema(StrictBaseModel):
    """Single condition rule in the query builder AST."""

    id: str | None = Field(
        default=None, description="Client UI clause identifier (optional)"
    )
    field: str = Field(
        ..., description="Target POI field (e.g. 'country', 'rating', 'visit_state')"
    )
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: Any | None = Field(
        default=None, description="Operand value (string, number, boolean, or null)"
    )

    @field_validator("operator", mode="before")
    @classmethod
    def normalize_operator(cls, v: Any) -> Any:
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in OPERATOR_ALIASES:
                return OPERATOR_ALIASES[clean]
            if v.strip() in OPERATOR_ALIASES:
                return OPERATOR_ALIASES[v.strip()]
        return v


class QueryTreeSchema(StrictBaseModel):
    """Recursive query builder AST tree node."""

    id: str | None = Field(
        default=None, description="Client UI group identifier (optional)"
    )
    conjunction: FilterConjunction = Field(default=FilterConjunction.AND)
    rules: list[RuleClauseSchema | QueryTreeSchema] = Field(default_factory=list)

    @field_validator("conjunction", mode="before")
    @classmethod
    def normalize_conjunction(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class TableColumnSortSchema(StrictBaseModel):
    """Table column sorting specification."""

    column: str = Field(..., description="Target column identifier")
    direction: SortDirection = Field(default=SortDirection.UNSORTED)

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class TableConfigSchema(StrictBaseModel):
    """POI table view settings: visible columns, sequence, and sorting."""

    visible_columns: list[str] = Field(
        default_factory=lambda: ["name", "city", "country", "rating", "visit_state", "tags"]
    )
    column_order: list[str] = Field(
        default_factory=lambda: ["name", "city", "country", "rating", "visit_state", "tags"]
    )
    sort: TableColumnSortSchema = Field(
        default_factory=lambda: TableColumnSortSchema(column="name", direction=SortDirection.ASC)
    )

    @field_validator("visible_columns", "column_order", mode="before")
    @classmethod
    def normalize_columns(cls, v: Any) -> Any:
        if v is None:
            return ["name", "city", "country", "rating", "visit_state", "tags"]
        return v

    @field_validator("sort", mode="before")
    @classmethod
    def normalize_sort(cls, v: Any) -> Any:
        if v is None:
            return TableColumnSortSchema(column="name", direction=SortDirection.ASC)
        if isinstance(v, dict):
            col = v.get("column") or "name"
            dir_val = v.get("direction") or "asc"
            return {"column": col, "direction": dir_val}
        return v


class PinColorSchemeSchema(StrictBaseModel):
    """Map pin coloring preferences."""

    mode: PinColorMode = Field(default=PinColorMode.UNIFORM)
    default_color: str = Field(default="#2563eb", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    palette: dict[str, str] = Field(
        default_factory=dict,
        description="Value-to-hex mappings for rating (1-5) or visit status",
    )
    rule_mappings: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("default_color", mode="before")
    @classmethod
    def normalize_default_color(cls, v: Any) -> Any:
        if not v or not isinstance(v, str):
            return "#2563eb"
        v_clean = v.strip()
        if not v_clean.startswith("#"):
            v_clean = f"#{v_clean}"
        return v_clean

    @field_validator("palette", mode="before")
    @classmethod
    def normalize_palette(cls, v: Any) -> Any:
        if v is None:
            return {}
        return v

    @field_validator("rule_mappings", mode="before")
    @classmethod
    def normalize_rule_mappings(cls, v: Any) -> Any:
        if v is None:
            return []
        return v


class FilterRuleCreateRequest(StrictBaseModel):
    """Payload to create a new named filter rule."""

    name: str = Field(..., min_length=1, max_length=100)
    query_tree: QueryTreeSchema = Field(default_factory=QueryTreeSchema)
    table_config: TableConfigSchema = Field(default_factory=TableConfigSchema)
    pin_color_scheme: PinColorSchemeSchema = Field(default_factory=PinColorSchemeSchema)


class FilterRuleUpdateRequest(StrictBaseModel):
    """Payload to overwrite an existing filter rule."""

    name: str = Field(..., min_length=1, max_length=100)
    query_tree: QueryTreeSchema
    table_config: TableConfigSchema
    pin_color_scheme: PinColorSchemeSchema


class FilterRuleResponse(StrictBaseModel):
    """Serialised filter rule record."""

    id: UUID
    user_id: UUID
    name: str
    query_tree: QueryTreeSchema
    table_config: TableConfigSchema
    pin_color_scheme: PinColorSchemeSchema
    created_at: datetime
    updated_at: datetime


class FilterRuleListResponse(StrictBaseModel):
    """List response containing filter rules for the current tenant."""

    items: list[FilterRuleResponse]
    total: int
