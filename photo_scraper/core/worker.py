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

"""Multi-worker photo scraping and location cataloging engine (T-043).

Traverses photo directories, extracts EXIF coordinates and timestamps,
invokes Gemini Flash-Lite structured POI inference, interactively triages
uncertain locations (or marks NEEDS_REVIEW), and exports sanitized CSVs.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from vistarae_core.schemas.ingest import PhotoPOIInference

from photo_scraper.core.cache import PersistentCache, flush_all_caches
from photo_scraper.core.config import settings
from photo_scraper.core.db import ScraperDatabase
from photo_scraper.core.exif import SUPPORTED_EXTENSIONS, extract_image_metadata
from photo_scraper.core.geocoder import GeocodedLocation, ScraperGeocoder
from photo_scraper.core.llm_parser import GENERIC_CATEGORIES, GeminiPathParser
from photo_scraper.core.path_parser import (
    add_skip_over,
    is_path_excluded,
    is_skip_folder,
    parse_directory_path,
)

logger = logging.getLogger("vistarae.photo_scraper.worker")

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_field(val: Any) -> str:
    """Neutralizes spreadsheet formula injection prefixes."""
    if val is None:
        return ""
    s = str(val)
    if s.startswith(FORMULA_PREFIXES):
        return f"'{s}"
    return s


@dataclass
class ScrapedPOIRow:
    """Formatted Point-of-Interest record ready for ingestion CSV export."""

    name: str
    description: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    visited_date: str | None = None
    tags: str | None = None
    triage_status: str = "APPROVED"


def write_ingestion_csv(rows: list[ScrapedPOIRow], output_path: Path | str) -> int:
    """Writes list of ScrapedPOIRow objects to a canonical Vistarae ingestion CSV.

    Args:
        rows: Extracted and triaged POI rows.
        output_path: Target CSV file path.

    Returns:
        Number of rows written.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "name",
        "description",
        "address",
        "city",
        "state",
        "country",
        "latitude",
        "longitude",
        "visited_date",
        "tags",
        "triage_status",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(
                [
                    sanitize_csv_field(r.name),
                    sanitize_csv_field(r.description),
                    sanitize_csv_field(r.address),
                    sanitize_csv_field(r.city),
                    sanitize_csv_field(r.state),
                    sanitize_csv_field(r.country),
                    r.latitude if r.latitude is not None else "",
                    r.longitude if r.longitude is not None else "",
                    sanitize_csv_field(r.visited_date),
                    sanitize_csv_field(r.tags),
                    sanitize_csv_field(r.triage_status),
                ]
            )
    return len(rows)


RESULT_SKIP = "skip "
RESULT_NEW = "new  "
RESULT_DUP = "dup  "
RESULT_ERR = "err  "
RESULT_NONE = "none "
RESULT_EMPTY = "empty"

@dataclass
class ScraperStats:
    """Thread-safe statistics for the scraping run."""

    files_looked_at: int = 0
    folders_new_entry: int = 0
    folders_duplicate_entry: int = 0
    folders_unknown: int = 0
    folders_total: int = 0
    folders_empty: int = 0
    folders_skipped: int = 0
    folders_unmapped: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_files(self, count: int) -> None:
        with self._lock:
            self.files_looked_at += count

    def add_new_entry(self) -> None:
        with self._lock:
            self.folders_total += 1
            self.folders_new_entry += 1

    def add_duplicate_entry(self) -> None:
        with self._lock:
            self.folders_total += 1
            self.folders_duplicate_entry += 1

    def add_skipped_entry(self) -> None:
        with self._lock:
            self.folders_total += 1
            self.folders_skipped += 1

    def add_empty_entry(self) -> None:
        with self._lock:
            self.folders_total += 1
            self.folders_empty += 1

    def add_unknown(self, folder_str: str) -> None:
        with self._lock:
            self.folders_total += 1
            self.folders_unknown += 1
            self.folders_unmapped.append(folder_str)

    def write_unmapped_log(self, filepath: str) -> None:
        """Writes unmapped folder paths to the output file."""
        with self._lock:
            try:
                out_path = Path(filepath)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.writelines(f"{line}\n" for line in self.folders_unmapped)
                logger.info(f"Wrote {len(self.folders_unmapped)} unmapped folders to {filepath}")
            except Exception as e:
                logger.error(f"Failed to write unmapped folders file: {e}")


