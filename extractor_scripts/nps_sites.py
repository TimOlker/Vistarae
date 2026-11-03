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

"""Extractor for US National Park System (NPS) sites."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure repository root is on sys.path for direct CLI script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bs4 import BeautifulSoup, Tag  # noqa: E402
from vistarae_core.schemas.extractor import (  # noqa: E402
    AdditionalAddressRecord,
    ExtractorRecord,
    WebsiteRecord,
)

from extractor_scripts.common.base import (  # noqa: E402
    BaseExtractor,
    extractor_options,
    run_extractor_cli,
)

NPS_BASE_URL = "https://www.nps.gov/findmypark/index.htm"


class NPSSitesExtractor(BaseExtractor):
    """Scrapes US National Park Service units with baseline and designation tags."""

    name = "NPSSites"
    default_tags: list[str] = ["NPS"]

    def _parse_additional_addresses(self, item: Tag) -> list[AdditionalAddressRecord]:
        """Extracts secondary locations into AdditionalAddressRecord domain objects.

        Args:
            item: BeautifulSoup park item element.

        Returns:
            List of secondary address records.
        """
        records: list[AdditionalAddressRecord] = []
        add_container = item.select_one(".additional-locations")
        if not add_container:
            return records

        locations = add_container.find_all(class_="location")
        for loc in locations:
            if not isinstance(loc, Tag):
                continue
            street = loc.get("data-street") or loc.get_text(strip=True)
            city = loc.get("data-city")
            state = loc.get("data-state")
            postal = loc.get("data-postal")
            lat_raw = loc.get("data-lat")
            lon_raw = loc.get("data-lon")

            lat = None
            lon = None
            if lat_raw and lon_raw:
                try:
                    lat = float(str(lat_raw))
                    lon = float(str(lon_raw))
                except ValueError:
                    pass

            records.append(
                AdditionalAddressRecord(
                    street_address=str(street) if street else None,
                    town_city=str(city) if city else None,
                    state_province=str(state) if state else None,
                    zip_code=str(postal) if postal else None,
                    latitude=lat,
                    longitude=lon,
                )
            )

        return records

    def _parse_park_item(self, item: Tag) -> ExtractorRecord | None:
        """Parses a park DOM node into an ExtractorRecord.

        Args:
            item: BeautifulSoup element containing park metadata.

        Returns:
            ExtractorRecord instance or None if invalid.
        """
        title_elem = item.find("h2") or item.find("h3") or item.select_one(".park-title")
        if not title_elem:
            return None

        link_elem = title_elem.find("a") if isinstance(title_elem, Tag) else None
        poi_name = title_elem.get_text(strip=True)
        if not poi_name:
            return None

        url = ""
        if link_elem and isinstance(link_elem, Tag):
            url = str(link_elem.get("href", ""))

        desig_elem = item.select_one(".designation")
        designation = desig_elem.get_text(strip=True) if desig_elem else ""

        state_elem = item.select_one(".state")
        state_raw = state_elem.get_text(strip=True) if state_elem else ""
        primary_state = state_raw.split(",")[0].strip() if state_raw else ""

        city_elem = item.select_one(".city")
        city = city_elem.get_text(strip=True) if city_elem else None

        street_elem = item.select_one(".street")
        street = street_elem.get_text(strip=True) if street_elem else None

        postal_elem = item.select_one(".postal")
        postal = postal_elem.get_text(strip=True) if postal_elem else None

        lat_elem = item.select_one(".lat")
        lon_elem = item.select_one(".lon")
        lat = None
        lon = None
        if lat_elem and lon_elem:
            try:
                lat = float(lat_elem.get_text(strip=True))
                lon = float(lon_elem.get_text(strip=True))
            except ValueError:
                pass

        # Resolve tags: baseline "NPS" + conditional designation tag
        conditional_tags = [designation] if designation else []
        tags = self.resolve_tags(conditional_tags)

        # JSON websites: only populate unique POI URLs, not source directory URL
        websites: list[WebsiteRecord] = []
        if url and url != NPS_BASE_URL:
            websites.append(WebsiteRecord(name="National Park Service", url=url))

        # Secondary locations
        additional_addresses = self._parse_additional_addresses(item)

        return ExtractorRecord(
            poi_name=poi_name,
            street_address=street,
            town_city=city,
            state_province=primary_state or None,
            zip_code=postal,
            country="United States",
            country_code="US",
            latitude=lat,
            longitude=lon,
            tags=tags,
            websites=websites,
            additional_addresses=additional_addresses,
        )

    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests NPS sites from directory.

        Returns:
            List of parsed ExtractorRecord objects.
        """
        html = self.http.get(NPS_BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".park-item")
        if not items:
            items = soup.find_all(class_=re.compile(r"park-item|park-row"))

        records: list[ExtractorRecord] = []
        for item in items:
            if not isinstance(item, Tag):
                continue
            rec = self._parse_park_item(item)
            if rec:
                records.append(rec)
                if self.config.limit and len(records) >= self.config.limit:
                    break

        return records


@extractor_options(default_output="nps_sites.csv")
def cli(
    output_path: Path | None,
    limit: int | None,
    delay_seconds: float,
    deep: bool,
    cache_enabled: bool,
    split_size: int,
    geocode_missing: bool,
    user_tags: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Extracts US National Park System units with baseline and designation tags."""
    run_extractor_cli(
        extractor_cls=NPSSitesExtractor,
        default_filename="nps_sites.csv",
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
        deep=deep,
        cache_enabled=cache_enabled,
        split_size=split_size,
        geocode_missing=geocode_missing,
        user_tags=user_tags,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    cli()
