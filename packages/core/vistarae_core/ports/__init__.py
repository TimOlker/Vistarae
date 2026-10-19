# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Port interfaces package for dependency inversion."""

from vistarae_core.ports.embedding import IEmbeddingPort
from vistarae_core.ports.geocoding import GeocodingResult, IGeocodingPort
from vistarae_core.ports.identity import IIdentityProvider
from vistarae_core.ports.queue import IMessageQueue
from vistarae_core.ports.repositories import (
    IGeocodingCacheRepository,
    IIdempotencyRepository,
    IListRepository,
    IPOIRepository,
    IQuotaRepository,
    ITagRepository,
    IUserRepository,
)

__all__ = [
    "GeocodingResult",
    "IEmbeddingPort",
    "IGeocodingCacheRepository",
    "IGeocodingPort",
    "IIdentityProvider",
    "IIdempotencyRepository",
    "IListRepository",
    "IMessageQueue",
    "IPOIRepository",
    "IQuotaRepository",
    "ITagRepository",
    "IUserRepository",
]
