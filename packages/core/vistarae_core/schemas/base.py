# Copyright (c) 2026 Vistarae. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base schema configuration for Pydantic v2 boundary models.

Enforces Constitution Principle 5: extra='forbid', validate_assignment=True,
and str_strip_whitespace=True.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    """Immutable boundary model forbidding unmapped fields and stripping whitespace."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )
