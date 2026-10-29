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

"""Core domain exceptions.

Independent domain error definitions decoupled from HTTP and transport layers.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain logic violations."""

    def __init__(self, message: str) -> None:
        """Initializes a domain error.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message)
        self.message = message


class AccountDisabledError(DomainError):
    """Raised when an operation targets an administratively disabled tenant."""

    def __init__(self, user_id: str) -> None:
        """Initializes an account disabled error.

        Args:
            user_id: UUID string of the disabled user.
        """
        super().__init__(f"Account {user_id} is disabled.")
        self.user_id = user_id


class QuotaExceededError(DomainError):
    """Raised when an operation exceeds monthly token quota or rate limit."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Initializes a quota exceeded error.

        Args:
            message: Explanation of the quota boundary exceeded.
            retry_after: Optional seconds remaining before quota reset.
        """
        super().__init__(message)
        self.retry_after = retry_after


class IdempotencyConflictError(DomainError):
    """Raised when a concurrent mutating operation with the same key is in progress."""

    def __init__(self, idempotency_key: str) -> None:
        """Initializes an idempotency conflict error.

        Args:
            idempotency_key: The client key currently marked PENDING.
        """
        super().__init__(f"Concurrent mutation in progress for key: {idempotency_key}")
        self.idempotency_key = idempotency_key


class TenantNotFoundError(DomainError):
    """Raised when a tenant user account does not exist."""

    def __init__(self, identifier: str) -> None:
        """Initializes a tenant not found error.

        Args:
            identifier: User ID or Cognito sub that was not found.
        """
        super().__init__(f"Tenant account {identifier} not found.")
        self.identifier = identifier


class CyclicHierarchyError(DomainError):
    """Raised when setting a POI parent would cause a directed cyclic loop."""

    def __init__(self, poi_id: str, proposed_parent_id: str) -> None:
        """Initializes a cyclic hierarchy error.

        Args:
            poi_id: ID of the POI being updated.
            proposed_parent_id: Proposed parent ID that creates a cycle.
        """
        super().__init__(
            f"Assigning parent {proposed_parent_id} to POI {poi_id} would create a circular hierarchy."
        )
        self.poi_id = poi_id
        self.proposed_parent_id = proposed_parent_id


class TagLimitExceededError(DomainError):
    """Raised when assigning more than 30 tags to a single POI."""

    def __init__(self, count: int, limit: int = 30) -> None:
        """Initializes a tag limit exceeded error.

        Args:
            count: Number of tags attempted.
            limit: Maximum allowed tags per POI.
        """
        super().__init__(f"Cannot assign {count} tags to POI; maximum limit is {limit}.")
        self.count = count
        self.limit = limit


class GeocodingTimeoutError(DomainError):
    """Raised when an external geocoding resolution times out beyond 3.0s."""

    def __init__(self, query: str, timeout_seconds: float = 3.0) -> None:
        """Initializes a geocoding timeout error.

        Args:
            query: The address or query string that timed out.
            timeout_seconds: Timeout ceiling in seconds.
        """
        super().__init__(
            f"Geocoding request for '{query}' exceeded {timeout_seconds}s timeout ceiling."
        )
        self.query = query
        self.timeout_seconds = timeout_seconds


class InvalidCoordinateError(DomainError):
    """Raised when coordinates fall outside canonical WGS-84 bounding limits."""

    def __init__(self, lat: float, lon: float) -> None:
        """Initializes an invalid coordinate error.

        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
        """
        super().__init__(
            f"Invalid WGS-84 coordinates: lat={lat}, lon={lon}. Lat must be in [-90, 90], Lon in [-180, 180]."
        )
        self.lat = lat
        self.lon = lon


class POINotFoundError(DomainError):
    """Raised when a requested POI is not found for the tenant."""

    def __init__(self, poi_id: str) -> None:
        """Initializes a POI not found error.

        Args:
            poi_id: ID of the requested POI.
        """
        super().__init__(f"Point of interest {poi_id} not found.")
        self.poi_id = poi_id


class IngestCandidateNotFoundError(DomainError):
    """Raised when a staged candidate cannot be found for the tenant and job."""

    def __init__(self, candidate_id: str) -> None:
        """Initializes an ingest candidate not found error.

        Args:
            candidate_id: ID of the requested staged candidate.
        """
        super().__init__(f"Staged candidate {candidate_id} not found.")
        self.candidate_id = candidate_id


class IngestJobNotFoundError(DomainError):
    """Raised when an ingestion job cannot be found for the tenant."""

    def __init__(self, job_id: str) -> None:
        """Initializes an ingest job not found error.

        Args:
            job_id: ID of the requested ingestion job.
        """
        super().__init__(f"Ingestion job {job_id} not found.")
        self.job_id = job_id


class FileTooLargeError(DomainError):
    """Raised when an uploaded file exceeds the maximum permitted size."""

    def __init__(self, size: int, max_size: int = 2_097_152) -> None:
        """Initializes a file too large error.

        Args:
            size: Actual file size in bytes.
            max_size: Maximum permitted file size in bytes (default 2MB).
        """
        super().__init__(
            f"File size {size} bytes exceeds maximum allowed limit of {max_size} bytes."
        )
        self.size = size
        self.max_size = max_size


class RowLimitExceededError(DomainError):
    """Raised when an uploaded CSV exceeds the maximum permitted row count."""

    def __init__(self, count: int, max_rows: int = 2000) -> None:
        """Initializes a row limit exceeded error.

        Args:
            count: Total data rows in the file.
            max_rows: Maximum permitted rows (default 2,000).
        """
        super().__init__(f"Row count {count} exceeds maximum allowed limit of {max_rows} rows.")
        self.count = count
        self.max_rows = max_rows


class InvalidMimeTypeError(DomainError):
    """Raised when an uploaded file does not match allowed CSV MIME types."""

    def __init__(self, mime_type: str, allowed: list[str] | None = None) -> None:
        """Initializes an invalid MIME type error.

        Args:
            mime_type: Uploaded MIME type.
            allowed: List of acceptable MIME types.
        """
        allowed_types = allowed or ["text/csv", "text/plain", "application/vnd.ms-excel"]
        super().__init__(f"MIME type '{mime_type}' is invalid. Allowed: {allowed_types}.")
        self.mime_type = mime_type
        self.allowed = allowed_types


class InvalidCSVHeaderError(DomainError):
    """Raised when a CSV upload is missing required canonical column headers."""

    def __init__(self, missing_headers: list[str]) -> None:
        """Initializes an invalid CSV header error.

        Args:
            missing_headers: Required headers that were not found.
        """
        super().__init__(
            f"CSV header validation failed: missing required column(s) {missing_headers}."
        )
        self.missing_headers = missing_headers
