# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Abstract repository port interfaces.

Isolates external persistence dependencies behind typing.Protocol contracts per
Constitution Principle 2 (Ports & Adapters). No ORM or driver imports allowed.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from uuid import UUID

from vistarae_core.domain.entities import (
    POI,
    GeocodingCacheEntry,
    IdempotencyRecord,
    ListEntity,
    PotentialDuplicateMatch,
    TagEntity,
    User,
    UserMetric,
    UserPreferences,
    UserQuota,
)
from vistarae_core.domain.value_objects import (
    BoundingBox,
    IdempotencyStatus,
    MergeResolutionRule,
    UserTier,
    VisitState,
    WGS84Point,
)


class IUserRepository(Protocol):
    """Persistence contract for tenant identity management."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Retrieves a user by primary key.

        Args:
            user_id: UUID of the target user.

        Returns:
            User entity or None if not found.
        """
        ...

    async def get_by_cognito_sub(self, sub: str) -> User | None:
        """Resolves a user entity from a Cognito JWT subject claim.

        Args:
            sub: Cognito unique subject identifier.

        Returns:
            Matched User entity or None.
        """
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Resolves a user entity by registered email address.

        Args:
            email: User's registered email address.

        Returns:
            Matched User entity or None.
        """
        ...

    async def create(
        self,
        user: User,
        preferences: UserPreferences,
        quotas: UserQuota,
        metrics: UserMetric,
    ) -> User:
        """Inserts a new tenant with all sub-tables atomically.

        Args:
            user: Core user aggregate.
            preferences: Partitioned tenant preferences.
            quotas: Initial quota allocation.
            metrics: Zero-initialized utilization metrics.

        Returns:
            Persisted User entity with database-assigned defaults.
        """
        ...

    async def update_profile(self, user_id: UUID, full_name: str) -> None:
        """Updates user display name.

        Args:
            user_id: UUID of the tenant.
            full_name: New display name value.
        """
        ...

    async def delete(self, user_id: UUID) -> None:
        """Permanently removes a tenant and all cascaded sub-records.

        Args:
            user_id: UUID of the tenant to delete.
        """
        ...

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        """Retrieves the preferences record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserPreferences entity or None if not found.
        """
        ...

    async def update_preferences(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies a partial update to tenant preferences.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        ...

    async def get_metrics(self, user_id: UUID) -> UserMetric | None:
        """Retrieves aggregate metrics for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserMetric entity or None.
        """
        ...

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves the quota record for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        ...


class IQuotaRepository(Protocol):
    """Persistence contract for rolling rate limiting and token budgeting."""

    async def get_quota(self, user_id: UUID) -> UserQuota | None:
        """Retrieves current quota state for a tenant.

        Args:
            user_id: UUID of the target tenant.

        Returns:
            UserQuota entity or None.
        """
        ...

    async def increment_request_count(
        self,
        user_id: UUID,
        tier: UserTier,
        window_seconds: int = 60,
    ) -> tuple[int, int, bool]:
        """Atomically increments rolling window request count.

        Args:
            user_id: UUID of the requesting tenant.
            tier: Current tenant governance tier.
            window_seconds: Rolling window duration in seconds.

        Returns:
            Tuple of (current_count, limit_for_tier, limit_exceeded).
        """
        ...

    async def check_token_budget(self, user_id: UUID, required_tokens: int) -> bool:
        """Verifies available token budget without mutating state.

        Args:
            user_id: UUID of the target tenant.
            required_tokens: Tokens required for the prospective operation.

        Returns:
            True if budget is available, False if exhausted.
        """
        ...

    async def increment_tokens(self, user_id: UUID, tokens: int) -> None:
        """Atomically adds consumed token count to quota and lifetime metrics.

        Args:
            user_id: UUID of the target tenant.
            tokens: Number of tokens consumed in the operation.
        """
        ...

    async def update_quota(self, user_id: UUID, updates: dict[str, Any]) -> None:
        """Applies administrative quota adjustments to a tenant.

        Args:
            user_id: UUID of the target tenant.
            updates: Dict of column names to new values.
        """
        ...


class IIdempotencyRepository(Protocol):
    """Persistence contract for duplicate mutation prevention."""

    async def get_or_create(
        self,
        user_id: UUID,
        key: str,
    ) -> tuple[IdempotencyStatus, int | None, dict[str, Any] | None]:
        """Atomically retrieves or creates an idempotency record.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client-provided idempotency key string.

        Returns:
            Tuple of (status, cached_response_code, cached_payload).
        """
        ...

    async def complete(
        self,
        user_id: UUID,
        key: str,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        """Marks key as COMPLETED and stores cached response.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to finalize.
            status_code: HTTP status code of the successful response.
            payload: Serializable response body to cache.
        """
        ...

    async def fail(self, user_id: UUID, key: str) -> None:
        """Marks a key FAILED so subsequent retries can proceed.

        Args:
            user_id: UUID of the requesting tenant.
            key: Client idempotency key to mark failed.
        """
        ...

    async def cleanup_older_than(self, hours: int = 24) -> int:
        """Purges idempotency records older than the given age.

        Args:
            hours: Age threshold in hours. Records older than this are deleted.

        Returns:
            Count of records deleted.
        """
        ...

    async def get_record(self, user_id: UUID, key: str) -> IdempotencyRecord | None:
        """Retrieves a single idempotency record by composite key.

        Args:
            user_id: UUID of the tenant.
            key: Client idempotency key string.

        Returns:
            IdempotencyRecord or None if not found.
        """
        ...


class IPOIRepository(Protocol):
    """Persistence contract for Point of Interest management and spatial discovery."""

    async def create(self, poi: POI) -> POI:
        """Creates a new POI record for the tenant.

        Args:
            poi: Domain POI aggregate to persist.

        Returns:
            Persisted POI with server timestamps.
        """
        ...

    async def get_by_id(self, poi_id: UUID, user_id: UUID) -> POI | None:
        """Retrieves a POI by ID scoped to tenant.

        Args:
            poi_id: UUID of the target POI.
            user_id: Tenant UUID.

        Returns:
            POI aggregate or None if not found.
        """
        ...

    async def update(self, poi: POI) -> POI:
        """Updates an existing POI record.

        Args:
            poi: Domain POI aggregate with updated fields.

        Returns:
            Updated POI aggregate.
        """
        ...

    async def delete(self, poi_id: UUID, user_id: UUID) -> bool:
        """Deletes a POI by ID scoped to tenant.

        Args:
            poi_id: UUID of the POI to remove.
            user_id: Tenant UUID.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def bulk_delete(self, poi_ids: list[UUID], user_id: UUID) -> int:
        """Deletes multiple POIs in a single transaction.

        Args:
            poi_ids: List of POI UUIDs to delete.
            user_id: Tenant UUID.

        Returns:
            Number of POIs deleted.
        """
        ...

    async def list_pois(
        self,
        user_id: UUID,
        bbox: BoundingBox | None = None,
        list_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
        state: str | None = None,
        country: str | None = None,
        visit_state: VisitState | None = None,
        visited_from: date | None = None,
        visited_to: date | None = None,
        hierarchy: str = "all",
        parent_id: UUID | None = None,
        text_query: str | None = None,
        semantic_vector: list[float] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[POI], int]:
        """Queries POIs with multi-facet spatial, planar bbox, and taxonomic filters.

        Args:
            user_id: Tenant UUID.
            bbox: Optional bounding box for planar viewport query.
            list_id: Filter by membership in a specific list.
            tag_ids: Filter by matching tag UUIDs.
            state: Filter by state containment in states JSONB array.
            country: Filter by country containment in countries JSONB array.
            visit_state: Filter by visit state enum.
            visited_from: Filter visited_dates on or after date.
            visited_to: Filter visited_dates on or before date.
            hierarchy: 'all', 'root_only', or 'children_only'.
            parent_id: Filter by direct parent POI ID.
            text_query: Fuzzy name or address query.
            semantic_vector: 768-dim query vector for cosine ranking.
            limit: Maximum items to return.
            offset: Pagination offset.

        Returns:
            Tuple of (matched POIs, total count).
        """
        ...

    async def find_potential_duplicates(
        self,
        user_id: UUID,
        name: str,
        point: WGS84Point,
        radius_meters: float,
        similarity_threshold: float = 0.60,
    ) -> list[PotentialDuplicateMatch]:
        """Finds candidate duplicate POIs using geodesic proximity and trigram similarity.

        Args:
            user_id: Tenant UUID.
            name: POI name to compare.
            point: Canonical coordinates of candidate.
            radius_meters: Geodesic search radius in meters.
            similarity_threshold: Trigram similarity cut-off score (default 0.60).

        Returns:
            List of potential duplicate matches ranked by confidence.
        """
        ...

    async def merge_pois(
        self,
        user_id: UUID,
        rule: MergeResolutionRule,
    ) -> POI:
        """Interactively merges two duplicate POIs atomically.

        Args:
            user_id: Tenant UUID.
            rule: Merge specification with attribute copy instructions.

        Returns:
            Merged canonical POI.

        Raises:
            CyclicHierarchyError: If re-parenting creates a cyclic loop.
            TagLimitExceededError: If merged tags exceed 30.
            POINotFoundError: If either source or target POI is not found.
        """
        ...

    async def bulk_attach_tags(
        self, user_id: UUID, poi_ids: list[UUID], tag_ids: list[UUID]
    ) -> int:
        """Attaches tags to multiple POIs in a single transaction.

        Args:
            user_id: Tenant UUID.
            poi_ids: List of POI UUIDs.
            tag_ids: List of Tag UUIDs to attach.

        Returns:
            Count of newly created associations.
        """
        ...

    async def bulk_detach_tags(
        self, user_id: UUID, poi_ids: list[UUID], tag_ids: list[UUID]
    ) -> int:
        """Detaches tags from multiple POIs in a single transaction.

        Args:
            user_id: Tenant UUID.
            poi_ids: List of POI UUIDs.
            tag_ids: List of Tag UUIDs to detach.

        Returns:
            Count of removed associations.
        """
        ...

    async def bulk_attach_lists(
        self, user_id: UUID, poi_ids: list[UUID], list_ids: list[UUID]
    ) -> int:
        """Attaches POIs to multiple lists in a single transaction.

        Args:
            user_id: Tenant UUID.
            poi_ids: List of POI UUIDs.
            list_ids: List of List UUIDs to attach.

        Returns:
            Count of newly created associations.
        """
        ...

    async def bulk_detach_lists(
        self, user_id: UUID, poi_ids: list[UUID], list_ids: list[UUID]
    ) -> int:
        """Detaches POIs from multiple lists in a single transaction.

        Args:
            user_id: Tenant UUID.
            poi_ids: List of POI UUIDs.
            list_ids: List of List UUIDs to detach.

        Returns:
            Count of removed associations.
        """
        ...


