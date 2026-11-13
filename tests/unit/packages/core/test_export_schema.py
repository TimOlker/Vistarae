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

"""Unit tests validating canonical ExportFieldDefinition schema registry (017-export)."""

from __future__ import annotations

from vistarae_core.schemas.export_schema import (
    CANONICAL_EXPORT_FIELDS,
    format_csv_cell,
    get_attribute_to_header_map,
    get_canonical_headers,
    get_header_to_attribute_map,
    serialize_candidate_value,
)


class TestExportSchemaRegistry:
    """Validates the canonical field definitions, header mappings, and cell formatters."""

    def test_canonical_fields_count_and_completeness(self) -> None:
        """Asserts that all 37 canonical candidate attributes are present in the registry."""
        assert len(CANONICAL_EXPORT_FIELDS) == 37

        attr_keys = {f.attribute_key for f in CANONICAL_EXPORT_FIELDS}
        required_keys = {
            "candidate_id",
            "row_index",
            "poi_name",
            "street_address",
            "city",
            "locality",
            "admin_level_2",
            "admin_level_1",
            "state_province",
            "postal_code",
            "country",
            "country_code",
            "latitude",
            "longitude",
            "recommended_disposition",
            "user_disposition",
            "confidence_score",
            "disposition_justification",
            "description",
            "reason_to_visit",
            "hero_image_url",
            "official_url",
            "wiki_url",
            "related_websites",
            "no_websites",
            "tags",
            "photo_directory",
            "photo_directories",
            "dates_visited",
            "recommended_duration_hours",
            "recommended_visit_days",
            "estimated_visit_time_notes",
            "parent_candidate_id",
            "parent_poi_id",
            "matched_existing_poi_id",
            "merge_target_id",
            "is_user_overridden",
        }
        assert required_keys.issubset(attr_keys)

    def test_canonical_headers_order(self) -> None:
        """Asserts that get_canonical_headers returns 37 ordered headers starting with Candidate ID."""
        headers = get_canonical_headers()
        assert len(headers) == 37
        assert headers[0] == "Candidate ID"
        assert headers[1] == "Row Index"
        assert headers[2] == "POI Name"
        assert "Tags" in headers
        assert "Related Websites" in headers
        assert "Locality" in headers
        assert "County / District (Admin Level 2)" in headers

    def test_header_to_attribute_map_aliasing(self) -> None:
        """Asserts case-insensitive mapping of headers and aliases."""
        mapping = get_header_to_attribute_map()
        assert mapping["poi name"] == "poi_name"
        assert mapping["town/city"] == "city"
        assert mapping["town_city"] == "city"
        assert mapping["city"] == "city"
        assert mapping["locality"] == "locality"
        assert mapping["admin_level_1"] == "admin_level_1"
        assert mapping["state"] == "admin_level_1"
        assert mapping["zip code"] == "postal_code"
        assert mapping["websites"] == "related_websites"

    def test_format_csv_cell_rfc4180(self) -> None:
        """Validates quoting and quote escaping under RFC 4180."""
        assert format_csv_cell("") == ""
        assert format_csv_cell("simple") == "simple"
        assert format_csv_cell("comma,separated") == '"comma,separated"'
        assert format_csv_cell('quote"inside') == '"quote""inside"'
        assert format_csv_cell("line\nbreak") == '"line\nbreak"'

    def test_attribute_to_header_map(self) -> None:
        """Asserts attribute_key to header_name mapping returns expected headers."""
        mapping = get_attribute_to_header_map()
        assert mapping["poi_name"] == "POI Name"
        assert mapping["candidate_id"] == "Candidate ID"
        assert len(mapping) == 37

    def test_serialize_candidate_value_formula_defense_and_types(self) -> None:
        """Asserts formatting across diverse field types and defensive sanitization."""
        poi_field = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "poi_name")
        assert serialize_candidate_value(poi_field, "=SUM(A1:A2)") == "'=SUM(A1:A2)"
        assert serialize_candidate_value(poi_field, "Normal Name") == "Normal Name"
        assert serialize_candidate_value(poi_field, None) == ""

        tags_field = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "tags")
        assert serialize_candidate_value(tags_field, "Preformatted; Tags") == "Preformatted; Tags"

        websites_field = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "related_websites")
        assert serialize_candidate_value(websites_field, "https://raw-url.com") == "https://raw-url.com"

        bool_field = next(f for f in CANONICAL_EXPORT_FIELDS if f.attribute_key == "is_user_overridden")
        assert serialize_candidate_value(bool_field, True) == "true"
        assert serialize_candidate_value(bool_field, False) == "false"

    def test_python_typescript_schema_parity(self) -> None:
        """Asserts that Python and TypeScript schema registries remain strictly synchronized (FR-009)."""
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        sys.path.insert(0, str(repo_root))
        try:
            from scripts.validate_export_schema_sync import main as validate_sync

            assert validate_sync() == 0
        finally:
            if str(repo_root) in sys.path:
                sys.path.remove(str(repo_root))
