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

"""Hierarchy cycle prevention and graph validation service (T-017).

Enforces directed acyclic graph (DAG) invariants for POI parent-child relationships:
- Immediate self-parenting prevention (poi_id == proposed_parent_id)
- Recursive ancestor traversal via CTE to prevent circular loops
- Re-parenting validation during interactive POI merges
"""

from __future__ import annotations

from typing import Any
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

    async def assert_no_cycle(
        self,
        poi_id: UUID,
        proposed_parent_id: UUID | None,
        user_id: UUID | None = None,
    ) -> None:
        """Alias for validate_no_cycle ensuring backward compatibility."""
        if proposed_parent_id is None:
            return
        if poi_id == proposed_parent_id:
            raise CyclicHierarchyError(
                poi_id=str(poi_id), proposed_parent_id=str(proposed_parent_id)
            )
        if user_id is not None:
            await self.validate_no_cycle(
                user_id=user_id,
                poi_id=poi_id,
                proposed_parent_id=proposed_parent_id,
            )

    async def get_candidate_parents(
        self,
        user_id: UUID,
        exclude_poi_id: UUID | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Returns candidate parent POIs, excluding self and all descendants.

        Args:
            user_id: Tenant UUID.
            exclude_poi_id: Active POI UUID to exclude along with its descendants.
            query: Optional substring query to filter candidate names.
            limit: Maximum candidates to return (default 20).

        Returns:
            List of candidate dicts with id, name, location_summary.
        """
        params: dict[str, Any] = {
            "user_id": user_id,
            "limit": limit,
        }

        if exclude_poi_id is not None:
            params["exclude_poi_id"] = exclude_poi_id
            cte_sql = """
            WITH RECURSIVE descendants AS (
                SELECT id FROM pois WHERE id = :exclude_poi_id AND user_id = :user_id
                UNION ALL
                SELECT p.id FROM pois p
                INNER JOIN descendants d ON p.parent_poi_id = d.id
                WHERE p.user_id = :user_id
            )
            SELECT p.id, p.name, p.city, p.addresses
            FROM pois p
            WHERE p.user_id = :user_id
              AND p.id NOT IN (SELECT id FROM descendants)
            """
        else:
            cte_sql = """
            SELECT p.id, p.name, p.city, p.addresses
            FROM pois p
            WHERE p.user_id = :user_id
            """

        if query and query.strip():
            cte_sql += " AND p.name ILIKE :name_pattern"
            params["name_pattern"] = f"%{query.strip()}%"

        cte_sql += " ORDER BY p.name ASC LIMIT :limit;"

        result = await self._session.execute(text(cte_sql), params)
        candidates: list[dict[str, Any]] = []
        for row in result.all():
            r_id, r_name, r_city, r_addresses = row[0], row[1], row[2], row[3]
            summary = None
            if r_addresses and len(r_addresses) > 0 and isinstance(r_addresses[0], dict):
                first_addr = r_addresses[0]
                city = first_addr.get("city") or r_city
                state = first_addr.get("state_province")
                country = first_addr.get("country")
                parts = [p for p in [city, state, country] if p]
                if parts:
                    summary = ", ".join(parts)
            elif r_city:
                summary = r_city

            candidates.append(
                {
                    "id": r_id,
                    "name": r_name,
                    "location_summary": summary,
                }
            )

        return candidates
