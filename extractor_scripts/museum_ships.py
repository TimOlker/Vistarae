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

"""Extractor for global preserved museum ships and historic warships."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

# Ensure repository root is on sys.path for direct CLI script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bs4 import BeautifulSoup, Tag  # noqa: E402
from vistarae_core.schemas.extractor import ExtractorRecord, WebsiteRecord  # noqa: E402

from extractor_scripts.common.base import (  # noqa: E402
    BaseExtractor,
    extractor_options,
    run_extractor_cli,
)

WIKI_SHIPS_URL = "https://en.wikipedia.org/wiki/List_of_museum_ships"

WARSHIP_KEYWORDS = {
    "warship",
    "naval",
    "navy",
    "battleship",
    "aircraft carrier",
    "cruiser",
    "destroyer",
    "frigate",
    "corvette",
    "submarine",
    "patrol boat",
    "torpedo boat",
    "minesweeper",
    "uss",
    "hms",
}

COUNTRY_MAP = {
    "United States": "US",
    "United Kingdom": "GB",
    "Canada": "CA",
    "Australia": "AU",
    "Germany": "DE",
    "Japan": "JP",
    "France": "FR",
    "Russia": "RU",
    "Sweden": "SE",
    "Norway": "NO",
    "Netherlands": "NL",
}


class MuseumShipsExtractor(BaseExtractor):
    """Scrapes preserved museum ships and historic warships."""

    name = "MuseumShips"
    default_tags: list[str] = ["Ship"]

    def _is_warship(self, poi_name: str, vessel_type: str) -> bool:
        """Determines if a ship qualifies as a warship / military vessel.

        Args:
            poi_name: Name of the vessel.
            vessel_type: Description or classification of vessel.

        Returns:
            True if military/warship, False otherwise.
        """
        combined = f"{poi_name} {vessel_type}".lower()
        return any(kw in combined for kw in WARSHIP_KEYWORDS)

    def _parse_coordinates(self, text: str) -> tuple[float | None, float | None]:
        """Parses coordinate pairs from text strings like '40.7645; -73.9996'.

        Args:
            text: Raw coordinate string.

        Returns:
            Tuple of (latitude, longitude).
        """
        match = re.search(r"(-?\d+\.\d+)[\s;,/]+(-?\d+\.\d+)", text)
        if match:
            try:
                return float(match.group(1)), float(match.group(2))
            except ValueError:
                pass
        return None, None

    def _parse_row(self, row: Tag) -> ExtractorRecord | None:
        """Parses a table row into an ExtractorRecord.

        Args:
            row: BeautifulSoup table row element.

        Returns:
            ExtractorRecord or None if invalid.
        """
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            return None

        name_elem = cells[0].find("a") or cells[0]
        poi_name = name_elem.get_text(strip=True)
        if not poi_name or poi_name.lower() in ("ship name", "name", "vessel"):
            return None

        wiki_href = ""
        if isinstance(name_elem, Tag) and name_elem.name == "a":
            wiki_href = str(name_elem.get("href", ""))
        wiki_url = urljoin(WIKI_SHIPS_URL, wiki_href) if wiki_href else ""

        vessel_type = cells[1].get_text(strip=True)
        country_name = cells[2].get_text(strip=True)
        berth_location = cells[3].get_text(strip=True)

        city = berth_location
        state = None
        if "," in berth_location:
            parts = [p.strip() for p in berth_location.split(",")]
            city = parts[0]
            if len(parts) > 1 and len(parts[1]) <= 3:
                state = parts[1]

        # Coordinates
        lat, lon = None, None
        if len(cells) > 4:
            geo_elem = cells[4].select_one(".geo") or cells[4]
            lat, lon = self._parse_coordinates(geo_elem.get_text(strip=True))

        # Museum link: only populate unique URLs, omit directory list URL
        websites: list[WebsiteRecord] = []
        if wiki_href and wiki_url != WIKI_SHIPS_URL:
            websites.append(WebsiteRecord(name="Wikipedia", url=wiki_url))

        if len(cells) > 5:
            museum_link = cells[5].find("a")
            if museum_link and isinstance(museum_link, Tag) and museum_link.get("href"):
                url = str(museum_link.get("href"))
                if url and url != WIKI_SHIPS_URL:
                    name = museum_link.get_text(strip=True) or "Official Museum"
                    websites.append(WebsiteRecord(name=name, url=url))

        # Tag logic: baseline "Ship" + conditional "Military" (no naval classification)
        conditional_tags = ["Military"] if self._is_warship(poi_name, vessel_type) else []
        tags = self.resolve_tags(conditional_tags)

        country_code = COUNTRY_MAP.get(country_name, "")

        return ExtractorRecord(
            poi_name=poi_name,
            town_city=city,
            state_province=state,
            country=country_name,
            country_code=country_code,
            latitude=lat,
            longitude=lon,
            tags=tags,
            websites=websites,
        )

    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests preserved museum ships from Wikipedia directory.

        Returns:
            List of parsed ExtractorRecord items.
        """
        html = self.http.get(WIKI_SHIPS_URL)
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", class_=re.compile(r"wikitable"))
        if not tables:
            tables = soup.find_all("table")

        records: list[ExtractorRecord] = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                if not isinstance(row, Tag):
                    continue
                rec = self._parse_row(row)
                if rec:
                    records.append(rec)
                    if self.config.limit and len(records) >= self.config.limit:
                        return records

        return records


@extractor_options(default_output="museum_ships.csv")
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
    """Extracts preserved museum ships and warships."""
    run_extractor_cli(
        extractor_cls=MuseumShipsExtractor,
        default_filename="museum_ships.csv",
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
