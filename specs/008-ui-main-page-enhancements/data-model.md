<!--
Copyright (c) 2026 Tim Olker

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
-->

# Data Model & Schema Specification: Phase 8 — UI Main Page Enhancements

**Feature Identifier**: `008-ui-main-page-enhancements`  
**Date**: 2026-10-22  
**Status**: Completed  
**Spec Reference**: [spec.md](./spec.md) | **Research Reference**: [research.md](./research.md)

---

## 1. Database Schema (`filter_rules` Table)

Phase 8 introduces the `filter_rules` table to persist user-defined visual search profiles, table display preferences, and map pin coloring schemes.

### 1.1 SQLAlchemy 2.0 ORM Table Definition

```python
# packages/core/vistarae_core/adapters/db/tables.py

class FilterRuleTable(Base):
    """User-persisted POI search profile, table view configuration, and map pin coloring rules."""

    __tablename__ = "filter_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    query_tree: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    table_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    pin_color_scheme: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_filter_rules_user_name"),
        Index("ix_filter_rules_user_id_name", "user_id", "name"),
    )
```

### 1.2 Alembic Migration: `0006_filter_rules.py`

```python
"""Add filter_rules table with tenant isolation and JSONB configurations (0006_filter_rules.py).

Revision ID: 0006_filter_rules
Revises: 0005_poi_edit_enhancements
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_filter_rules"
down_revision = "0005_poi_edit_enhancements"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "filter_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query_tree", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("table_config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pin_color_scheme", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_filter_rules_user_name", "filter_rules", ["user_id", "name"])
    op.create_index("ix_filter_rules_user_id_name", "filter_rules", ["user_id", "name"])

def downgrade() -> None:
    op.drop_index("ix_filter_rules_user_id_name", table_name="filter_rules")
    op.drop_constraint("uq_filter_rules_user_name", "filter_rules", type_="unique")
    op.drop_table("filter_rules")
```

---

## 2. Pure Domain Entities & Value Objects

### 2.1 `FilterRuleEntity` Domain Model

```python
# packages/core/vistarae_core/domain/entities.py

@dataclass
class FilterRuleEntity:
    """Domain aggregate representing a traveler's saved search and view configuration."""

    id: UUID
    user_id: UUID
    name: str
    query_tree: dict[str, Any]
    table_config: dict[str, Any]
    pin_color_scheme: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

### 2.2 AST Value Objects & Types

```python
# packages/core/vistarae_core/domain/value_objects.py

class FilterOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    HAS_TAG = "has_tag"
    LACKS_TAG = "lacks_tag"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"

class FilterConjunction(StrEnum):
    AND = "AND"
    OR = "OR"

class PinColorMode(StrEnum):
    UNIFORM = "uniform"
    RATING = "rating"
    VISIT_STATUS = "visit_status"
    CUSTOM = "custom"

class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"
    UNSORTED = "unsorted"
```

---

## 3. Pydantic v2 Contracts & Schemas

### 3.1 Filter Rule Schemas (`schemas/filter_rule.py`)

All schemas inherit from `StrictBaseModel` enforcing `extra="forbid"` per Constitution Principle 5.

```python
# packages/core/vistarae_core/schemas/filter_rule.py

class RuleClauseSchema(StrictBaseModel):
    """Single condition rule in the query builder AST."""
    field: str = Field(..., description="Target POI field (e.g. 'country', 'rating', 'visit_state')")
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: Any | None = Field(default=None, description="Operand value (string, number, boolean, or null)")

class QueryTreeSchema(StrictBaseModel):
    """Recursive query builder AST tree node."""
    conjunction: FilterConjunction = Field(default=FilterConjunction.AND)
    rules: list[RuleClauseSchema | QueryTreeSchema] = Field(default_factory=list)

class TableColumnSortSchema(StrictBaseModel):
    column: str = Field(..., description="Target column identifier")
    direction: SortDirection = Field(default=SortDirection.UNSORTED)

