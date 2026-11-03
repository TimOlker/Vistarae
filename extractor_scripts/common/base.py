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

"""Abstract base class and Click CLI infrastructure for specialized extractors."""

from __future__ import annotations

import functools
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from vistarae_core.schemas.extractor import ExtractorRecord

from extractor_scripts.common.exporter import CSVExporter
from extractor_scripts.common.geo import NominatimGeoClient
from extractor_scripts.common.http_client import ResilientHttpClient
from extractor_scripts.common.models import ExtractionResult, ExtractorConfig


def extractor_options(default_output: str | None = None) -> Callable[[Any], Any]:
    """Decorator attaching standardized Click options to an extractor CLI command.

    Args:
        default_output: Optional default output file name (e.g. 'nps_sites.csv').

    Returns:
        Click command wrapper with options attached.
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @click.command(context_settings={"help_option_names": ["-h", "--help"]})
        @click.option(
            "-o",
            "--output",
            "output_path",
            type=click.Path(path_type=Path),
            default=Path(default_output) if default_output else None,
            help="Destination path for output CSV dataset.",
        )
        @click.option(
            "-l",
            "--limit",
            type=click.IntRange(min=1),
            default=None,
            help="Maximum number of POI records to harvest.",
        )
        @click.option(
            "-d",
            "--delay",
            "delay_seconds",
            type=click.FloatRange(min=0.1),
            default=1.0,
            show_default=True,
            help="Politeness delay between network requests in seconds.",
        )
        @click.option(
            "--deep/--shallow",
            default=False,
            show_default=True,
            help="Harvest full details from individual subpages.",
        )
        @click.option(
            "--cache/--no-cache",
            "cache_enabled",
            default=True,
            show_default=True,
            help="Read and write raw responses to local disk cache.",
        )
        @click.option(
            "--split-size",
            type=click.IntRange(min=1, max=2000),
            default=2000,
            show_default=True,
            help="Maximum rows permitted per CSV partition file.",
        )
        @click.option(
            "--geocode/--no-geocode",
            "geocode_missing",
            default=False,
            show_default=True,
            help="Query Nominatim for missing coordinates (1 req/sec).",
        )
        @click.option(
            "-t",
            "--tag",
            "user_tags",
            multiple=True,
            type=str,
            help="Custom tags to append to all extracted records.",
        )
        @click.option(
            "--dry-run",
            is_flag=True,
            default=False,
            help="Preview extraction without writing files to disk.",
        )
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return f(*args, **kwargs)

        return wrapper

    return decorator


class BaseExtractor(ABC):
    """Abstract base class establishing lifecycle and utilities for all extractors."""

    name: str = "BaseExtractor"
    default_tags: list[str] = []

    def __init__(
        self,
        config: ExtractorConfig,
        http_client: ResilientHttpClient | None = None,
        geo_client: NominatimGeoClient | None = None,
    ) -> None:
        """Initializes the base extractor.

        Args:
            config: Runtime configuration options.
            http_client: Optional pre-configured HTTP client (e.g. for testing).
            geo_client: Optional Nominatim geocoding client.
        """
        self.config = config
        self._owned_http = http_client is None
        self._owned_geo = geo_client is None

        self.http = http_client or ResilientHttpClient(
            delay_seconds=config.delay_seconds,
            cache_enabled=config.cache_enabled,
        )
        self.geo = geo_client or NominatimGeoClient() if config.geocode_missing else None

    def close(self) -> None:
        """Disposes owned networking transports."""
        if self._owned_http:
            self.http.close()
        if self.geo and self._owned_geo:
            self.geo.close()

    def resolve_tags(self, conditional_tags: list[str] | None = None) -> list[str]:
        """Resolves the unified tags list combining baseline, conditional, and CLI tags.

        Args:
            conditional_tags: Specific tags determined per-record.

        Returns:
            Deduplicated list of tags preserving resolution order.
        """
        combined: list[str] = []
        # Tier 1: Baseline default tags
        for t in self.default_tags:
            if t not in combined:
                combined.append(t)
        # Tier 2: Conditional per-record tags
        if conditional_tags:
            for t in conditional_tags:
                if t and t not in combined:
                    combined.append(t)
        # Tier 3: User CLI tags
        for t in self.config.user_tags:
            if t and t not in combined:
                combined.append(t)
        return combined

    @abstractmethod
    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests and parses raw records into ExtractorRecord instances.

        Returns:
            Collection of ExtractorRecord domain models ready for export.
        """

    def extract(self) -> ExtractionResult:
        """Executes the extraction workflow, formats output, and computes metrics.

        Returns:
            ExtractionResult summary object.
        """
        t0 = time.monotonic()
        try:
            records = self.harvest_records()
            if self.config.limit is not None:
                records = records[: self.config.limit]

            output_files: list[Path] = []
            if not self.config.dry_run and records:
                output_files = CSVExporter.export(
                    records=records,
                    output_path=self.config.output_path,
                    split_size=self.config.split_size,
                )
            elif not self.config.dry_run:
                output_files = CSVExporter.export(
                    records=[],
                    output_path=self.config.output_path,
                    split_size=self.config.split_size,
                )

            duration = round(time.monotonic() - t0, 2)
            return ExtractionResult(
                extractor_name=self.name,
                total_harvested=len(records),
                total_valid=len(records),
                total_errors=0,
                output_files=output_files,
                duration_seconds=duration,
            )
        finally:
            self.close()


