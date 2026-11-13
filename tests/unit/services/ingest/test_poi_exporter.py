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

"""Unit tests for POIExporter streaming serializer, UTF-8 BOM, formula escaping, and schema parity."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import yaml
from vistarae_core.domain.value_objects import IngestDisposition
from vistarae_core.schemas.poi_exchange import POIExchangeRecord
from vistarae_core.services.poi_exporter import POIExporter


@pytest.fixture
def sample_records() -> list[POIExchangeRecord]:
    """Provides test records including special characters, formula injection candidates, and non-ASCII text."""
    rec1 = POIExchangeRecord(
        poi_id=uuid4(),
        poi_name="Senso-ji (浅草寺)",
        latitude=35.7148,
        longitude=139.7967,
        street_address="2-3-1 Asakusa",
        city="Taito City",
        state_province="Tokyo",
        postal_code="111-0032",
        country="Japan",
        tags=["Temple", "Historic", "Scenic"],
        dates_visited=["2023-04-12", "2024-05-10"],
        photo_directory="M:\\Photos\\2023\\Japan\\Tokyo\\Senso-ji",
        location_confidence_percent=98,
        user_disposition=IngestDisposition.ACCEPT,
        ai_description="Ancient Buddhist temple located in Asakusa.",
        reason_to_visit="Oldest temple in Tokyo.",
        recommended_duration_hours=2.5,
        itinerary_days=1,
        hero_image_url="https://images.unsplash.com/sensoji.jpg",
        official_website="https://www.senso-ji.jp",
        wikipedia_url="https://en.wikipedia.org/wiki/Sens%C5%8D-ji",
    )
    rec2 = POIExchangeRecord(
        poi_name="=SUM(A1:A10)",  # Formula injection candidate
        latitude=48.8584,
        longitude=2.2945,
        street_address="@Champ de Mars",  # Formula injection candidate
        city="+Paris",  # Formula injection candidate
        country="France",
        tags=["Monument"],
        rejection_reason="Duplicate candidate within 50m",
        user_disposition=IngestDisposition.IGNORE,
    )
    return [rec1, rec2]


def test_dynamic_schema_introspection():
    """Asserts that exporter derives column headers dynamically from POIExchangeRecord."""
    headers = POIExporter.get_export_headers()
    expected_fields = list(POIExchangeRecord.model_fields.keys())
    assert headers == expected_fields
    assert "poi_name" in headers
    assert "latitude" in headers
    assert "longitude" in headers
    assert "created_at" in headers


def test_csv_export_starts_with_utf8_bom(sample_records: list[POIExchangeRecord]):
    """Asserts that CSV export bytes prepend the UTF-8 Byte Order Mark."""
    csv_bytes = POIExporter.export_csv_bytes(sample_records)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    decoded_text = csv_bytes.decode("utf-8-sig")
    assert "Senso-ji (浅草寺)" in decoded_text


def test_csv_formula_injection_escaping(sample_records: list[POIExchangeRecord]):
    """Asserts that cells starting with '=', '+', '-', '@' are neutralized with a leading single quote."""
    csv_bytes = POIExporter.export_csv_bytes(sample_records)
    decoded_text = csv_bytes.decode("utf-8-sig")

    # Assert formulas are sanitized
    assert "'=SUM(A1:A10)" in decoded_text
    assert "'@Champ de Mars" in decoded_text
    assert "'+Paris" in decoded_text


def test_json_export_structure(sample_records: list[POIExchangeRecord]):
    """Asserts that JSON export outputs a valid array of objects matching POIExchangeRecord."""
    json_str = POIExporter.export_json_str(sample_records)
    data = json.loads(json_str)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["poi_name"] == "Senso-ji (浅草寺)"
    assert data[0]["latitude"] == 35.7148
    assert data[1]["poi_name"] == "=SUM(A1:A10)"


def test_yaml_export_structure(sample_records: list[POIExchangeRecord]):
    """Asserts that YAML export outputs a valid YAML document matching POIExchangeRecord."""
    yaml_str = POIExporter.export_yaml_str(sample_records)
    data = yaml.safe_load(yaml_str)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["poi_name"] == "Senso-ji (浅草寺)"
    assert data[1]["country"] == "France"


def test_streaming_csv_chunks(sample_records: list[POIExchangeRecord]):
    """Asserts that chunked generator yields header and record rows properly."""
    chunks = list(POIExporter.stream_csv_chunks(sample_records))
    assert len(chunks) >= 2
    combined = "".join(chunks)
    assert combined.startswith("\ufeff")  # BOM in Python unicode
    assert "Senso-ji" in combined


def test_stream_candidate_export_chunks_full_fidelity():
    """Asserts that stream_candidate_export_chunks streams all 37 attributes with UTF-8 BOM."""
    from tests.fixtures.export_fixtures import get_sample_staged_candidates
    candidates = get_sample_staged_candidates()

    chunks = list(POIExporter.stream_candidate_export_chunks(candidates, chunk_size=1))
    combined = "".join(chunks)

    assert combined.startswith("\ufeff")
    lines = combined.replace("\ufeff", "").split("\r\n")
    headers = lines[0].split(",")

    assert len(headers) == 37
    assert headers[0] == "Candidate ID"
    assert headers[2] == "POI Name"
    assert headers[5] == "Locality"
    assert headers[6] == "County / District (Admin Level 2)"

    # Row 1 check
    assert "Yellowstone National Park" in lines[1]
    assert "Mammoth Hot Springs" in lines[1]
    assert "Park County" in lines[1]
    assert "National Park; Geyser; Wildlife; Scenic" in lines[1]

    # Row 2 check (formula sanitized)
    assert "'=Grand Prismatic Spring" in lines[2]
    assert "'+Sublocation nested" in lines[2]
    assert "'@Largest hot spring" in lines[2]
