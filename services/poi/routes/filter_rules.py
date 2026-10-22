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

"""Filter Rules persistence endpoints (T-016).

Implements:
- GET /pois/filter-rules: List tenant-owned saved filter rules
- POST /pois/filter-rules: Create new named filter rule (with 409 Conflict check)
- GET /pois/filter-rules/{id}: Retrieve single saved rule by UUID
- PUT /pois/filter-rules/{id}: Overwrite existing saved rule by UUID
- DELETE /pois/filter-rules/{id}: Remove saved filter rule
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from vistarae_core.domain.entities import FilterRuleEntity, User
from vistarae_core.ports.repositories import IFilterRuleRepository
from vistarae_core.schemas.filter_rule import (
    FilterRuleCreateRequest,
    FilterRuleListResponse,
    FilterRuleResponse,
    FilterRuleUpdateRequest,
    PinColorSchemeSchema,
    QueryTreeSchema,
    TableConfigSchema,
)

from services.poi.dependencies import get_current_user, get_filter_rule_repo

router = APIRouter(prefix="/pois/filter-rules", tags=["filter-rules"])


def _entity_to_response(entity: FilterRuleEntity) -> FilterRuleResponse:
    """Serializes a FilterRuleEntity into FilterRuleResponse schema."""
    return FilterRuleResponse(
        id=entity.id,
        user_id=entity.user_id,
        name=entity.name,
        query_tree=QueryTreeSchema.model_validate(entity.query_tree)
        if isinstance(entity.query_tree, dict)
        else entity.query_tree,
        table_config=TableConfigSchema.model_validate(entity.table_config)
        if isinstance(entity.table_config, dict)
        else entity.table_config,
        pin_color_scheme=PinColorSchemeSchema.model_validate(entity.pin_color_scheme)
        if isinstance(entity.pin_color_scheme, dict)
        else entity.pin_color_scheme,
        created_at=entity.created_at or datetime.now(UTC),
        updated_at=entity.updated_at or datetime.now(UTC),
    )


@router.get("", response_model=FilterRuleListResponse)
async def list_filter_rules(
    current_user: User = Depends(get_current_user),
    repo: IFilterRuleRepository = Depends(get_filter_rule_repo),
) -> FilterRuleListResponse:
    """Retrieves all saved filter rules owned by the authenticated traveler."""
    rules = await repo.list_by_user(current_user.id)
    items = [_entity_to_response(r) for r in rules]
    return FilterRuleListResponse(items=items, total=len(items))


@router.post("", response_model=FilterRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_filter_rule(
    request: FilterRuleCreateRequest,
    current_user: User = Depends(get_current_user),
    repo: IFilterRuleRepository = Depends(get_filter_rule_repo),
) -> FilterRuleResponse:
    """Persists a new named filter rule.

    Returns 409 Conflict if a rule with the same name already exists for the user.
    """
    existing = await repo.get_by_name(request.name, current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Filter rule with name '{request.name}' already exists.",
        )

    now = datetime.now(UTC)
    entity = FilterRuleEntity(
        id=uuid4(),
        user_id=current_user.id,
        name=request.name,
        query_tree=request.query_tree.model_dump(),
        table_config=request.table_config.model_dump(),
        pin_color_scheme=request.pin_color_scheme.model_dump(),
        created_at=now,
        updated_at=now,
    )
    created = await repo.create(entity)
    return _entity_to_response(created)


@router.get("/{rule_id}", response_model=FilterRuleResponse)
async def get_filter_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    repo: IFilterRuleRepository = Depends(get_filter_rule_repo),
) -> FilterRuleResponse:
    """Retrieves a single saved filter rule by ID scoped to current user."""
    rule = await repo.get_by_id(rule_id, current_user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule {rule_id} not found.",
        )
    return _entity_to_response(rule)


@router.put("/{rule_id}", response_model=FilterRuleResponse)
async def update_filter_rule(
    rule_id: UUID,
    request: FilterRuleUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: IFilterRuleRepository = Depends(get_filter_rule_repo),
) -> FilterRuleResponse:
    """Updates/overwrites an existing filter rule scoped to current user."""
    rule = await repo.get_by_id(rule_id, current_user.id)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule {rule_id} not found.",
        )

    # Check for name collision with another rule
    existing_name = await repo.get_by_name(request.name, current_user.id)
    if existing_name is not None and existing_name.id != rule_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another filter rule with name '{request.name}' already exists.",
        )

    rule.name = request.name
    rule.query_tree = request.query_tree.model_dump()
    rule.table_config = request.table_config.model_dump()
    rule.pin_color_scheme = request.pin_color_scheme.model_dump()
    rule.updated_at = datetime.now(UTC)

    updated = await repo.update(rule)
    return _entity_to_response(updated)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    repo: IFilterRuleRepository = Depends(get_filter_rule_repo),
) -> None:
    """Deletes an existing filter rule record under tenant verification."""
    deleted = await repo.delete(rule_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule {rule_id} not found.",
        )