def print_summary(result: ExtractionResult, dry_run: bool = False) -> None:
    """Prints a standardized terminal summary table of extraction results.

    Args:
        result: Extraction execution metrics.
        dry_run: Whether dry-run mode was active.
    """
    mode_str = " (DRY RUN)" if dry_run else ""
    click.echo("=" * 60)
    click.echo(f"Vistarae Extractor Summary: {result.extractor_name}{mode_str}")
    click.echo("=" * 60)
    click.echo(f"Total Records Harvested: {result.total_harvested}")
    click.echo(f"Total Valid Records:     {result.total_valid}")
    click.echo(f"Validation Errors:       {result.total_errors}")
    if dry_run:
        click.echo("Output Files:            [None - Dry Run Mode]")
    else:
        click.echo("Output Files Generated:")
        for path in result.output_files:
            click.echo(f"  - {path}")
    click.echo(f"Execution Time:          {result.duration_seconds}s")
    click.echo("=" * 60)


def run_extractor_cli(
    extractor_cls: type[BaseExtractor],
    default_filename: str,
    output_path: Path | None,
    limit: int | None,
    delay_seconds: float,
    deep: bool,
    cache_enabled: bool,
    split_size: int,
    geocode_missing: bool,
    user_tags: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Instantiates and executes an extractor CLI command from parsed Click options.

    Args:
        extractor_cls: Concrete subclass of BaseExtractor to execute.
        default_filename: Fallback filename if output_path is not specified.
        output_path: Destination path specified by user.
        limit: Optional maximum record limit.
        delay_seconds: Seconds between HTTP requests.
        deep: Whether to traverse subpages.
        cache_enabled: Whether to read/write response cache.
        split_size: Partition size ceiling.
        geocode_missing: Whether to geocode missing coordinates.
        user_tags: Custom tags provided on command line.
        dry_run: Whether to skip writing files.
    """
    target_path = output_path or Path(default_filename)
    config = ExtractorConfig(
        output_path=target_path,
        limit=limit,
        delay_seconds=delay_seconds,
        deep_scrape=deep,
        cache_enabled=cache_enabled,
        split_size=split_size,
        geocode_missing=geocode_missing,
        user_tags=list(user_tags),
        dry_run=dry_run,
    )
    extractor = extractor_cls(config=config)
    try:
        result = extractor.extract()
        print_summary(result, dry_run=dry_run)
    except Exception as exc:
        click.echo(f"Error during extraction: {exc}", err=True)
        sys.exit(1)
