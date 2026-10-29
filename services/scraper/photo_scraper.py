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

"""Standalone Photo Scraper CLI Runner (T-018, T-020).

Adheres to:
- REQ-SCR-001: Strict read-only traversal over photo archives
- REQ-SCR-002: Recursive filesystem directory traversal
- REQ-SCR-004..007: Noise folder skipping
- REQ-SCR-008..009: Previous CSV incremental skipping and rescan override
- REQ-SCR-035: Standardized 12-column RFC 4180 CSV export
- REQ-SCR-036: Tags column left empty for downstream extractors
- REQ-SCR-038: Missing data left empty
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from vistarae_core.schemas.poi_export import POIExportRecord
from vistarae_core.services.csv_exporter import generate_standard_poi_csv

from services.scraper.cache import ScraperCacheManager
from services.scraper.location_resolver import (
    LocationResolver,
    validate_api_key_or_exit,
)
from services.scraper.metadata_extractor import (
    SUPPORTED_IMAGE_EXTENSIONS,
    extract_directory_metadata,
)
from services.scraper.path_parser import (
    is_noise_folder,
    parse_path_hierarchy,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vistarae.scraper")


def load_previous_directories(csv_path: Path | str | None) -> set[str]:
    """Parses already processed directories from previous CSV output.

    Args:
        csv_path: Optional path to a previously generated CSV file.

    Returns:
        Set of directory strings present in the 'Photo directory' column.
    """
    if not csv_path:
        return set()

    p = Path(csv_path)
    if not p.is_file():
        return set()

    recorded_dirs: set[str] = set()
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return set()

            dir_key = None
            for col in reader.fieldnames:
                if col.strip().lower() == "photo directory":
                    dir_key = col
                    break

            if dir_key:
                for row in reader:
                    val = row.get(dir_key)
                    if val and val.strip():
                        clean_val = val.strip()
                        recorded_dirs.add(clean_val)
                        with contextlib.suppress(Exception):
                            recorded_dirs.add(str(Path(clean_val).resolve()))
    except Exception as exc:
        logger.warning("Failed to parse previous CSV %s: %s", csv_path, exc)

    return recorded_dirs


def _is_poi_directory(folder: Path) -> bool:
    """Checks whether a folder directly contains supported image files."""
    try:
        for entry in folder.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                return True
    except (PermissionError, OSError):
        return False
    return False


def discover_candidate_directories(root_dir: Path) -> list[Path]:
    """Recursively traverses photo archives, skipping noise directories.

    Args:
        root_dir: Root photo archive folder.

    Returns:
        List of folders containing candidate POI photos.
    """
    candidates: list[Path] = []

    def _walk(curr: Path) -> None:
        if is_noise_folder(curr.name):
            return

        if _is_poi_directory(curr):
            candidates.append(curr)

        try:
            for entry in sorted(curr.iterdir()):
                if entry.is_dir() and not is_noise_folder(entry.name):
                    _walk(entry)
        except (PermissionError, OSError) as exc:
            logger.debug("Skipping unreadable directory %s: %s", curr, exc)

    _walk(root_dir)
    return candidates


def run_photo_scraper(
    input_dir: Path | str,
    output_csv: Path | str = "vistarae_pois.csv",
    cache_db: Path | str = ".scraper_cache.db",
    previous_csv: Path | str | None = None,
    rescan_existing: bool = False,
    api_key: str | None = None,
) -> int:
    """Executes the photo scraper pipeline end-to-end.

    Args:
        input_dir: Root photo directory to scan.
        output_csv: Output CSV destination path.
        cache_db: Path to the SQLite cache database.
        previous_csv: Optional previous CSV output for incremental scanning.
        rescan_existing: Flag overriding skip behavior on previous directories.
        api_key: Optional Gemini API key override for testing.

    Returns:
        Exit code (0 on success, non-zero on error).
    """
    root_path = Path(input_dir)
    if not root_path.exists() or not root_path.is_dir():
        logger.error("Specified input directory does not exist or is not a directory: %s", input_dir)
        return 1

    # Require Google API Key unless mock key provided (REQ-SCR-028)
    effective_api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not effective_api_key:
        validate_api_key_or_exit()

    # Load incremental diff directories
    previous_dirs = load_previous_directories(previous_csv)
    if previous_dirs:
        logger.info("Loaded %d previously processed directories from %s", len(previous_dirs), previous_csv)

    # Initialize cache & resolver
    cache_manager = ScraperCacheManager(db_path=cache_db)
    resolver = LocationResolver(cache_manager=cache_manager, api_key=effective_api_key)

    logger.info("Scanning media directories under: %s", root_path)
    candidates = discover_candidate_directories(root_path)
    logger.info("Discovered %d candidate POI folders", len(candidates))

    records: list[POIExportRecord] = []
    skipped_count = 0

    for folder in candidates:
        folder_str = str(folder)
        folder_resolved = str(folder.resolve())

        # Check incremental diffing (REQ-SCR-008)
        if not rescan_existing and (folder_str in previous_dirs or folder_resolved in previous_dirs):
            logger.debug("Skipping already processed directory: %s", folder)
            skipped_count += 1
            continue

        try:
            # 1. Read-only metadata extraction
            meta = extract_directory_metadata(folder)

            # 2. Path hierarchy parsing
            path_ctx = parse_path_hierarchy(folder)
            if not path_ctx.poi_name:
                continue

            # 3. Location resolution & ambiguity scoring
            resolved = resolver.resolve(
                path_context=path_ctx,
                latitude=meta.latitude,
                longitude=meta.longitude,
                tags=meta.tags,
            )

            # 4. Construct standardized export record
            record = POIExportRecord(
                poi_name=resolved.poi_name,
                street_address=[resolved.street] if resolved.street else [],
                town_city=[resolved.city] if resolved.city else [],
                state_province=[resolved.state_province] if resolved.state_province else [],
                zip_code=[resolved.postal_code] if resolved.postal_code else [],
                country=[resolved.country] if resolved.country else [],
                tags=[],  # Empty for photo scraper (REQ-SCR-036)
                latitude=meta.latitude,
                longitude=meta.longitude,
                dates_visited=[meta.earliest_date] if meta.earliest_date else [],
                photo_directory=folder_str,
                location_confidence_percent=resolved.location_confidence_percent,
            )
            records.append(record)
        except Exception as exc:
            logger.error("Error processing directory %s: %s", folder, exc, exc_info=True)

    # 5. Generate and write RFC 4180 CSV
    csv_content = generate_standard_poi_csv(records)
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(csv_content, encoding="utf-8", newline="\n")

    logger.info(
        "Successfully scraped %d POIs (%d skipped). Output saved to: %s",
        len(records),
        skipped_count,
        out_path,
    )
    return 0


def main(args: Sequence[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Vistarae Photo Scraper CLI: Extract standardized travel POIs from photo archives."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=str,
        help="Root directory containing photo folders to scan.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="vistarae_pois.csv",
        help="Destination path for the standardized RFC 4180 CSV output.",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=".scraper_cache.db",
        help="Path to SQLite cache database for location resolution.",
    )
    parser.add_argument(
        "--previous-csv",
        type=str,
        default=None,
        help="Path to previous CSV output for incremental skipping.",
    )
    parser.add_argument(
        "--rescan-existing",
        action="store_true",
        help="Force re-scanning of directories listed in the previous CSV.",
    )

    parsed = parser.parse_args(args)

    code = run_photo_scraper(
        input_dir=parsed.input_dir,
        output_csv=parsed.output_csv,
        cache_db=parsed.cache_dir,
        previous_csv=parsed.previous_csv,
        rescan_existing=parsed.rescan_existing,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
