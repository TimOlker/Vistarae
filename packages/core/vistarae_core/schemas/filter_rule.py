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

from pydantic import Field

from vistarae_core.domain.value_objects import (
    FilterConjunction,
    FilterOperator,
    PinColorMode,
    SortDirection,
)
from vistarae_core.schemas.base import StrictBaseModel


class RuleClauseSchema(StrictBaseModel):
    """Single condition rule in the query builder AST."""

    field: str = Field(
        ..., description="Target POI field (e.g. 'country', 'rating', 'visit_state')"
    )
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: Any | None = Field(
        default=None, description="Operand value (string, number, boolean, or null)"
    )


class QueryTreeSchema(StrictBaseModel):
    """Recursive query builder AST tree node."""

    conjunction: FilterConjunction = Field(default=FilterConjunction.AND)
    rules: list[RuleClauseSchema | QueryTreeSchema] = Field(default_factory=list)


class TableColumnSortSchema(StrictBaseModel):
    """Table column sorting specification."""

    column: str = Field(..., description="Target column identifier")
    direction: SortDirection = Field(default=SortDirection.UNSORTED)


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


class PinColorSchemeSchema(StrictBaseModel):
    """Map pin coloring preferences."""

    mode: PinColorMode = Field(default=PinColorMode.UNIFORM)
    default_color: str = Field(default="#2563eb", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    palette: dict[str, str] = Field(
        default_factory=dict,
        description="Value-to-hex mappings for rating (1-5) or visit status",
    )
    rule_mappings: list[dict[str, Any]] = Field(default_factory=list)


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
