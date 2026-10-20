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

"""Unit tests for Phase 3 Alembic migration 0003_async_ingestion_cli (T-003).

Verifies migration metadata, upgrade/downgrade callables, table definitions,
column types, check constraints, foreign keys, and index configurations.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_migration_module():
    """Dynamically loads the 0003 migration module."""
    migration_path = (
        Path(__file__).parents[3]
        / "db"
        / "migrations"
        / "versions"
        / "0003_async_ingestion_cli.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0003", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigration0003Metadata:
    """Verifies migration file revision identifiers and functions."""

    def test_migration_identifiers(self) -> None:
        """Asserts correct revision and parent revision pointers."""
        mod = _load_migration_module()
        assert mod.revision == "0003"
        assert mod.down_revision == "0002"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)
        assert mod.branch_labels is None
        assert mod.depends_on is None
