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

"""Repositories adapter package — SQLAlchemy repository implementations."""

from vistarae_core.adapters.repositories.geocache_repo import (
    SqlAlchemyGeocodingCacheRepository,
)
from vistarae_core.adapters.repositories.idempotency_repo import (
    SqlAlchemyIdempotencyRepository,
)
from vistarae_core.adapters.repositories.ingest_repo import IngestJobRepository
from vistarae_core.adapters.repositories.list_repo import SqlAlchemyListRepository
from vistarae_core.adapters.repositories.poi_repo import SqlAlchemyPOIRepository
from vistarae_core.adapters.repositories.quota_repo import SqlAlchemyQuotaRepository
from vistarae_core.adapters.repositories.tag_repo import SqlAlchemyTagRepository
from vistarae_core.adapters.repositories.user_repo import SqlAlchemyUserRepository

__all__ = [
    "IngestJobRepository",
    "SqlAlchemyGeocodingCacheRepository",
    "SqlAlchemyIdempotencyRepository",
    "SqlAlchemyListRepository",
    "SqlAlchemyPOIRepository",
    "SqlAlchemyQuotaRepository",
    "SqlAlchemyTagRepository",
    "SqlAlchemyUserRepository",
]

