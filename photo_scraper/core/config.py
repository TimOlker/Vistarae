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

"""Configuration for Vistarae Photo Scraper."""


from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project and module directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_ROOT = Path(__file__).resolve().parent.parent

# Env file search paths in priority order (later overrides earlier)
ENV_FILES = (
    str(PROJECT_ROOT / ".env"),
    str(PROJECT_ROOT / ".env.local"),
    str(MODULE_ROOT / ".env"),
    str(MODULE_ROOT / ".env.local"),
    ".env",
    ".env.local",
)

# Load into system environment for any direct os.getenv calls
for ef in ENV_FILES:
    if Path(ef).exists():
        load_dotenv(ef)


class ScraperSettings(BaseSettings):
    """Settings for photo library scraping and POI cataloging."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Photo library directory to scan
    PHOTO_DIR: str = Field(default="", description="Root directory of photo library to scan")

    # Worker concurrency
    NUM_WORKERS: int = Field(default=4, description="Number of parallel worker threads")

    # Folder limits (0 = unlimited)
    MAX_FOLDERS: int = Field(default=0, description="Max leaf folders to process (0 = unlimited)")

    # Folder exclusion patterns (comma-separated or list)
    EXCLUSION_PATTERNS: list[str] = Field(
        default=["*Kids*", "*iPhone*", "*Personal*", "*Screenshot*", "*Screenshots*", "*Choir*"],
        description="Glob patterns to exclude from scanning",
    )

    # Fallback geographic bias when city/state is absent
    FALLBACK_LOCATION: str = Field(
        default="Batavia, IL",
        description="Default geographic search bias when city/state is not present",
    )

    # Technical or camera folders to skip over during path hierarchy parsing
    SKIP_OVER_FOLDERS: list[str] = Field(
        default=["2d", "3d", "raw", "dcim", "edited", "export", "exports", "selected", "favorites", "jpg", "jpeg", "hdr"],
        description="Folder names to skip over during hierarchical path parsing",
    )

    # Persistent disk cache (located inside photo_scraper/output directory)
    CACHE_FILE_PATH: str = Field(
        default=str(Path(__file__).resolve().parent.parent / "output" / "photo_scraper_cache.json"),
        description="Path to JSON cache file for external geocoding queries",
    )

    # Output file for unmapped locations (located inside photo_scraper/output directory)
    UNMAPPED_LOG_PATH: str = Field(
        default=str(Path(__file__).resolve().parent.parent / "output" / "folders_unmapped.txt"),
        description="Path to output text file logging unmapped folder paths",
    )

    # Cache leaf folders discovery list to bypass directory traversal
    CACHE_LEAF_FOLDERS: bool = Field(
        default=False,
        description="If true, save and reuse discovered leaf folders list from disk",
    )
    LEAF_FOLDERS_CACHE_PATH: str = Field(
        default=str(Path(__file__).resolve().parent.parent / "output" / "folders_leaf.txt"),
        description="Path to text file caching discovered leaf folders to bypass filesystem scans",
    )

    # Database connection
    DATABASE_URL_SYNC: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/vistarae",
        description="Synchronous database connection URL for workers",
    )
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/vistarae",
        description="Async database connection URL",
    )

    # Database user for photo scraping
    PHOTOSCRAPER_DB_USER: str = Field(
        default="",
        description="Target user email in database to assign created POIs to",
    )
    USER_EMAIL: str = Field(
        default="tim@olker.us",
        description="Fallback user email if PHOTOSCRAPER_DB_USER is not set",
    )

    @property
    def target_db_user(self) -> str:
        """Returns PHOTOSCRAPER_DB_USER if configured, otherwise falls back to USER_EMAIL."""
        return self.PHOTOSCRAPER_DB_USER.strip() if self.PHOTOSCRAPER_DB_USER.strip() else self.USER_EMAIL.strip()

    # OpenStreetMap Nominatim settings
    NOMINATIM_BASE_URL: str = Field(
        default="https://nominatim.openstreetmap.org",
        description="Base URL for Nominatim API",
    )
    NOMINATIM_USER_AGENT: str = Field(
        default="VistaraeTravelEngine/1.0",
        description="User-Agent header required by Nominatim Acceptable Use Policy",
    )
    NOMINATIM_RATE_LIMIT_SEC: float = Field(
        default=1.0,
        description="Minimum seconds between outbound Nominatim requests",
    )

    # Optional Gemini API configuration
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for smart path fallback parsing",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash-lite",
        description="Google Gemini model identifier for entity extraction",
    )
    GEMINI_PATH_CACHE_PATH: str = Field(
        default=str(MODULE_ROOT / "output" / "gemini_path_cache.json"),
        description="Path to JSON cache file for Gemini path parsing results",
    )
    USE_GEMINI: bool = Field(
        default=True,
        description="Enable Gemini LLM path parsing when GEMINI_API_KEY is configured",
    )


settings = ScraperSettings()