class IListRepository(Protocol):
    """Persistence contract for curated POI lists."""

    async def create(self, list_entity: ListEntity) -> ListEntity:
        """Creates a new list.

        Args:
            list_entity: List entity to persist.

        Returns:
            Persisted list entity.
        """
        ...

    async def get_by_id(self, list_id: UUID, user_id: UUID | None = None) -> ListEntity | None:
        """Retrieves a list by ID. If user_id is provided, checks ownership or is_public.

        Args:
            list_id: UUID of the list.
            user_id: Optional requesting user UUID.

        Returns:
            List entity or None if not found or unauthorized.
        """
        ...

    async def list_by_user(self, user_id: UUID) -> list[ListEntity]:
        """Lists all collections owned by the user.

        Args:
            user_id: Tenant UUID.

        Returns:
            List of owned ListEntity objects.
        """
        ...

    async def update(self, list_entity: ListEntity) -> ListEntity:
        """Updates a list's title, description, or visibility.

        Args:
            list_entity: Updated ListEntity.

        Returns:
            Updated ListEntity.
        """
        ...

    async def delete(self, list_id: UUID, user_id: UUID) -> bool:
        """Deletes a list owned by the user.

        Args:
            list_id: UUID of the list to delete.
            user_id: Tenant UUID.

        Returns:
            True if deleted, False otherwise.
        """
        ...


