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

"""Vistarae AI Photo Scraper CLI (T-044).

Extracts EXIF metadata from photo libraries, queries Google Gemini Flash-Lite
for structured POI inference, supports interactive/non-interactive triage,
and exports formula-neutralized CSVs for Vistarae ingestion.

Usage:
    python -m photo_scraper.main --dir <path_to_photos> [OPTIONS]
    .\vistarae.ps1 scrape <path_to_photos> [OPTIONS]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from photo_scraper.core.cache import flush_all_caches  # noqa: E402
from photo_scraper.core.config import settings  # noqa: E402
from photo_scraper.core.worker import PhotoScraperEngine  # noqa: E402

logger = logging.getLogger("vistarae.photo_scraper.main")


def configure_logging(verbose: bool = False) -> None:
    """Sets up console logging format."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses command-line arguments for photo scraper CLI."""
    parser = argparse.ArgumentParser(
        description="Vistarae Photo Scraper: Extract visited POIs from photo libraries.",
    )
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=settings.PHOTO_DIR,
        help="Path to photo library root directory to scan",
    )
    parser.add_argument(
        "--out",
        "-o",
        type=str,
        default="output/ingest.csv",
        help="Output CSV path for formatted ingestion records (default: output/ingest.csv)",
    )
    parser.add_argument(
        "--max-folders",
        "-m",
        type=int,
        default=settings.MAX_FOLDERS,
        help="Maximum folders to process (default: 0 = unlimited)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default="",
        help="Comma-separated patterns to exclude (e.g. '*Kids*,*iPhone*')",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Run unattended; mark uncertain POIs as NEEDS_REVIEW without prompting",
    )
    parser.add_argument(
        "--skip-over",
        "--skip-folders",
        type=str,
        default="",
        help="Comma-separated folder names to skip over during path hierarchy parsing",
    )
    parser.add_argument(
        "--fallback",
        type=str,
        default=settings.FALLBACK_LOCATION,
        help=f"Fallback search location bias (default: {settings.FALLBACK_LOCATION})",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=settings.NUM_WORKERS,
        help=f"Number of parallel workers (default: {settings.NUM_WORKERS})",
    )
    parser.add_argument(
        "--db-user",
        type=str,
        default=settings.target_db_user,
        help=f"Target database user email (default: {settings.target_db_user})",
    )
    parser.add_argument(
        "--to-db",
        action="store_true",
        default=False,
        help="Upsert scraped records directly into database instead of CSV only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without writing output files or database records",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for photo_scraper."""
    args = parse_args(argv)
    configure_logging(args.verbose)

    target_dir = args.dir
    if not target_dir:
        print("Error: No photo directory specified. Use --dir <path> or set PHOTO_DIR in .env")
        sys.exit(1)

    scan_path = Path(target_dir)
    if not scan_path.exists():
        print(f"Error: Directory does not exist: {scan_path}")
        sys.exit(1)

    extra_excludes = []
    if args.exclude:
        extra_excludes = [p.strip() for p in args.exclude.split(",") if p.strip()]

    skip_folders = list(settings.SKIP_OVER_FOLDERS)
    if args.skip_over:
        extra_skips = [s.strip().lower() for s in args.skip_over.split(",") if s.strip()]
        for item in extra_skips:
            if item not in skip_folders:
                skip_folders.append(item)

    try:
        engine = PhotoScraperEngine(
            dry_run=args.dry_run or not args.to_db,
            skip_over=skip_folders,
            user_email=args.db_user or settings.target_db_user,
        )

        if args.to_db:
            # Legacy direct DB upsert mode
            stats = engine.run(
                photo_dir=str(scan_path),
                num_workers=args.workers,
                max_folders=args.max_folders,
            )
            print(f"Scraping to database complete. Files examined: {stats.files_looked_at}")
        else:
            # Canonical Phase 3 Ingestion CSV export
            out_path = Path(args.out)
            rows = engine.scan_and_export(
                photo_dir=scan_path,
                output_csv=out_path,
                non_interactive=args.non_interactive,
                max_folders=args.max_folders,
                exclude_patterns=extra_excludes,
            )
            print(f"Exported {len(rows)} POI records to {out_path}")

    except KeyboardInterrupt:
        print(
            "\n[WARNING] Process stopped by user (Ctrl+C / SIGINT). In-memory caches saved to disk."
        )
        flush_all_caches()
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Application encountered an error: {exc}. In-memory caches saved to disk.")
        flush_all_caches()
        raise
    finally:
        flush_all_caches()


if __name__ == "__main__":
    main()
