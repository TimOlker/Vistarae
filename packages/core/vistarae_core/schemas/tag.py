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

"""Tag domain and API schemas enforcing Constitution Principle 5."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from pydantic import Field, field_validator

from vistarae_core.schemas.base import StrictBaseModel
from vistarae_core.schemas.errors import ProblemDetails


def slugify_tag_name(name: str) -> str:
    """Generate a clean slug identifier from a tag display name."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    cleaned = re.sub(r"^_+|_+$", "", cleaned)
    return cleaned or "tag"


class TagCreateRequest(StrictBaseModel):
    """Payload to create or register a new user-scoped tag."""

    name: str = Field(min_length=1, max_length=64, description="Human readable display name")
    slug: str | None = Field(
        default=None,
        validate_default=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Immutable slug identifier (auto-derived from name if omitted)",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Array of searchable synonym aliases",
    )

    @field_validator("slug", mode="before")
    @classmethod
    def set_default_slug(cls, v: str | None, info) -> str | None:
        """Auto-derive slug from name if not provided."""
        if v:
            return v.strip().lower()
        name = info.data.get("name") if hasattr(info, "data") else None
        if name and isinstance(name, str):
            return slugify_tag_name(name)
        return v


class TagResponse(StrictBaseModel):
    """Detailed tag representation returned to clients."""

    id: uuid.UUID
    name: str
    slug: str = Field(default="", validate_default=True)
    aliases: list[str] = Field(default_factory=list)
    poi_count: int = Field(
        default=0, description="Count of POIs currently associated with this tag"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("slug", mode="before")
    @classmethod
    def set_default_slug(cls, v: str | None, info) -> str:
        """Auto-derive slug from name if omitted."""
        if v:
            return v.strip().lower()
        name = info.data.get("name") if hasattr(info, "data") else None
        if name and isinstance(name, str):
            return slugify_tag_name(name)
        return ""


class TagInUseProblemDetails(ProblemDetails):
    """RFC 7807 problem details when tag deletion is blocked by referential integrity."""

    type: str = Field(
        default="urn:vistarae:error:tag-in-use",
        description="Problem type identifier for tag referential integrity conflicts",
    )
    title: str = Field(
        default="Tag in use",
        description="Short summary of error",
    )
    status: int = Field(
        default=409,
        description="HTTP status code (409 Conflict)",
    )
    referencing_poi_count: int = Field(
        ...,
        description="Number of POIs referencing this tag",
    )
    remediation_filter_url: str = Field(
        ...,
        description="Direct link to filter the POI Table by this tag for bulk remediation",
    )
