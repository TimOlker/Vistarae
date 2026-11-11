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

"""Extractor for aviation and aerospace museums worldwide."""

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

AVIATION_MUSEUMS_URL = "https://en.wikipedia.org/wiki/List_of_aviation_museums"

COUNTRY_MAP = {
    "Afghanistan": "AF",
    "Argentina": "AR",
    "Armenia": "AM",
    "Australia": "AU",
    "Austria": "AT",
    "Belarus": "BY",
    "Belgium": "BE",
    "Bolivia": "BO",
    "Brazil": "BR",
    "Bulgaria": "BG",
    "Burma": "MM",
    "Cambodia": "KH",
    "Canada": "CA",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "Croatia": "HR",
    "Cuba": "CU",
    "Czech Republic": "CZ",
    "Denmark": "DK",
    "Ecuador": "EC",
    "El Salvador": "SV",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Honduras": "HN",
    "Hungary": "HU",
    "Iceland": "IS",
    "India": "IN",
    "Indonesia": "ID",
    "Iran": "IR",
    "Ireland": "IE",
    "Israel": "IL",
    "Italy": "IT",
    "Japan": "JP",
    "Laos": "LA",
    "Latvia": "LV",
    "Lebanon": "LB",
    "Lithuania": "LT",
    "Malaysia": "MY",
    "Malta": "MT",
    "Mexico": "MX",
    "Nepal": "NP",
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Nigeria": "NG",
    "Norway": "NO",
    "Pakistan": "PK",
    "Peru": "PE",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Russia": "RU",
    "Saudi Arabia": "SA",
    "Serbia": "RS",
    "Singapore": "SG",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "South Africa": "ZA",
    "South Korea": "KR",
    "Spain": "ES",
    "Sri Lanka": "LK",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Taiwan": "TW",
    "Thailand": "TH",
    "Turkey": "TR",
    "Ukraine": "UA",
    "United Arab Emirates": "AE",
    "United Kingdom": "GB",
    "United States": "US",
    "Uruguay": "UY",
    "Venezuela": "VE",
    "Vietnam": "VN",
    "Zimbabwe": "ZW",
}


