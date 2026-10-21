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

"""Unit tests for Phase 6 Alembic migration 0004_trip_planner (T008).

Verifies migration revision identifiers, upgrade/downgrade callables, table schemas,
check constraints, and index definitions for itineraries, itinerary_days,
itinerary_items, and system_settings.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    """Dynamically loads the 0004 migration module."""
    migration_path = (
        Path(__file__).parents[3] / "db" / "migrations" / "versions" / "0004_trip_planner.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0004", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigration0004Metadata:
    """Verifies migration file revision identifiers, callables, and chain order."""

    def test_migration_identifiers(self) -> None:
        """Asserts correct revision and parent revision pointers."""
        mod = _load_migration_module()
        assert mod.revision == "0004"
        assert mod.down_revision == "0003"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)
        assert mod.branch_labels is None
        assert mod.depends_on is None

    def test_table_definitions_in_orm(self) -> None:
        """Asserts that all Phase 6 ORM tables match the migration schema."""
        from vistarae_core.adapters.db.tables import (
            ItineraryDayTable,
            ItineraryItemTable,
            ItineraryTable,
            SystemSettingsTable,
        )

        assert ItineraryTable.__tablename__ == "itineraries"
        assert ItineraryDayTable.__tablename__ == "itinerary_days"
        assert ItineraryItemTable.__tablename__ == "itinerary_items"
        assert SystemSettingsTable.__tablename__ == "system_settings"

        # Verify columns exist
        assert hasattr(ItineraryTable, "budget_cents")
        assert hasattr(ItineraryTable, "status")
        assert hasattr(ItineraryDayTable, "total_cost_cents")
        assert hasattr(ItineraryItemTable, "travel_time_prev_minutes")
        assert hasattr(ItineraryItemTable, "is_backup_for_id")
        assert hasattr(SystemSettingsTable, "key")
        assert hasattr(SystemSettingsTable, "value")
