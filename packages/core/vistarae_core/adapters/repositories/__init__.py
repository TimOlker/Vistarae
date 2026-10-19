# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Repositories adapter package — SQLAlchemy repository implementations."""

from vistarae_core.adapters.repositories.geocache_repo import (
    SqlAlchemyGeocodingCacheRepository,
)
from vistarae_core.adapters.repositories.idempotency_repo import (
    SqlAlchemyIdempotencyRepository,
)
from vistarae_core.adapters.repositories.list_repo import SqlAlchemyListRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.adapters.repositories.quota_repo import SqlAlchemyQuotaRepository
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.adapters.repositories.user_repo import SqlAlchemyUserRepository

__all__ = [
    "SqlAlchemyGeocodingCacheRepository",
    "SqlAlchemyIdempotencyRepository",
    "SqlAlchemyListRepository",
    "SqlAlchemyPOIRepository",
    "SqlAlchemyQuotaRepository",
    "SqlAlchemyTagRepository",
    "SqlAlchemyUserRepository",
]