class ITagRepository(Protocol):
    """Persistence contract for user taxonomy tags."""

    async def create(self, tag: TagEntity) -> TagEntity:
        """Creates a new tag.

        Args:
            tag: Tag entity to persist.

        Returns:
            Persisted TagEntity.
        """
        ...

    async def get_by_id(self, tag_id: UUID, user_id: UUID) -> TagEntity | None:
        """Retrieves a tag by ID.

        Args:
            tag_id: Tag UUID.
            user_id: Tenant UUID.

        Returns:
            TagEntity or None if not found.
        """
        ...

    async def get_by_name(self, name: str, user_id: UUID) -> TagEntity | None:
        """Retrieves a tag by name for the tenant.

        Args:
            name: Tag name string.
            user_id: Tenant UUID.

        Returns:
            TagEntity or None if not found.
        """
        ...

    async def list_by_user(self, user_id: UUID) -> list[TagEntity]:
        """Lists all tags defined by the user.

        Args:
            user_id: Tenant UUID.

        Returns:
            List of TagEntity objects.
        """
        ...

    async def delete(self, tag_id: UUID, user_id: UUID) -> bool:
        """Deletes a tag.

        Args:
            tag_id: UUID of the tag.
            user_id: Tenant UUID.

        Returns:
            True if deleted, False otherwise.
        """
        ...

    async def get_tags_for_poi(self, poi_id: UUID) -> list[TagEntity]:
        """Retrieves all tags attached to a specific POI.

        Args:
            poi_id: UUID of the POI.

        Returns:
            List of TagEntity objects.
        """
        ...

    async def get_tags_for_pois(self, poi_ids: list[UUID]) -> dict[UUID, list[TagEntity]]:
        """Batch retrieves tags for multiple POIs.

        Args:
            poi_ids: List of POI UUIDs.

        Returns:
            Dictionary mapping POI UUID to list of TagEntity objects.
        """
        ...

    async def get_or_create(self, user_id: UUID, name: str) -> TagEntity:
        """Retrieves an existing tag or creates a new one.

        Args:
            user_id: Tenant UUID.
            name: Tag name string.

        Returns:
            TagEntity domain model.
        """
        ...


class IGeocodingCacheRepository(Protocol):
    """Persistence contract for SHA-256 hashed geocoding cache entries."""

    async def get(self, query_hash: str) -> GeocodingCacheEntry | None:
        """Retrieves a cached geocoding entry by SHA-256 hash if not expired.

        Args:
            query_hash: 64-char hex string SHA-256 digest.

        Returns:
            GeocodingCacheEntry or None if missing or expired.
        """
        ...

    async def set(self, entry: GeocodingCacheEntry) -> None:
        """Persists or refreshes a geocoding cache entry with a 90-day TTL.

        Args:
            entry: Cache entry to store.
        """
        ...

    async def cleanup_expired(self) -> int:
        """Evicts expired geocoding cache rows (expires_at <= NOW()).

        Returns:
            Number of evicted rows.
        """
        ...
