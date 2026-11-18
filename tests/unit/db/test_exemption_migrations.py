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

"""Unit tests for the reversible 0018 missing data exemptions migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_migration_definition():
    """Verify revision 0018 implements upgrade and downgrade functions."""
    migration_path = Path("db/migrations/versions/20261118_add_missing_data_exemptions.py")
    assert migration_path.exists(), "Migration file must exist"

    spec = importlib.util.spec_from_file_location("migration_0018", migration_path)
    assert spec is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0018"
    assert migration.down_revision == "0017"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