class TableConfigSchema(StrictBaseModel):
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
    mode: PinColorMode = Field(default=PinColorMode.UNIFORM)
    default_color: str = Field(default="#2563eb", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
    palette: dict[str, str] = Field(
        default_factory=dict,
        description="Value-to-hex mappings for rating (1-5) or visit status"
    )
    rule_mappings: list[dict[str, Any]] = Field(default_factory=list)

class FilterRuleCreateRequest(StrictBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    query_tree: QueryTreeSchema = Field(default_factory=QueryTreeSchema)
    table_config: TableConfigSchema = Field(default_factory=TableConfigSchema)
    pin_color_scheme: PinColorSchemeSchema = Field(default_factory=PinColorSchemeSchema)

class FilterRuleUpdateRequest(StrictBaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    query_tree: QueryTreeSchema
    table_config: TableConfigSchema
    pin_color_scheme: PinColorSchemeSchema

class FilterRuleResponse(StrictBaseModel):
    id: UUID
    user_id: UUID
    name: str
    query_tree: QueryTreeSchema
    table_config: TableConfigSchema
    pin_color_scheme: PinColorSchemeSchema
    created_at: datetime
    updated_at: datetime

class FilterRuleListResponse(StrictBaseModel):
    items: list[FilterRuleResponse]
    total: int
```

### 3.2 Bulk Operation Schemas (`schemas/poi.py`)

```python
# packages/core/vistarae_core/schemas/poi.py (Additions)

class BulkEditAction(StrEnum):
    SET_RATING = "set_rating"
    ADD_VISIT_DATE = "add_visit_date"
    SET_VISIT_AGAIN = "set_visit_again"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    ADD_TO_LIST = "add_to_list"
    REMOVE_FROM_LIST = "remove_from_list"
    UPDATE_ADDRESS = "update_address"

class BulkAddressUpdatePayload(StrictBaseModel):
    city: str | None = Field(default=None, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    clear_fields: list[str] = Field(default_factory=list, description="Fields explicitly cleared to null")

class BulkEditPayload(StrictBaseModel):
    rating: int | None = Field(default=None, ge=0, le=5)
    visit_date: date | None = None
    want_to_visit_again: bool | None = None
    tag_name: str | None = Field(default=None, max_length=50)
    list_id: UUID | None = None
    address: BulkAddressUpdatePayload | None = None

class BulkEditRequest(StrictBaseModel):
    poi_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="Target POI IDs (max 500)")
    action: BulkEditAction = Field(...)
    payload: BulkEditPayload = Field(...)

class BulkDeleteRequest(StrictBaseModel):
    poi_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="Target POI IDs (max 500)")

class BulkOperationResponse(StrictBaseModel):
    modified_count: int = Field(..., ge=0)

class BulkDeleteResponse(StrictBaseModel):
    deleted_count: int = Field(..., ge=0)
```

---

## 4. Frontend State Models (`frontend/src/types/`)

### 4.1 Layout Mode State

```typescript
// frontend/src/types/layout.ts

export type LayoutMode = "split" | "map_only" | "table_only";
```

### 4.2 Query Builder State

```typescript
// frontend/src/types/filter.ts

export interface RuleClause {
  id: string;
  field: string;
  operator: string;
  value: any;
}

export interface QueryGroup {
  id: string;
  conjunction: "AND" | "OR";
  rules: (RuleClause | QueryGroup)[];
}

export interface TableConfig {
  visible_columns: string[];
  column_order: string[];
  sort: {
    column: string;
    direction: "asc" | "desc" | "unsorted";
  };
}

export interface PinColorScheme {
  mode: "uniform" | "rating" | "visit_status" | "custom";
  default_color: string;
  palette: Record<string, string>;
  rule_mappings: Array<{
    field: string;
    operator: string;
    value: any;
    color: string;
  }>;
}

export interface FilterRule {
  id: string;
  user_id: string;
  name: string;
  query_tree: QueryGroup;
  table_config: TableConfig;
  pin_color_scheme: PinColorScheme;
  created_at: string;
  updated_at: string;
}
```

---

## 5. Repository Ports (`packages/core/vistarae_core/ports/repositories.py`)

```python
class IFilterRuleRepository(Protocol):
    """Port interface for FilterRule persistence."""

    async def list_by_user(self, user_id: UUID) -> list[FilterRuleEntity]:
        ...

    async def get_by_id(self, rule_id: UUID, user_id: UUID) -> FilterRuleEntity | None:
        ...

    async def get_by_name(self, name: str, user_id: UUID) -> FilterRuleEntity | None:
        ...

    async def create(self, rule: FilterRuleEntity) -> FilterRuleEntity:
        ...

    async def update(self, rule: FilterRuleEntity) -> FilterRuleEntity:
        ...

    async def delete(self, rule_id: UUID, user_id: UUID) -> bool:
        ...
```
