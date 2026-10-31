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
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT / "packages" / "core") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "packages" / "core"))

from google.genai.errors import ClientError  # noqa: E402
from vistarae_core.schemas.poi_export import POIExportRecord  # noqa: E402
from vistarae_core.services.csv_exporter import generate_standard_poi_csv  # noqa: E402

from services.scraper.cache import ScraperCacheManager  # noqa: E402
from services.scraper.location_resolver import (  # noqa: E402
    LocationResolver,
    check_ambiguity_penalty,
    validate_api_key_or_exit,
)
from services.scraper.metadata_extractor import (  # noqa: E402
    SUPPORTED_IMAGE_EXTENSIONS,
    extract_directory_metadata,
)
from services.scraper.path_parser import (  # noqa: E402
    is_noise_folder,
    parse_path_hierarchy,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vistarae.scraper")


def _format_duration(seconds: float) -> str:
    """Formats duration in seconds to HH:MM:SS or MM:SS format."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


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


def _filter_unprocessed_directories(
    candidates: list[Path],
    previous_dirs: set[str],
    rescan_existing: bool,
) -> tuple[list[Path], int]:
    """Filters candidate directories against previously processed entries."""
    to_process: list[Path] = []
    skipped_count = 0
    for folder in candidates:
        folder_str = str(folder)
        folder_resolved = str(folder.resolve())
        if not rescan_existing and (
            folder_str in previous_dirs or folder_resolved in previous_dirs
        ):
            logger.debug("Skipping already processed directory: %s", folder)
            skipped_count += 1
        else:
            to_process.append(folder)
    return to_process, skipped_count


def _build_confidence_source(
    meta: Any,
    resolved: Any,
    poi_name: str,
) -> str:
    """Builds a human-readable list of signals contributing to the confidence score."""
    parts: list[str] = []
    if meta.latitude is not None and meta.longitude is not None:
        parts.append("GPS (EXIF/Sidecar)")
    else:
        parts.append("Directory Path (No GPS)")

    if resolved.poi_name and resolved.poi_name.lower() != "unknown":
        parts.append("POI Identified")
    if resolved.street:
        parts.append("Street Address")
    if resolved.city:
        parts.append("City/Town")
    if resolved.state_province:
        parts.append("State/Province")
    if resolved.postal_code:
        parts.append("Postal Code")
    if resolved.country:
        parts.append("Country")

    if meta.latitude is None:
        penalty = check_ambiguity_penalty(poi_name, has_coords=False)
        if penalty is not None:
            parts.append(f"Ambiguity Penalty (Cap {penalty}%)")

    return "; ".join(parts)


def _log_ingestion_summary(
    records: list[POIExportRecord],
    processed_count: int,
    skipped_count: int,
    total_photos: int,
    total_duration: float,
    out_path: Path,
) -> None:
    """Logs aggregated summary metrics at the conclusion of ingestion."""
    unique_towns: set[str] = {t.strip() for r in records for t in r.town_city if t.strip()}
    unique_states: set[str] = {s.strip() for r in records for s in r.state_province if s.strip()}
    unique_countries: set[str] = {c.strip() for r in records for c in r.country if c.strip()}
    confidences = [
        r.location_confidence_percent for r in records if r.location_confidence_percent is not None
    ]
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

    logger.info("=" * 60)
    logger.info("Photo Scraper Ingestion Summary")
    logger.info("  POIs Extracted:                 %d", len(records))
    logger.info("  Directories Processed:          %d", processed_count)
    logger.info("  Directories Skipped (Previous): %d", skipped_count)
    logger.info("  Total Photos Analyzed:          %d", total_photos)
    logger.info("  Unique Towns / Cities:          %d", len(unique_towns))
    logger.info("  Unique States / Provinces:      %d", len(unique_states))
    logger.info("  Unique Countries:               %d", len(unique_countries))
    logger.info("  Average Location Confidence:    %.1f%%", avg_confidence)
    logger.info(
        "  Total Processing Time:          %s (%.2fs)",
        _format_duration(total_duration),
        total_duration,
    )
    logger.info("  Output CSV:                     %s", out_path)
    logger.info("=" * 60)


def run_photo_scraper(
    input_dir: Path | str,
    output_csv: Path | str = "vistarae_pois.csv",
    cache_db: Path | str = ".scraper_cache.db",
    previous_csv: Path | str | None = None,
    rescan_existing: bool = False,
    api_key: str | None = None,
    model_name: str | None = None,
    early_exit: bool = True,
    max_photos_per_dir: int = 50,
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
        logger.error(
            "Specified input directory does not exist or is not a directory: %s", input_dir
        )
        return 1

    # Require Google API Key unless mock key provided (REQ-SCR-028)
    effective_api_key = (
        api_key
        or os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    if not effective_api_key:
        validate_api_key_or_exit()

    # Load incremental diff directories
    previous_dirs = load_previous_directories(previous_csv)
    if previous_dirs:
        logger.info(
            "Loaded %d previously processed directories from %s", len(previous_dirs), previous_csv
        )

    # Initialize cache & resolver
    effective_model = (
        model_name or os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite"
    )
    cache_manager = ScraperCacheManager(db_path=cache_db)
    resolver = LocationResolver(
        cache_manager=cache_manager,
        api_key=effective_api_key,
        model_name=effective_model,
    )

    logger.info("Scanning media directories under: %s", root_path)
    candidates = discover_candidate_directories(root_path)
    to_process, skipped_count = _filter_unprocessed_directories(
        candidates, previous_dirs, rescan_existing
    )
    total_dirs = len(to_process)
    logger.info(
        "Discovered %d candidate POI folders (%d already processed in previous CSV, %d to process)",
        len(candidates),
        skipped_count,
        total_dirs,
    )

    records: list[POIExportRecord] = []
    total_photos_analyzed = 0
    start_total_time = time.monotonic()

    for idx, folder in enumerate(to_process, start=1):
        folder_str = str(folder)
        pct = (idx / total_dirs) * 100.0 if total_dirs > 0 else 100.0
        elapsed_so_far = time.monotonic() - start_total_time
        logger.info(
            "[%d/%d - %.1f%%] (Elapsed: %s) Processing directory: %s",
            idx,
            total_dirs,
            pct,
            _format_duration(elapsed_so_far),
            folder.name,
        )
        dir_start_time = time.monotonic()

        try:
            # 1. Read-only metadata extraction
            meta = extract_directory_metadata(
                folder,
                early_exit=early_exit,
                max_photos_per_dir=max_photos_per_dir,
            )
            total_photos_analyzed += meta.photos_inspected

            # 2. Path hierarchy parsing
            path_ctx = parse_path_hierarchy(folder)
            if not path_ctx.poi_name:
                dir_duration = time.monotonic() - dir_start_time
                logger.info(
                    "[%d/%d - %.1f%%] Finished in %.2fs (skipped - no POI name detected): %s",
                    idx,
                    total_dirs,
                    pct,
                    dir_duration,
                    folder.name,
                )
                continue

            # 3. Location resolution & ambiguity scoring
            resolved = resolver.resolve(
                path_context=path_ctx,
                latitude=meta.latitude,
                longitude=meta.longitude,
                tags=meta.tags,
            )

            # 4. Determine confidence calculation source signals
            conf_source_str = _build_confidence_source(meta, resolved, path_ctx.poi_name)

            # 5. Construct standardized export record
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
                confidence_source=conf_source_str,
            )
            records.append(record)

            dir_duration = time.monotonic() - dir_start_time
            logger.info(
                "[%d/%d - %.1f%%] Finished in %.2fs -> %s (%s, %s)",
                idx,
                total_dirs,
                pct,
                dir_duration,
                resolved.poi_name,
                resolved.city or "Unknown City",
                resolved.country,
            )
        except ClientError as exc:
            logger.error(
                "FATAL: Google Gemini API error: %s. Terminating traversal immediately to prevent repeated failures.",
                exc,
            )
            return 1
        except Exception as exc:
            logger.error("Error processing directory %s: %s", folder, exc, exc_info=True)

    # 5. Generate and write RFC 4180 CSV
    csv_content = generate_standard_poi_csv(records)
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(csv_content, encoding="utf-8", newline="\n")

    total_duration = time.monotonic() - start_total_time
    _log_ingestion_summary(
        records=records,
        processed_count=len(to_process),
        skipped_count=skipped_count,
        total_photos=total_photos_analyzed,
        total_duration=total_duration,
        out_path=out_path,
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
    parser.add_argument(
        "--model",
        default=None,
        help="Google Gemini model identifier (default: GEMINI_MODEL env var or gemini-3.5-flash-lite).",
    )
    parser.add_argument(
        "--no-early-exit",
        action="store_true",
        help="Disable smart early-exit and scan all photos in every directory.",
    )
    parser.add_argument(
        "--max-photos-per-dir",
        type=int,
        default=50,
        help="Maximum photos to scan in a folder without GPS before stopping (default: 50).",
    )

    parsed = parser.parse_args(args)

    code = run_photo_scraper(
        input_dir=parsed.input_dir,
        output_csv=parsed.output_csv,
        cache_db=parsed.cache_dir,
        previous_csv=parsed.previous_csv,
        rescan_existing=parsed.rescan_existing,
        model_name=parsed.model,
        early_exit=not parsed.no_early_exit,
        max_photos_per_dir=parsed.max_photos_per_dir,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
