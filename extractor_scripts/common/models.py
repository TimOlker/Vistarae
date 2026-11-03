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

"""Execution configuration and summary metrics models for CLI extractors."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from vistarae_core.domain.base import StrictBaseModel


class ExtractorConfig(StrictBaseModel):
    """Runtime configuration parameters for a CLI extractor run."""

    output_path: Path = Field(
        ...,
        description="Target CSV file path for extracted results",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of POI records to harvest (None for all)",
    )
    delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        description="Politeness delay between outbound network requests in seconds",
    )
    deep_scrape: bool = Field(
        default=False,
        description="Whether to navigate to detail subpages for full metadata",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Whether to read and write local HTML disk cache",
    )
    split_size: int = Field(
        default=2000,
        ge=1,
        le=2000,
        description="Maximum rows permitted per CSV partition file",
    )
    geocode_missing: bool = Field(
        default=False,
        description="Whether to query OpenStreetMap Nominatim for missing coordinates",
    )
    user_tags: list[str] = Field(
        default_factory=list,
        description="Operator-supplied custom tags to append to all extracted records",
    )
    dry_run: bool = Field(
        default=False,
        description="Whether to preview extraction results without writing files to disk",
    )


class ExtractionResult(StrictBaseModel):
    """Execution summary statistics produced after an extractor run."""

    extractor_name: str = Field(
        ...,
        description="Identifier of the executing extractor tool",
    )
    total_harvested: int = Field(
        ...,
        ge=0,
        description="Total raw entries inspected",
    )
    total_valid: int = Field(
        ...,
        ge=0,
        description="Total valid ExtractorRecord objects created",
    )
    total_errors: int = Field(
        default=0,
        ge=0,
        description="Count of parsing or network errors encountered",
    )
    output_files: list[Path] = Field(
        default_factory=list,
        description="Paths of all output CSV files generated",
    )
    duration_seconds: float = Field(
        ...,
        ge=0.0,
        description="Elapsed wall-clock execution time in seconds",
    )
