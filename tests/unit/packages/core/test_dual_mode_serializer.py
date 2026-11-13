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

"""Unit tests validating dual-mode serialization and deserialization (017-export)."""

from __future__ import annotations

from vistarae_core.schemas.export_schema import (
    deserialize_json_pairs,
    deserialize_string_list,
    serialize_json_pairs,
    serialize_string_list,
)


class TestDualModeSerializer:
    """Validates tolerant parsing of JSON arrays and semicolon-separated strings."""

    def test_serialize_and_deserialize_string_list_semicolon(self) -> None:
        """Tests semicolon serialization and deserialization of simple string lists."""
        tags = ["Volcano", "Scenic", "National Park"]
        serialized = serialize_string_list(tags)
        assert serialized == "Volcano; Scenic; National Park"

        deserialized = deserialize_string_list(serialized)
        assert deserialized == tags

    def test_deserialize_string_list_from_json_array(self) -> None:
        """Asserts deserialize_string_list seamlessly accepts JSON array strings."""
        json_str = '["Volcano", "Scenic", "National Park"]'
        deserialized = deserialize_string_list(json_str)
        assert deserialized == ["Volcano", "Scenic", "National Park"]

    def test_deserialize_string_list_whitespace_handling(self) -> None:
        """Asserts whitespace around delimiters is cleanly trimmed."""
        messy_str = " Volcano ;  Scenic  ;National Park "
        deserialized = deserialize_string_list(messy_str)
        assert deserialized == ["Volcano", "Scenic", "National Park"]

    def test_serialize_and_deserialize_json_pairs(self) -> None:
        """Tests JSON serialization and roundtrip deserialization of website objects."""
        websites = [
            {"name": "NPS Official", "url": "https://nps.gov/yell"},
            {"name": "Lodging Guide", "url": "https://yellowstone.com"},
        ]
        serialized = serialize_json_pairs(websites)
        assert serialized.startswith("[") and serialized.endswith("]")

        deserialized = deserialize_json_pairs(serialized)
        assert deserialized == websites

    def test_deserialize_json_pairs_from_delimited_string_fallback(self) -> None:
        """Asserts deserialize_json_pairs gracefully parses delimited URL strings as default objects."""
        url_list = "https://nps.gov/yell; https://yellowstone.com"
        deserialized = deserialize_json_pairs(url_list)
        assert len(deserialized) == 2
        assert deserialized[0]["url"] == "https://nps.gov/yell"
        assert deserialized[1]["url"] == "https://yellowstone.com"

    def test_null_and_empty_inputs(self) -> None:
        """Asserts null and empty inputs serialize and deserialize cleanly to empty values."""
        assert serialize_string_list(None) == ""
        assert serialize_string_list([]) == ""
        assert deserialize_string_list("") == []
        assert deserialize_string_list(None) == []

        assert serialize_json_pairs(None) == ""
        assert serialize_json_pairs([]) == ""
        assert deserialize_json_pairs("") == []
        assert deserialize_json_pairs(None) == []

    def test_corrupted_json_graceful_fallbacks(self) -> None:
        """Asserts corrupted bracketed strings fall back gracefully to delimited splitting."""
        assert deserialize_string_list("[broken, json]") == ["[broken", "json]"]
        assert deserialize_json_pairs("[broken, json]") == [
            {"name": "[broken", "url": "[broken"},
            {"name": "json]", "url": "json]"},
        ]

    def test_deserialize_json_pairs_with_string_elements(self) -> None:
        """Asserts JSON array of raw string URLs unpacks into name/url objects."""
        raw_json = '["https://nps.gov", "https://usda.gov"]'
        deserialized = deserialize_json_pairs(raw_json)
        assert len(deserialized) == 2
        assert deserialized[0] == {"name": "https://nps.gov", "url": "https://nps.gov"}
        assert deserialized[1] == {"name": "https://usda.gov", "url": "https://usda.gov"}
