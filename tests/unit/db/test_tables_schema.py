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

"""Unit tests for SQLAlchemy table schema definitions for missing data exemptions."""

from vistarae_core.adapters.db.tables import IngestCandidateTable, POITable
from vistarae_core.domain.entities import POI, IngestCandidate


def test_poi_table_has_exemption_columns():
    """Verify POITable defines no_address and no_websites columns."""
    poi_cols = {c.name for c in POITable.__table__.columns}
    assert "no_address" in poi_cols
    assert "no_websites" in poi_cols

    poi_no_addr = POITable.__table__.columns["no_address"]
    poi_no_web = POITable.__table__.columns["no_websites"]
    assert not poi_no_addr.nullable
    assert not poi_no_web.nullable


def test_ingest_candidate_table_has_exemption_columns():
    """Verify IngestCandidateTable defines no_address and no_websites columns."""
    cand_cols = {c.name for c in IngestCandidateTable.__table__.columns}
    assert "no_address" in cand_cols
    assert "no_websites" in cand_cols

    cand_no_addr = IngestCandidateTable.__table__.columns["no_address"]
    cand_no_web = IngestCandidateTable.__table__.columns["no_websites"]
    assert not cand_no_addr.nullable
    assert not cand_no_web.nullable


def test_domain_entities_have_exemption_attributes():
    """Verify POI and IngestCandidate dataclasses default exemption attributes to False."""
    poi = POI(
        id=None,  # type: ignore
        user_id=None,  # type: ignore
        name="Test",
        geom=None,  # type: ignore
    )
    assert poi.no_address is False
    assert poi.no_websites is False

    cand = IngestCandidate(
        id=None,  # type: ignore
        user_id=None,  # type: ignore
        job_id=None,  # type: ignore
        row_index=0,
        poi_name="Test",
    )
    assert cand.no_address is False
    assert cand.no_websites is False
