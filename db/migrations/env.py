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

"""Pure async Alembic migration runner.

Configures Alembic to execute migrations through the SQLAlchemy 2.0
asyncpg engine. Reads DATABASE_URL from the environment and normalizes
the URL scheme to postgresql+asyncpg:// before constructing the engine.

Constitution Principle 4: All schema migrations reside strictly inside
db/migrations/. Alembic check is enforced in CI.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from logging.config import fileConfig
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT / "packages" / "core") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "packages" / "core"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from alembic import context  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

# Alembic Config object providing access to alembic.ini values.
config = context.config

# Set up Python logging from alembic.ini [loggers] section if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the project Base so Alembic autogenerate can detect schema drift.
from vistarae_core.adapters.db.tables import (  # noqa: E402
    Base,
)

target_metadata = Base.metadata


def _normalize_url(raw_url: str) -> str:
    """Converts legacy postgres:// or plain postgresql:// to postgresql+asyncpg://.

    Args:
        raw_url: Raw database URL string, possibly with legacy scheme.

    Returns:
        Normalized URL string.
    """
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", raw_url)
    url = url.replace("sslmode=require", "ssl=require")
    # Alembic may have %-escaped percent signs; replace double-% with single.
    url = url.replace("%%", "%")
    return url


def _get_url() -> str:
    """Resolves the database connection URL from environment or alembic.ini.

    Returns:
        Normalized postgresql+asyncpg:// URL string.
    """
    raw = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    return _normalize_url(raw)


POSTGIS_EXTENSION_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
    "topology",
    "layer",
    "addr",
    "addrfeat",
    "bg",
    "county",
    "county_lookup",
    "countysub_lookup",
    "cousub",
    "direction_lookup",
    "edges",
    "faces",
    "featnames",
    "geocode_settings",
    "geocode_settings_default",
    "loader_lookuptables",
    "loader_platform",
    "loader_variables",
    "pagc_gaz",
    "pagc_lex",
    "pagc_rules",
    "place",
    "place_lookup",
    "secondary_unit_lookup",
    "state",
    "state_lookup",
    "street_type_lookup",
    "tabblock",
    "tabblock20",
    "tract",
    "zcta5",
    "zip_lookup",
    "zip_lookup_all",
    "zip_lookup_base",
    "zip_state",
    "zip_state_loc",
}

UNMAPPED_STANDALONE_TABLES = {
    "scanned_paths",
    "poi_access_points",
    "poi_list_memberships",
    "user_tags",
    "geocache",
}

UNMAPPED_LEGACY_COLUMNS = {
    "lists": {"is_trip"},
    "users": {"hashed_password"},
    "pois": {
        "visited",
        "cost_tier",
        "source_url",
        "name_aliases",
        "raw_selected_text",
        "phone_number",
        "iptc_province_state",
        "geofence_radius_ft",
        "category_tags",
        "visit_date",
        "visit_again",
        "hours_seasonality",
        "physical_effort",
        "primary_image_url",
        "indoor_outdoor",
        "google_place_id",
        "location",
        "iptc_world_region",
        "visit_dates",
        "personal_rating",
        "poi_type",
        "estimated_duration",
        "booking_lead_time",
        "iptc_city",
        "website_official",
        "iptc_zip_code",
        "alternate_image_urls",
        "iptc_country_code",
        "best_time_to_visit",
        "iptc_sublocation",
    },
}

UNMAPPED_LEGACY_INDEXES = {
    "idx_pois_location",
    "idx_pois_parent_id",
    "idx_pois_user_id",
}


def include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Filters out PostGIS extension tables and prototype objects from migration diffs."""
    if type_ == "table":
        if name in POSTGIS_EXTENSION_TABLES or name in UNMAPPED_STANDALONE_TABLES:
            return False
        if name and (
            name.startswith("tiger")
            or name.startswith("topology")
            or name.startswith("pagc")
            or name.endswith("_lookup")
            or "lookup" in name
        ):
            return False
    elif type_ == "column" and reflected and compare_to is None:
        table_name = getattr(getattr(object_, "table", None), "name", None)
        if table_name in UNMAPPED_LEGACY_COLUMNS and name in UNMAPPED_LEGACY_COLUMNS[table_name]:
            return False
    elif type_ == "index":
        table_name = getattr(getattr(object_, "table", None), "name", None)
        if (
            table_name in POSTGIS_EXTENSION_TABLES
            or table_name in UNMAPPED_STANDALONE_TABLES
            or (
                table_name
                and (
                    table_name.startswith("tiger")
                    or table_name.startswith("topology")
                    or table_name.startswith("pagc")
                    or table_name.endswith("_lookup")
                    or "lookup" in table_name
                )
            )
        ):
            return False
        if reflected and compare_to is None and name in UNMAPPED_LEGACY_INDEXES:
            return False
    return True


def run_migrations_offline() -> None:
    """Generates SQL migration scripts without a live database connection.

    Used by ``alembic upgrade --sql`` for generating DDL scripts.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Executes migrations within an active database connection context.

    Args:
        connection: Active SQLAlchemy async connection.
    """
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Creates an async engine and runs migrations using asyncpg driver."""
    url = _get_url()
    connectable = create_async_engine(
        url,
        connect_args={"statement_cache_size": 0},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration execution."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