class PhotoScraperEngine:
    """Coordinates multi-threaded photo folder discovery, EXIF extraction, and DB upsert."""

    def __init__(
        self,
        db: ScraperDatabase | None = None,
        geocoder: ScraperGeocoder | None = None,
        cache: PersistentCache | None = None,
        gemini_parser: GeminiPathParser | None = None,
        dry_run: bool = False,
        skip_over: list[str] | set[str] | None = None,
        user_email: str | None = None,
    ):
        self.cache = cache or PersistentCache(settings.CACHE_FILE_PATH)
        self.geocoder = geocoder or ScraperGeocoder(self.cache)
        self.gemini_parser = gemini_parser or GeminiPathParser()
        if dry_run or db is not None:
            self.db = db
        else:
            try:
                self.db = ScraperDatabase()
            except Exception as exc:
                logger.debug(f"ScraperDatabase not available: {exc}")
                self.db = None
        self.dry_run = dry_run
        self.user_email = user_email or settings.target_db_user
        self.stats = ScraperStats()
        self.skip_over: list[str] = list(settings.SKIP_OVER_FOLDERS if skip_over is None else skip_over)
        add_skip_over(self.skip_over)

    def add_skip_over(self, folders: str | list[str] | set[str]) -> None:
        """Adds folder names to skip over during path traversal."""
        add_skip_over(folders)
        if isinstance(folders, str):
            items = [f.strip().lower() for f in folders.split(",") if f.strip()]
        else:
            items = [str(f).strip().lower() for f in folders if str(f).strip()]
        for item in items:
            if item not in self.skip_over:
                self.skip_over.append(item)

    def discover_leaf_folders(self, root_path: Path, max_folders: int = 0, cache_info: dict = None) -> tuple[dict[str, dict[str, str]], dict]:
        """Discovers folders containing image files, applying exclusions and max limits."""
        folders_leaf: dict[str, dict[str, str]] = {}
        if cache_info is None:
            cache_info = {}

        if not root_path.exists():
            logger.error(f"Root path does not exist: {root_path}")
            return folders_leaf, cache_info

        # Recursively search for directories
        for current_dir, dirnames, filenames in root_path.walk():
            # Check exclusions
            if is_path_excluded(current_dir, settings.EXCLUSION_PATTERNS):
                logger.debug(f"Excluding directory matching patterns: {current_dir}")
                dirnames.clear()  # Do not recurse into excluded subtrees
                continue

            # Check if this directory contains supported image files
            has_images = any(Path(fn).suffix.lower() in SUPPORTED_EXTENSIONS for fn in filenames)
            if has_images:
                # If directory is an intermediate format/camera folder (e.g. 2d), skip adding it directly as leaf
                if is_skip_folder(current_dir.name, self.skip_over):
                    continue
                parsed = parse_directory_path(current_dir, root_path, skip_over=self.skip_over)

                # Consult Gemini if configured and country/city could not be fully resolved by heuristics
                if settings.USE_GEMINI and self.gemini_parser.is_configured() and (not parsed.country or not parsed.city):
                    gemini_loc = self.gemini_parser.resolve_path(current_dir, root_path)
                    if gemini_loc:
                        if gemini_loc.country and not parsed.country:
                            parsed.country = gemini_loc.country
                        if gemini_loc.state and not parsed.state:
                            parsed.state = gemini_loc.state
                        if gemini_loc.city and not parsed.city:
                            parsed.city = gemini_loc.city
                        if gemini_loc.site and (not parsed.site or parsed.site == parsed.cleaned_name):
                            parsed.site = gemini_loc.site
                            parsed.cleaned_name = gemini_loc.site
                        if not gemini_loc.is_travel_location:
                            parsed.is_likely_non_location = True

                folders_leaf[str(current_dir)] = {
                    'country': parsed.country or '',
                    'state': parsed.state or '',
                    'city': parsed.city or '',
                    'site': parsed.site or parsed.cleaned_name or '',
                }

        return folders_leaf, cache_info

    def process_folder(self, folder: Path, root_path: Path, cache_info: dict | None = None) -> None:
        found_info = {}
        result = self.process_folder_exe(folder, root_path, cache_info, found_info)
        if found_info:
            logger.info(f"New entry added for folder: {folder} - result={found_info}")
        else:
            logger.info(f"Processed folder ({result}): {folder}")

    def process_folder_exe(self, folder: Path, root_path: Path, cache_info: dict | None = None, found_info: dict | None = None) -> str:  # noqa: C901
        """Processes a single leaf folder containing photos."""
        cache_info = cache_info or {}
        # Find all images in folder (not recursive in subfolders)
        if (
            cache_info.get('country', '').lower() == 'skip'
            or cache_info.get('state', '').lower() == 'skip'
            or cache_info.get('city', '').lower() == 'skip'
            or cache_info.get('site', '').lower() == 'skip'
            or cache_info.get('skip') is True
        ):
            logger.info(f"Skipping folder per skip directive: {folder}")
            self.stats.add_skipped_entry()
            return RESULT_SKIP

        # Check database for existing scanned_paths record
        user_uuid = None
        if not self.dry_run and self.db:
            try:
                user_uuid = self.db.get_or_resolve_user_id(self.user_email)
                existing_record = self.db.get_scanned_path(user_uuid, str(folder))
                if existing_record and existing_record.get("status") != "pending":
                    logger.info(f"Skipping folder already processed with status '{existing_record.get('status')}': {folder}")
                    return RESULT_SKIP
            except Exception as e:
                logger.debug(f"Could not check existing scanned_paths record: {e}")

        image_files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not image_files:
            self.stats.add_empty_entry()
            return RESULT_EMPTY

        self.stats.add_files(len(image_files))

        # Parse directory path hierarchy with active skip-over folders
        parsed_path = parse_directory_path(folder, root_path, skip_over=self.skip_over)
        if parsed_path.is_likely_non_location:
            logger.info(f"Skipping probable non-location folder: {folder}")
            self.stats.add_unknown(str(folder))
            if not self.dry_run and self.db and user_uuid:
                try:
                    self.db.upsert_scanned_path(
                        user_id=user_uuid,
                        folder_path=str(folder),
                        folder_name=folder.name,
                        status="skipped",
                        site_name=parsed_path.cleaned_name,
                        photo_count=len(image_files),
                        confidence="high",
                        reasoning="Folder name or path matched non-travel / event pattern",
                    )
                except Exception as e:
                    logger.debug(f"Failed to record skipped scanned_path: {e}")
            return RESULT_SKIP

        # Override with any user-curated values from cache_info
        if cache_info.get('country'):
            parsed_path.country = cache_info['country']
        if cache_info.get('state'):
            parsed_path.state = cache_info['state']
        if cache_info.get('city'):
            parsed_path.city = cache_info['city']
        if cache_info.get('site'):
            parsed_path.site = cache_info['site']
            parsed_path.cleaned_name = cache_info['site']

        # Consult Gemini if country or city is still missing and Gemini is configured
        if settings.USE_GEMINI and self.gemini_parser.is_configured() and (not parsed_path.country or not parsed_path.city):
            gemini_loc = self.gemini_parser.resolve_path(folder, root_path)
            if gemini_loc:
                if not gemini_loc.is_travel_location:
                    logger.info(f"Gemini flagged folder as non-travel: {folder}")
                    self.stats.add_skipped_entry()
                    if not self.dry_run and self.db and user_uuid:
                        try:
                            self.db.upsert_scanned_path(
                                user_id=user_uuid,
                                folder_path=str(folder),
                                folder_name=folder.name,
                                status="skipped",
                                photo_count=len(image_files),
                                confidence=gemini_loc.confidence or "medium",
                                reasoning=gemini_loc.reasoning or "Gemini identified as non-travel event",
                            )
                        except Exception as e:
                            logger.debug(f"Failed to record skipped scanned_path: {e}")
                    return RESULT_SKIP

                if gemini_loc.confidence == "low":
                    logger.info(f"Gemini low confidence / ambiguous path: {folder}")
                    self.stats.add_unknown(str(folder))
                    if not self.dry_run and self.db and user_uuid:
                        try:
                            self.db.upsert_scanned_path(
                                user_id=user_uuid,
                                folder_path=str(folder),
                                folder_name=folder.name,
                                status="location unknown",
                                photo_count=len(image_files),
                                confidence="low",
                                reasoning=gemini_loc.reasoning or "Ambiguous folder path without clear geographic anchors",
                            )
                        except Exception as e:
                            logger.debug(f"Failed to record unknown scanned_path: {e}")
                    return RESULT_NONE

                if gemini_loc.country and not parsed_path.country:
                    parsed_path.country = gemini_loc.country
                if gemini_loc.state and not parsed_path.state:
                    parsed_path.state = gemini_loc.state
                if gemini_loc.city and not parsed_path.city:
                    parsed_path.city = gemini_loc.city
                if gemini_loc.site and (not parsed_path.site or parsed_path.site == parsed_path.cleaned_name):
                    parsed_path.site = gemini_loc.site
                    parsed_path.cleaned_name = gemini_loc.site

        # Extract EXIF from images
        dates: list[date] = []
        gps_coords: list[tuple[float, float]] = []

        for img_path in image_files:
            meta = extract_image_metadata(img_path)
            if meta.date_taken:
                dates.append(meta.date_taken)
            if meta.latitude is not None and meta.longitude is not None:
                gps_coords.append((meta.latitude, meta.longitude))

        # Determine location
        geocoded_loc: GeocodedLocation | None = None
        query_used: str | None = None

        # Check if already resolved and cached in gemini_path_cache.json
        if settings.USE_GEMINI and self.gemini_parser:
            cached_nom = self.gemini_parser.get_cached_nominatim_location(folder)
            if cached_nom:
                geocoded_loc = cached_nom
                logger.info(f"Loaded cached Nominatim location from gemini_path_cache: '{geocoded_loc.name}'")

        # Case 1: GPS metadata found in images
        if not geocoded_loc and gps_coords:
            # Calculate representative average coordinates
            avg_lat = sum(c[0] for c in gps_coords) / len(gps_coords)
            avg_lon = sum(c[1] for c in gps_coords) / len(gps_coords)

            query_used = f"reverse: ({avg_lat:.5f}, {avg_lon:.5f})"
            logger.info(f"Resolving folder via EXIF GPS ({avg_lat:.5f}, {avg_lon:.5f}): {folder.name}")
            geocoded_loc = self.geocoder.reverse_geocode(avg_lat, avg_lon, fallback_name=parsed_path.cleaned_name)
            if geocoded_loc and parsed_path.cleaned_name and not parsed_path.is_likely_non_location:
                # Retain folder name as place name if it looks like a valid place
                geocoded_loc.name = parsed_path.cleaned_name

        # Case 2: No GPS metadata -> resolve from directory path hierarchy
        if not geocoded_loc:
            # 2a. Try hierarchical search query with ancestor context
            if parsed_path.combined_query:
                query_used = parsed_path.combined_query
                geocoded_loc = self.geocoder.forward_geocode(parsed_path.combined_query)

            # 2b. Try stripped landmark stem + city (e.g. "Behai Temple" -> "Behai, Beijing, China")
            if not geocoded_loc and parsed_path.city:
                stem = re.sub(
                    r"\s+(temple|park|palace|castle|museum|monument|church|tower|gardens?|cathedral|pagoda|abbey|square)$",
                    "",
                    parsed_path.cleaned_name,
                    flags=re.IGNORECASE,
                ).strip()
                if stem and stem.lower() != parsed_path.cleaned_name.lower():
                    stem_query = f"{stem}, {parsed_path.city}, {parsed_path.country}" if parsed_path.country else f"{stem}, {parsed_path.city}"
                    logger.info(f"Retrying with landmark stem query: '{stem_query}'")
                    query_used = stem_query
                    geocoded_loc = self.geocoder.forward_geocode(stem_query)
                    if not geocoded_loc:
                        query_used = f"{stem}, {parsed_path.city}"
                        geocoded_loc = self.geocoder.forward_geocode(query_used)
                    if geocoded_loc:
                        geocoded_loc.name = parsed_path.cleaned_name

            # 2c. If hierarchical search failed and no state/country, try Batavia fallback bias
            if not geocoded_loc:
                has_state_or_country = bool(parsed_path.detected_state or parsed_path.country or len(parsed_path.ancestor_context) > 0)
                if not has_state_or_country:
                    fallback_query = f"{parsed_path.cleaned_name}, {settings.FALLBACK_LOCATION}"
                    logger.info(f"Applying Batavia fallback bias for query: '{fallback_query}'")
                    query_used = fallback_query
                    geocoded_loc = self.geocoder.forward_geocode(fallback_query, bias_near_batavia=True)

            # 2d. Fallback to cleaned place name alone
            if not geocoded_loc:
                query_used = parsed_path.cleaned_name
                geocoded_loc = self.geocoder.forward_geocode(parsed_path.cleaned_name)

            # 2e. Try Gemini to correct or enrich query if available
            if not geocoded_loc and settings.USE_GEMINI and self.gemini_parser.is_configured():
                gemini_loc = self.gemini_parser.resolve_path(folder, root_path)
                if gemini_loc and gemini_loc.site:
                    gemini_query = f"{gemini_loc.site}, {gemini_loc.city or parsed_path.city or ''}, {gemini_loc.country or parsed_path.country or ''}".strip(", ")
                    logger.info(f"Retrying geocoding with Gemini resolved query: '{gemini_query}'")
                    query_used = gemini_query
                    geocoded_loc = self.geocoder.forward_geocode(gemini_query)

            # 2f. Fallback to city-level anchor (preserves place name, anchors to city coordinates)
            if not geocoded_loc and parsed_path.city:
                city_query = f"{parsed_path.city}, {parsed_path.country}" if parsed_path.country else parsed_path.city
                logger.info(f"Falling back to city anchor query: '{city_query}' for '{parsed_path.cleaned_name}'")
                query_used = city_query
                city_loc = self.geocoder.forward_geocode(city_query)
                if city_loc:
                    city_loc.name = parsed_path.cleaned_name
                    city_loc.city = parsed_path.city
                    if parsed_path.country:
                        city_loc.country = parsed_path.country
                    geocoded_loc = city_loc

        # Record Nominatim result in gemini_path_cache.json
        if settings.USE_GEMINI and self.gemini_parser:
            self.gemini_parser.update_nominatim_result(
                folder_path=folder,
                geo=geocoded_loc,
                query=query_used or parsed_path.combined_query or parsed_path.cleaned_name,
                parsed_path=parsed_path,
            )

        # Evaluation & Database Upsert
        place_label = parsed_path.cleaned_name or folder.name
        sorted_dates = sorted(dates) if dates else []
        earliest_dt = sorted_dates[0] if sorted_dates else None
        latest_dt = sorted_dates[-1] if sorted_dates else None

        if geocoded_loc and (geocoded_loc.latitude != 0.0 or geocoded_loc.longitude != 0.0):
            if self.dry_run:
                logger.info(f"[DRY RUN] Identified: '{geocoded_loc.name}' at ({geocoded_loc.latitude}, {geocoded_loc.longitude}) for folder {folder}")
                self.stats.add_new_entry()
                return RESULT_NEW

            else:
                try:
                    is_dup, _poi_id, _place_name = self.db.upsert_poi_visit(
                        geo=geocoded_loc,
                        visit_dates=dates,
                        folder=folder,
                        user_id=user_uuid,
                        fallback_name=place_label,
                    )

                    if user_uuid:
                        try:
                            self.db.upsert_scanned_path(
                                user_id=user_uuid,
                                folder_path=str(folder),
                                folder_name=folder.name,
                                status="identified",
                                poi_id=_poi_id,
                                site_name=geocoded_loc.name,
                                city=geocoded_loc.city,
                                state=geocoded_loc.state,
                                country=geocoded_loc.country,
                                country_code=geocoded_loc.country_code,
                                latitude=geocoded_loc.latitude,
                                longitude=geocoded_loc.longitude,
                                confidence="high",
                                reasoning="Identified and geocoded via Nominatim",
                                photo_count=len(image_files),
                                earliest_date=earliest_dt,
                                latest_date=latest_dt,
                            )
                        except Exception as sp_err:
                            logger.debug(f"Failed to record identified scanned_path: {sp_err}")

                    found_info['country'] = geocoded_loc.country
                    found_info['state'] = geocoded_loc.state
                    found_info['city'] = geocoded_loc.city
                    found_info['site'] = geocoded_loc.display_name

                    if is_dup:
                        self.stats.add_duplicate_entry()
                        return RESULT_DUP
                    else:
                        self.stats.add_new_entry()
                        return RESULT_NEW

                except Exception as e:
                    logger.error(f"Database upsert failed for {folder}: {e}")
                    self.stats.add_unknown(str(folder))
                    return RESULT_ERR

        else:
            logger.info(f"Location unknown for folder: {folder}. Recording as 'location unknown' for manual review.")
            self.stats.add_unknown(str(folder))
            if not self.dry_run and self.db and user_uuid:
                try:
                    self.db.upsert_scanned_path(
                        user_id=user_uuid,
                        folder_path=str(folder),
                        folder_name=folder.name,
                        status="location unknown",
                        site_name=place_label,
                        city=parsed_path.city,
                        state=parsed_path.state,
                        country=parsed_path.country,
                        confidence="low",
                        reasoning="Location coordinates could not be determined",
                        photo_count=len(image_files),
                        earliest_date=earliest_dt,
                        latest_date=latest_dt,
                    )
                except Exception as e:
                    logger.debug(f"Failed to record unknown scanned_path: {e}")
            return RESULT_NONE


    def load_cached_leaf_folders(self, cache_file: Path, max_folders: int = 0) -> list[Path]:
        """Loads cached leaf folder paths from disk, skipping filesystem traversal."""
        cache_info = {}
        leaf_folders: list[Path] = []
        try:
            with open(cache_file, encoding="utf-8") as f:
                cache_info = json.load(f)

            for folder_str in cache_info:
                folder_path = Path(folder_str)
                if folder_path.exists() and folder_path.is_dir():
                    leaf_folders.append(folder_path)
                else:
                    logger.warning(f"Cached folder does not exist or is not a directory: {folder_path}")

            logger.info(f"Loaded {len(cache_info.keys())} leaf folders from cache file: {cache_file}")
        except Exception as e:
            logger.warning(f"Could not load leaf folders cache ({e}). Will perform new discovery scan.")

        return leaf_folders, cache_info

    def save_leaf_folders_cache(self, folders_leaf: dict | list | tuple, cache_file: Path) -> None:
        """Saves discovered leaf folders to disk cache in the output directory."""
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(folders_leaf, tuple):
                data = folders_leaf[0]
            elif isinstance(folders_leaf, dict):
                data = folders_leaf
            elif isinstance(folders_leaf, list):
                data = {
                    str(p): parse_directory_path(Path(p), skip_over=self.skip_over).to_dict()
                    for p in folders_leaf
                }
            else:
                data = dict(folders_leaf)

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False, default=str)
            logger.info(f"Saved {len(data)} leaf folders to cache file: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to write leaf folders cache file: {e}")

    def run(
        self,
        photo_dir: str | None = None,
        num_workers: int | None = None,
        max_folders: int | None = None,
        cache_folders: bool | None = None,
        rescan_folders: bool = False,
    ) -> ScraperStats:
        """Executes multi-worker scraping on the target directory."""
        dir_to_scan = Path(photo_dir or settings.PHOTO_DIR)
        workers_count = num_workers or settings.NUM_WORKERS
        folder_limit = max_folders if max_folders is not None else settings.MAX_FOLDERS
        use_folder_cache = cache_folders if cache_folders is not None else settings.CACHE_LEAF_FOLDERS
        cache_file = Path(settings.LEAF_FOLDERS_CACHE_PATH)

        logger.info(f"Starting photo scraper on: {dir_to_scan}")
        logger.info(
            f"Workers: {workers_count} | Max Folders: {folder_limit} | "
            f"Fallback: {settings.FALLBACK_LOCATION} | Cache Folders: {use_folder_cache} | "
            f"Target DB User: {self.user_email}"
        )

        # Validate target user in database before starting
        if not self.dry_run and self.db:
            validated_id, validated_email = self.db.validate_user(self.user_email)
            logger.info(f"Verified valid database user: '{validated_email}' (UUID: {validated_id})")

        folders_leaf: list[Path] = []
        cache_info: dict[str, dict[str, str]] = {}

        # If caching is enabled and cached file exists, use cached values to save search time
        if use_folder_cache and not rescan_folders and cache_file.exists():
            folders_leaf, cache_info = self.load_cached_leaf_folders(cache_file, max_folders=folder_limit)

        # If cache is not enabled or cached file was empty/absent, perform new discovery
        if not folders_leaf:
            folders_dict, cache_info = self.discover_leaf_folders(
                dir_to_scan, max_folders=folder_limit, cache_info=cache_info
            )
            folders_leaf = [Path(p) for p in folders_dict]
            logger.info(f"Discovered {len(folders_leaf)} candidate leaf folders to process.")
            if use_folder_cache and folders_dict:
                self.save_leaf_folders_cache(folders_dict, cache_file)
        else:
            logger.info(f"Reusing {len(folders_leaf)} cached leaf folders (bypassed directory traversal).")

        if not folders_leaf:
            logger.info("No photo folders found to process.")
            return self.stats

        if max_folders > 0:
            found_folder_count = len(folders_leaf)
            if found_folder_count >= max_folders:
                folders_leaf = folders_leaf[:max_folders]
                logger.info(f"Capping folders from {found_folder_count} to {max_folders}")

        try:
            with ThreadPoolExecutor(max_workers=workers_count) as executor:
                futures = {
                    executor.submit(self.process_folder, folder, dir_to_scan, cache_info.get(str(folder), {})): folder
                    for folder in folders_leaf
                }
                for future in as_completed(futures):
                    folder = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        logger.error(f"Error processing folder {folder}: {exc}")
                        self.stats.add_unknown(str(folder))
        finally:
            # Guarantee in-memory caches and unmapped logs are saved on stop, error, or completion
            flush_all_caches()
            self.stats.write_unmapped_log(settings.UNMAPPED_LOG_PATH)

        return self.stats

    def scan_and_export(  # noqa: C901
        self,
        photo_dir: Path | str,
        output_csv: Path | str,
        non_interactive: bool = False,
        max_folders: int = 0,
        exclude_patterns: list[str] | None = None,
    ) -> list[ScrapedPOIRow]:
        """Scans directories, performs AI POI inference, interactively triages, and writes CSV.

        Args:
            photo_dir: Directory containing photo libraries.
            output_csv: Destination CSV path.
            non_interactive: If True or non-TTY, marks uncertain POIs as NEEDS_REVIEW without prompting.
            max_folders: Optional limit on folders to scan (0 = unlimited).
            exclude_patterns: Glob patterns to exclude.

        Returns:
            List of generated ScrapedPOIRow items.
        """
        root_path = Path(photo_dir)
        patterns = list(settings.EXCLUSION_PATTERNS)
        if exclude_patterns:
            patterns.extend(exclude_patterns)

        scraped_rows: list[ScrapedPOIRow] = []
        folders_processed = 0

        # Traverse directory hierarchy
        for current_dir, dirnames, filenames in root_path.walk():
            if is_path_excluded(current_dir, patterns):
                dirnames.clear()
                continue

            # Check for image files in current_dir
            image_files = [
                current_dir / fn
                for fn in sorted(filenames)
                if Path(fn).suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            if not image_files:
                continue

            if is_skip_folder(current_dir.name, self.skip_over):
                continue

            # Extract EXIF metadata from available images
            exif_lat: float | None = None
            exif_lon: float | None = None
            visited_date: str | None = None
            first_img_name = image_files[0].name

            for img_path in image_files:
                meta = extract_image_metadata(img_path)
                if exif_lat is None and meta.latitude is not None:
                    exif_lat = meta.latitude
                    exif_lon = meta.longitude
                if visited_date is None and meta.date_taken is not None:
                    visited_date = meta.date_taken.isoformat()
                if exif_lat is not None and visited_date is not None:
                    break

            # Infer POI using Gemini parser or fallback heuristics
            inference: PhotoPOIInference | None = None
            if self.gemini_parser and self.gemini_parser.is_configured():
                inference = self.gemini_parser.infer_poi(
                    folder_path=current_dir,
                    file_name=first_img_name,
                    exif_lat=exif_lat,
                    exif_lon=exif_lon,
                    date_taken=visited_date,
                )

            if inference is None:
                parsed = parse_directory_path(current_dir, root_path, skip_over=self.skip_over)
                site_name = parsed.site or parsed.cleaned_name or current_dir.name
                inference = PhotoPOIInference(
                    name=site_name,
                    description=f"Extracted from {current_dir.name}",
                    city=parsed.city,
                    state=parsed.state,
                    country=parsed.country,
                    confidence_score=0.5,
                    is_uncertain=True,
                )

            # Determine uncertainty
            is_uncertain = (
                inference.is_uncertain
                or inference.confidence_score < 0.70
                or inference.name.strip().lower() in GENERIC_CATEGORIES
            )

            triage_status = "APPROVED"
            is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()

            if is_uncertain:
                if non_interactive or not is_tty:
                    triage_status = "NEEDS_REVIEW"
                else:
                    # Interactive prompt per schema
                    print("\n[UNCERTAIN POI DETECTED]")
                    print(f"Folder: {current_dir}")
                    print(f"File:   {first_img_name}")
                    print(
                        f"EXIF:   Lat: {exif_lat}, Lon: {exif_lon} (Taken: {visited_date or 'N/A'})"
                    )
                    print(
                        f"Inferred: {inference.name} (Confidence: {inference.confidence_score:.2f})"
                    )
                    print("Reason: Generic or low confidence establishment detected.\n")
                    print("Options:")
                    print("  [c] Confirm and keep as inferred")
                    print("  [e] Edit POI name and details")
                    print("  [s] Skip this POI")
                    choice = input("Enter choice [c/e/s]: ").strip().lower()
                    if choice == "s":
                        continue
                    elif choice == "e":
                        new_name = input(f"Enter POI name [{inference.name}]: ").strip()
                        new_desc = input(f"Enter description [{inference.description}]: ").strip()
                        inference = PhotoPOIInference(
                            name=new_name or inference.name,
                            description=new_desc or inference.description,
                            city=inference.city,
                            state=inference.state,
                            country=inference.country,
                            confidence_score=1.0,
                            is_uncertain=False,
                        )
                        triage_status = "APPROVED"
                    else:
                        triage_status = "APPROVED"

            scraped_rows.append(
                ScrapedPOIRow(
                    name=inference.name,
                    description=inference.description,
                    address=None,
                    city=inference.city,
                    state=inference.state,
                    country=inference.country,
                    latitude=exif_lat,
                    longitude=exif_lon,
                    visited_date=visited_date,
                    tags="photo_scraper,exif",
                    triage_status=triage_status,
                )
            )

            folders_processed += 1
            if max_folders > 0 and folders_processed >= max_folders:
                break

        # Write to destination CSV
        write_ingestion_csv(scraped_rows, output_csv)
        return scraped_rows