class AircraftMuseumsExtractor(BaseExtractor):
    """Scrapes aviation museums with Aircraft baseline tag."""

    name = "AircraftMuseums"
    default_tags: list[str] = ["Aircraft"]

    def _parse_coordinates(self, text: str) -> tuple[float | None, float | None]:
        """Parses coordinate pairs from text strings like '38.8882; -77.0199'.

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
        if not poi_name or poi_name.lower() in ("museum name", "name", "museum"):
            return None

        wiki_href = ""
        if isinstance(name_elem, Tag) and name_elem.name == "a":
            wiki_href = str(name_elem.get("href", ""))
        wiki_url = urljoin(AVIATION_MUSEUMS_URL, wiki_href) if wiki_href else ""

        country_name = cells[1].get_text(strip=True)
        state_region = cells[2].get_text(strip=True) if len(cells) > 2 else None
        city_airfield = cells[3].get_text(strip=True) if len(cells) > 3 else None

        # Coordinates
        lat, lon = None, None
        if len(cells) > 4:
            geo_elem = cells[4].select_one(".geo") or cells[4]
            lat, lon = self._parse_coordinates(geo_elem.get_text(strip=True))

        # Websites: only populate unique URLs, omit directory list URL
        websites: list[WebsiteRecord] = []
        if wiki_href and wiki_url != AVIATION_MUSEUMS_URL:
            websites.append(WebsiteRecord(name="Wikipedia", url=wiki_url))

        if len(cells) > 5:
            museum_link = cells[5].find("a")
            if museum_link and isinstance(museum_link, Tag) and museum_link.get("href"):
                url = str(museum_link.get("href"))
                if url and url != AVIATION_MUSEUMS_URL:
                    name = museum_link.get_text(strip=True) or "Official Website"
                    websites.append(WebsiteRecord(name=name, url=url))

        # Tag resolution: baseline Aircraft ONLY (no collection focus tags)
        tags = self.resolve_tags([])

        country_code = COUNTRY_MAP.get(country_name, "")

        return ExtractorRecord(
            poi_name=poi_name,
            town_city=city_airfield,
            state_province=state_region,
            country=country_name,
            country_code=country_code,
            latitude=lat,
            longitude=lon,
            tags=tags,
            websites=websites,
        )

    def _parse_list_item(
        self, li: Tag, country_name: str, region_name: str
    ) -> ExtractorRecord | None:
        """Parses a museum list item from a Wikipedia country or region section.

        Args:
            li: DOM list item element.
            country_name: Authoritative country name from parent h2 section.
            region_name: State, province, or region name from parent h3 section.

        Returns:
            ExtractorRecord instance or None if invalid.
        """
        a_tag = li.find("a")
        if not a_tag or not isinstance(a_tag, Tag):
            return None

        poi_name = a_tag.get_text(strip=True)
        if not poi_name or poi_name.lower().startswith(("category:", "list of")):
            return None

        href = str(a_tag.get("href", "")).strip()
        wiki_url = (
            urljoin("https://en.wikipedia.org", href) if href and not href.startswith("#") else ""
        )

        full_txt = li.get_text(strip=True)
        cleaned_txt = re.sub(r"\[.*?\]", "", full_txt).strip()
        loc_part = (
            cleaned_txt[len(poi_name) :].strip(" ,–-\t\r\n")
            if cleaned_txt.startswith(poi_name)
            else ""
        )

        country_code = COUNTRY_MAP.get(country_name, "")
        tags = self.resolve_tags([])

        websites: list[WebsiteRecord] = []
        if wiki_url and wiki_url != AVIATION_MUSEUMS_URL:
            websites.append(WebsiteRecord(name="Wikipedia", url=wiki_url))

        return ExtractorRecord(
            poi_name=poi_name,
            town_city=loc_part or None,
            state_province=region_name or None,
            country=country_name,
            country_code=country_code,
            tags=tags,
            websites=websites,
        )

    def _harvest_from_wiki_sections(self, soup: BeautifulSoup) -> list[ExtractorRecord]:
        """Harvests aviation museums from Wikipedia's section/list hierarchy.

        Args:
            soup: Parsed HTML of the Wikipedia list page.

        Returns:
            List of parsed ExtractorRecord items.
        """
        non_country_headings = {
            "Contents",
            "References",
            "See also",
            "External links",
            "Notes",
            "Bibliography",
        }
        records: list[ExtractorRecord] = []

        for section in soup.select(".mw-parser-output > section"):
            h2 = section.find("h2")
            if not h2:
                continue
            country = h2.get_text(strip=True).replace("[edit]", "").strip()
            if not country or country in non_country_headings:
                continue

            inner_sections = section.find_all("section", recursive=False)
            if inner_sections:
                for inner in inner_sections:
                    h3 = inner.find(["h3", "h4"])
                    region = h3.get_text(strip=True).replace("[edit]", "").strip() if h3 else ""
                    for li in inner.find_all("li"):
                        rec = self._parse_list_item(li, country, region)
                        if rec:
                            records.append(rec)
            else:
                for li in section.find_all("li"):
                    rec = self._parse_list_item(li, country, "")
                    if rec:
                        records.append(rec)

        return records

    def _harvest_from_tables(self, soup: BeautifulSoup) -> list[ExtractorRecord]:
        """Harvests aviation museums from structured wikitable elements (test fixture).

        Args:
            soup: Parsed HTML containing wikitable elements.

        Returns:
            List of parsed ExtractorRecord items.
        """
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
        return records

    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests aviation museums from Wikipedia directory.

        Returns:
            List of parsed ExtractorRecord items.
        """
        html = self.http.get(AVIATION_MUSEUMS_URL)
        soup = BeautifulSoup(html, "html.parser")

        if soup.select("table.wikitable"):
            records = self._harvest_from_tables(soup)
        else:
            records = self._harvest_from_wiki_sections(soup)

        if self.config.limit:
            return records[: self.config.limit]
        return records


@extractor_options(default_output="aircraft_museums.csv")
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
    """Extracts aviation and aerospace museums worldwide."""
    run_extractor_cli(
        extractor_cls=AircraftMuseumsExtractor,
        default_filename="aircraft_museums.csv",
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
