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

"""RFC 4180 CSV exporter with formula neutralization and automatic partitioning."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path

from vistarae_core.schemas.extractor import (
    CSV_HEADERS,
    ExtractorRecord,
    neutralize_formula_injection,
)


class CSVExporter:
    """Serializes ExtractorRecord collections into standardized RFC 4180 CSV files."""

    @staticmethod
    def serialize_record(record: ExtractorRecord) -> dict[str, str]:
        """Maps an ExtractorRecord to standardized sanitized CSV column values.

        Args:
            record: Authoritative extracted POI record.

        Returns:
            Dictionary mapping CSV header strings to sanitized cell value strings.
        """
        lat_str = str(record.latitude) if record.latitude is not None else ""
        lon_str = str(record.longitude) if record.longitude is not None else ""
        hours_str = (
            str(record.estimated_visit_hours) if record.estimated_visit_hours is not None else ""
        )
        days_str = str(record.itinerary_days) if record.itinerary_days is not None else ""

        # Semicolon-delimited collections
        tags_val = "; ".join(record.tags) if record.tags else ""
        dates_val = "; ".join(record.dates_visited) if record.dates_visited else ""

        # JSON-encoded complex columns
        websites_json = (
            json.dumps([w.model_dump() for w in record.websites], ensure_ascii=False)
            if record.websites
            else ""
        )
        addrs_json = (
            json.dumps(
                [
                    {
                        k: (str(v) if k in ("latitude", "longitude") and v is not None else v)
                        for k, v in addr.model_dump(exclude_none=True).items()
                    }
                    for addr in record.additional_addresses
                ],
                ensure_ascii=False,
            )
            if record.additional_addresses
            else ""
        )

        return {
            "POI Name": neutralize_formula_injection(record.poi_name),
            "Street Address": neutralize_formula_injection(record.street_address),
            "Town/City": neutralize_formula_injection(record.town_city),
            "State/Province": neutralize_formula_injection(record.state_province),
            "Zip Code": neutralize_formula_injection(record.zip_code),
            "Country": neutralize_formula_injection(record.country),
            "Country Code": neutralize_formula_injection(record.country_code),
            "latitude": lat_str,
            "longitude": lon_str,
            "Tags": neutralize_formula_injection(tags_val),
            "Hero Image URL": neutralize_formula_injection(record.hero_image_url),
            "Websites": neutralize_formula_injection(websites_json),
            "Additional Address": neutralize_formula_injection(addrs_json),
            "Estimated Visit Hours": hours_str,
            "Itinerary Days": days_str,
            "Description": neutralize_formula_injection(
                record.description[:4000] if record.description else ""
            ),
            "Reason to Visit": neutralize_formula_injection(
                record.reason_to_visit[:4000] if record.reason_to_visit else ""
            ),
            "Photo Directory": neutralize_formula_injection(record.photo_directory),
            "Dates Visited": neutralize_formula_injection(dates_val),
        }

    @classmethod
    def _write_single_csv(cls, records: Sequence[ExtractorRecord], path: Path) -> None:
        """Writes a batch of records to a single CSV file.

        Args:
            records: Slice of ExtractorRecord objects to serialize.
            path: Target file path on disk.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=CSV_HEADERS,
                dialect="excel",
                lineterminator="\r\n",
            )
            writer.writeheader()
            for rec in records:
                writer.writerow(cls.serialize_record(rec))

    @classmethod
    def export(
        cls,
        records: Sequence[ExtractorRecord],
        output_path: Path,
        split_size: int = 2000,
    ) -> list[Path]:
        """Serializes records into one or more partitioned RFC 4180 CSV files.

        If records exceed split_size (default 2,000), partitions are generated
        using the pattern {stem}_part{n}{suffix} to comply with upload limits.

        Args:
            records: Collection of ExtractorRecord instances to export.
            output_path: Destination path specified by user.
            split_size: Maximum row count permitted per file.

        Returns:
            List of Path objects representing all generated CSV files.
        """
        if not records:
            cls._write_single_csv([], output_path)
            return [output_path]

        total_rows = len(records)
        if total_rows <= split_size:
            cls._write_single_csv(records, output_path)
            return [output_path]

        output_files: list[Path] = []
        stem = output_path.stem
        suffix = output_path.suffix or ".csv"
        parent = output_path.parent

        part_num = 1
        for start_idx in range(0, total_rows, split_size):
            chunk = records[start_idx : start_idx + split_size]
            part_path = parent / f"{stem}_part{part_num}{suffix}"
            cls._write_single_csv(chunk, part_path)
            output_files.append(part_path)
            part_num += 1

        return output_files
