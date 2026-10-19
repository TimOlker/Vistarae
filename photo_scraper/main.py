"""Vistarae Photo Scraper Entry Point.

This is the primary starting point for executing photo scraping across photo directories.
Usage:
    python photo_scraper/main.py --dir <path_to_photos>
    python -m photo_scraper.main --dir <path_to_photos>
    .\vistarae.ps1 scrape [path_to_photos]
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path when running photo_scraper/main.py directly
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


def print_report(stats, unmapped_file: str) -> None:
    """Prints the final summary metrics report."""
    print("\n" + "=" * 60)
    print("           VISTARAE PHOTO SCRAPING SUMMARY")
    print("=" * 60)
    print(f"Number of files looked at                     : {stats.files_looked_at}")
    print(f"Number of folders total                       : {stats.folders_total}")
    print(f"Number of folders skipped                     : {stats.folders_skipped}")
    print(f"Number of folders empty                       : {stats.folders_empty}")
    print(f"Number of folders location identified - new   : {stats.folders_new_entry}")
    print(f"Number of folders location identified - dup   : {stats.folders_duplicate_entry}")
    print(f"Number of folders location unknown            : {stats.folders_unknown}")
    print("-" * 60)
    total_identified = stats.folders_new_entry + stats.folders_duplicate_entry
    total_folders = total_identified + stats.folders_unknown
    if total_folders > 0:
        success_rate = (total_identified / total_folders) * 100.0
        print(f"Success Rate                                  : {success_rate:.1f}%")
    if stats.folders_unknown > 0:
        print(f"Unmapped folders logged to                    : {unmapped_file}")
    print("=" * 60 + "\n")


def main() -> None:
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
        "--workers",
        "-w",
        type=int,
        default=settings.NUM_WORKERS,
        help=f"Number of parallel workers (default: {settings.NUM_WORKERS})",
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
        "--skip-over",
        "--skip-folders",
        type=str,
        default="",
        help="Comma-separated folder names to skip over during path hierarchy parsing (e.g. '2d,3d,raw')",
    )
    parser.add_argument(
        "--fallback",
        type=str,
        default=settings.FALLBACK_LOCATION,
        help=f"Fallback search location bias (default: {settings.FALLBACK_LOCATION})",
    )
    parser.add_argument(
        "--db-user",
        "--user-email",
        type=str,
        dest="db_user",
        default=settings.target_db_user,
        help=f"Target database user email for photo scraping (default: {settings.target_db_user})",
    )
    parser.add_argument(
        "--cache-folders",
        action="store_true",
        default=settings.CACHE_LEAF_FOLDERS,
        help="Cache discovered leaf folders to disk and reuse on subsequent runs to bypass filesystem traversal",
    )
    parser.add_argument(
        "--rescan-folders",
        action="store_true",
        default=False,
        help="Force a fresh filesystem scan even if a cached leaf folders file exists",
    )
    parser.add_argument(
        "--gemini",
        dest="use_gemini",
        action="store_true",
        default=settings.USE_GEMINI,
        help="Enable Gemini LLM path parsing when GEMINI_API_KEY is configured (default: true)",
    )
    parser.add_argument(
        "--no-gemini",
        dest="use_gemini",
        action="store_false",
        help="Disable Gemini LLM path parsing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without writing to the database",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)

    target_dir = args.dir
    if not target_dir:
        print("Error: No photo directory specified. Use --dir <path> or set PHOTO_DIR in .env")
        sys.exit(1)

    scan_path = Path(target_dir)
    if not scan_path.exists():
        print(f"Error: Directory does not exist: {scan_path}")
        sys.exit(1)

    if args.exclude:
        extra_excludes = [p.strip() for p in args.exclude.split(",") if p.strip()]
        settings.EXCLUSION_PATTERNS.extend(extra_excludes)

    if args.fallback:
        settings.FALLBACK_LOCATION = args.fallback
    if args.db_user:
        settings.PHOTOSCRAPER_DB_USER = args.db_user
    if hasattr(args, "use_gemini"):
        settings.USE_GEMINI = args.use_gemini

    skip_folders = list(settings.SKIP_OVER_FOLDERS)
    if args.skip_over:
        extra_skips = [s.strip().lower() for s in args.skip_over.split(",") if s.strip()]
        for item in extra_skips:
            if item not in skip_folders:
                skip_folders.append(item)

    try:
        engine = PhotoScraperEngine(
            dry_run=args.dry_run,
            skip_over=skip_folders,
            user_email=settings.target_db_user,
        )

        # Validate user before starting
        if not args.dry_run and engine.db:
            try:
                validated_id, validated_email = engine.db.validate_user(settings.target_db_user)
                logger.info(f"Target DB User verified: '{validated_email}' (UUID: {validated_id})")
            except ValueError as err:
                logger.error(f"Cannot start scraper: {err}")
                sys.exit(1)

        stats = engine.run(
            photo_dir=str(scan_path),
            num_workers=args.workers,
            max_folders=args.max_folders,
            cache_folders=args.cache_folders,
            rescan_folders=args.rescan_folders,
        )
        print_report(stats, settings.UNMAPPED_LOG_PATH)
    except KeyboardInterrupt:
        print("\n[WARNING] Process stopped by user (Ctrl+C / SIGINT). In-memory caches saved to disk.")
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
