# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Hierarchy cycle prevention and graph validation service (T-017).

Enforces directed acyclic graph (DAG) invariants for POI parent-child relationships:
- Immediate self-parenting prevention (poi_id == proposed_parent_id)
- Recursive ancestor traversal via CTE to prevent circular loops
- Re-parenting validation during interactive POI merges
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vistarae_core.domain.exceptions import CyclicHierarchyError


class HierarchyService:
    """Service validating hierarchy acyclicity and tree traversal for POIs."""

    def __init__(self, session: AsyncSession) -> None:
        """Initializes the hierarchy validation service.

        Args:
            session: Active SQLAlchemy AsyncSession.
        """
        self._session = session

    async def validate_no_cycle(
        self,
        user_id: UUID,
        poi_id: UUID,
        proposed_parent_id: UUID | None,
    ) -> None:
        """Validates that assigning proposed_parent_id to poi_id does not create a cycle.

        Args:
            user_id: Tenant UUID.
            poi_id: The POI being updated or merged.
            proposed_parent_id: The proposed parent POI UUID (or None to make root).

        Raises:
            CyclicHierarchyError: If proposed_parent_id equals poi_id or is a descendant.
        """
        if proposed_parent_id is None:
            return

        if poi_id == proposed_parent_id:
            raise CyclicHierarchyError(
                poi_id=str(poi_id), proposed_parent_id=str(proposed_parent_id)
            )

        # Query ancestors of proposed_parent_id using a recursive CTE.
        # If poi_id appears in the ancestor chain of proposed_parent_id,
        # then proposed_parent_id is a descendant of poi_id, forming a cycle.
        cte_query = text(
            """
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_poi_id
                FROM pois
                WHERE id = :proposed_parent_id AND user_id = :user_id
                UNION ALL
                SELECT p.id, p.parent_poi_id
                FROM pois p
                INNER JOIN ancestors a ON p.id = a.parent_poi_id
                WHERE p.user_id = :user_id
            )
            SELECT id FROM ancestors WHERE id = :poi_id LIMIT 1;
            """
        )

        result = await self._session.execute(
            cte_query,
            {
                "proposed_parent_id": proposed_parent_id,
                "user_id": user_id,
                "poi_id": poi_id,
            },
        )
        row = result.first()
        if row is not None:
            raise CyclicHierarchyError(
                poi_id=str(poi_id), proposed_parent_id=str(proposed_parent_id)
            )
