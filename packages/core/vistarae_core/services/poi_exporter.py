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

"""Streaming POI exporter supporting dynamic schema introspection, UTF-8 BOM, and formula sanitization."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

import yaml

from vistarae_core.schemas.export_schema import (
    CANONICAL_EXPORT_FIELDS,
    get_canonical_headers,
    serialize_candidate_value,
)
from vistarae_core.schemas.poi_exchange import POIExchangeRecord

# Formula injection trigger characters
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
UTF8_BOM = "\ufeff"
UTF8_BOM_BYTES = b"\xef\xbb\xbf"


class POIExporter:
    """High-performance serializer and streaming generator for POI datasets."""

    @classmethod
    def get_export_headers(cls) -> list[str]:
        """Dynamically introspects and returns all core field names from POIExchangeRecord.

        Returns:
            list[str]: Ordered list of field names.
        """
        return POIExchangeRecord.get_export_field_names()

    @staticmethod
    def sanitize_cell(value: Any) -> str:
        """Sanitizes cell value for CSV export, neutralizing spreadsheet formula injection.

        Args:
            value: The field value to format.

        Returns:
            str: Formula-safe string representation.
        """
        if value is None:
            return ""
        s = str(value)
        if s.startswith(FORMULA_PREFIXES):
            return f"'{s}"
        return s

    @classmethod
    def stream_csv_chunks(
        cls, records: Iterable[POIExchangeRecord], chunk_size: int = 100
    ) -> Iterator[str]:
        """Streams an RFC 4180 CSV document with prepended UTF-8 BOM.

        Args:
            records: Iterable stream of POIExchangeRecord items.
            chunk_size: Number of records to buffer per chunk.

        Yields:
            str: Chunk of CSV text.
        """
        headers = cls.get_export_headers()
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")

        # Yield BOM + Header row
        output.write(UTF8_BOM)
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Stream data rows
        buffer_count = 0
        for record in records:
            row_dict = record.to_export_dict()
            row = [cls.sanitize_cell(row_dict.get(h, "")) for h in headers]
            writer.writerow(row)
            buffer_count += 1
            if buffer_count >= chunk_size:
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                buffer_count = 0

        # Yield any trailing buffered rows
        remainder = output.getvalue()
        if remainder:
            yield remainder

    @classmethod
    def stream_candidate_export_chunks(
        cls, candidates: Iterable[Any], chunk_size: int = 100
    ) -> Iterator[str]:
        """Streams full-fidelity RFC 4180 CSV chunks for staged workbench candidates.

        Prepends UTF-8 BOM, outputs canonical headers, applies formula sanitization,
        and serializes all 37 attributes.

        Args:
            candidates: Iterable stream of IngestCandidateTable rows or candidate dicts.
            chunk_size: Number of records to buffer per yielded chunk.

        Yields:
            str: Chunk of CSV text.
        """
        headers = get_canonical_headers()
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")

        # Yield BOM + Canonical header row
        output.write(UTF8_BOM)
        writer.writerow(headers)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        buffer_count = 0
        for cand in candidates:
            row: list[str] = []
            for field_def in CANONICAL_EXPORT_FIELDS:
                key = field_def.attribute_key
                if isinstance(cand, dict):
                    raw_val = cand.get(key)
                    if raw_val is None and key == "candidate_id":
                        raw_val = cand.get("id")
                else:
                    raw_val = getattr(cand, key, None)
                    if raw_val is None and key == "candidate_id":
                        raw_val = getattr(cand, "id", None)

                if raw_val is None and field_def.default_value is not None:
                    raw_val = field_def.default_value

                val_str = serialize_candidate_value(field_def, raw_val)
                row.append(val_str)

            writer.writerow(row)
            buffer_count += 1
            if buffer_count >= chunk_size:
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                buffer_count = 0

        remainder = output.getvalue()
        if remainder:
            yield remainder

    @classmethod
    def export_csv_bytes(cls, records: Sequence[POIExchangeRecord]) -> bytes:
        """Serializes records into a complete CSV byte array prepended with UTF-8 BOM.

        Args:
            records: Sequence of POIExchangeRecord items.

        Returns:
            bytes: Encoded CSV bytes.
        """
        full_text = "".join(cls.stream_csv_chunks(records, chunk_size=len(records) or 1))
        # Note: full_text starts with \ufeff, which encodes to \xef\xbb\xbf in utf-8
        return full_text.encode("utf-8")

    @classmethod
    def export_json_str(cls, records: Sequence[POIExchangeRecord]) -> str:
        """Serializes records into a structured JSON array string.

        Args:
            records: Sequence of POIExchangeRecord items.

        Returns:
            str: Formatted JSON string.
        """
        dumped = [r.model_dump(mode="json") for r in records]
        return json.dumps(dumped, ensure_ascii=False, indent=2)

    @classmethod
    def stream_json_chunks(
        cls, records: Iterable[POIExchangeRecord], chunk_size: int = 100
    ) -> Iterator[str]:
        """Streams a JSON array document in discrete string chunks.

        Args:
            records: Iterable of POIExchangeRecord items.
            chunk_size: Number of items per streamed chunk.

        Yields:
            str: Chunk of JSON array text.
        """
        yield "[\n"
        first = True
        buffer: list[str] = []
        for record in records:
            prefix = "" if first else ",\n"
            first = False
            item_json = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2)
            # Indent array elements
            indented = "\n".join("  " + line for line in item_json.splitlines())
            buffer.append(f"{prefix}{indented}")
            if len(buffer) >= chunk_size:
                yield "".join(buffer)
                buffer.clear()
        if buffer:
            yield "".join(buffer)
        yield "\n]"

    @classmethod
    def export_yaml_str(cls, records: Sequence[POIExchangeRecord]) -> str:
        """Serializes records into a YAML document string.

        Args:
            records: Sequence of POIExchangeRecord items.

        Returns:
            str: Formatted YAML string.
        """
        dumped = [r.model_dump(mode="json") for r in records]
        return yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)

    @classmethod
    def stream_yaml_chunks(
        cls, records: Iterable[POIExchangeRecord], chunk_size: int = 100
    ) -> Iterator[str]:
        """Streams a YAML document in discrete string chunks.

        Args:
            records: Iterable of POIExchangeRecord items.
            chunk_size: Number of items per chunk.

        Yields:
            str: Chunk of YAML text.
        """
        # YAML lists can stream items prefixed by '- '
        buffer: list[str] = []
        for record in records:
            item_dict = [record.model_dump(mode="json")]
            item_yaml = yaml.safe_dump(item_dict, sort_keys=False, allow_unicode=True)
            buffer.append(item_yaml)
            if len(buffer) >= chunk_size:
                yield "".join(buffer)
                buffer.clear()
        if buffer:
            yield "".join(buffer)
