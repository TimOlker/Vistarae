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

"""Extractor for Hillman 1,000 Wonders of the World."""

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

HILLMAN_BASE_URL = "https://www.hillmanwonders.com/top_1000/index.htm"

COUNTRY_CODE_MAP = {
    "Egypt": "EG",
    "China": "CN",
    "India": "IN",
    "Greece": "GR",
    "Germany": "DE",
    "United States": "US",
    "Italy": "IT",
    "France": "FR",
    "Peru": "PE",
    "Jordan": "JO",
    "Brazil": "BR",
    "Mexico": "MX",
    "United Kingdom": "GB",
    "Spain": "ES",
    "Japan": "JP",
    "Australia": "AU",
    "Canada": "CA",
}


class HillmanWondersExtractor(BaseExtractor):
    """Scrapes ranked global wonders from Hillman Wonders directory."""

    name = "HillmanWonders"
    default_tags: list[str] = []

    def _determine_tier_tag(self, rank: int, award_text: str) -> str:
        """Determines the appropriate HillmanWonder tier tag.

        Args:
            rank: Integer ranking.
            award_text: Text from the award column.

        Returns:
            Specific tier tag string (Gold, Silver, or Bronze).
        """
        award_lower = award_text.lower()
        if "gold" in award_lower or (rank > 0 and rank <= 100):
            return "HillmanWonder:Gold"
        if "silver" in award_lower or (rank > 100 and rank <= 200):
            return "HillmanWonder:Silver"
        return "HillmanWonder:Bronze"

    def _parse_subpage_details(
        self, subpage_url: str
    ) -> tuple[str | None, str | None, float | None, float | None, float | None]:
        """Harvests extended details from a wonder subpage when --deep is specified.

        Args:
            subpage_url: Absolute URL to the individual wonder page.

        Returns:
            Tuple of (hero_image_url, overview_text, est_hours, latitude, longitude).
        """
        try:
            html = self.http.get(subpage_url)
        except Exception:
            return None, None, None, None, None

        soup = BeautifulSoup(html, "html.parser")
        hero_url = None
        img_elem = soup.select_one("img.hero") or soup.find("img")
        if img_elem and isinstance(img_elem, Tag) and img_elem.get("src"):
            hero_url = urljoin(subpage_url, str(img_elem.get("src")))

        overview = None
        overview_div = soup.select_one(".overview") or soup.find("p")
        if overview_div:
            overview = overview_div.get_text(strip=True)

        est_hours = None
        tips_div = soup.select_one(".tips")
        if tips_div:
            match = re.search(r"(\d+(?:\.\d+)?)\s+hours?", tips_div.get_text(), re.IGNORECASE)
            if match:
                est_hours = float(match.group(1))

        lat, lon = None, None
        coord_div = soup.select_one(".coordinates")
        if coord_div and isinstance(coord_div, Tag):
            data_lat = coord_div.get("data-lat")
            data_lon = coord_div.get("data-lon")
            if data_lat and data_lon:
                try:
                    lat = float(str(data_lat))
                    lon = float(str(data_lon))
                except ValueError:
                    pass

        return hero_url, overview, est_hours, lat, lon

    def _parse_row(self, row: Tag) -> ExtractorRecord | None:
        """Parses a single HTML table row into an ExtractorRecord.

        Args:
            row: BeautifulSoup table row Tag.

        Returns:
            ExtractorRecord if valid, otherwise None.
        """
        cells = row.find_all("td")
        if len(cells) < 3:
            return None

        rank_match = re.search(r"\d+", cells[0].get_text(strip=True))
        rank = int(rank_match.group(0)) if rank_match else 0

        name_elem = cells[1].find("a") or cells[1]
        poi_name = name_elem.get_text(strip=True)
        if not poi_name:
            return None

        href = ""
        if isinstance(name_elem, Tag) and name_elem.name == "a":
            href = str(name_elem.get("href", ""))
        subpage_url = urljoin(HILLMAN_BASE_URL, href) if href else HILLMAN_BASE_URL

        country_name = cells[2].get_text(strip=True)
        award_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        tier_tag = self._determine_tier_tag(rank, award_text)
        tags = self.resolve_tags([tier_tag])
        country_code = COUNTRY_CODE_MAP.get(country_name, "")

        websites = [WebsiteRecord(name="Hillman Wonders", url=subpage_url)]
        desc = f"Hillman Wonders ranked wonder #{rank}: {poi_name} in {country_name}."
        reason = f"Ranked #{rank} wonder in the world by Hillman Wonders."
        hero_url = None
        est_hours = None
        lat, lon = None, None

        if self.config.deep_scrape and href:
            hero_url, deep_desc, est_hours, dlat, dlon = self._parse_subpage_details(subpage_url)
            if deep_desc:
                desc = deep_desc
            if dlat is not None and dlon is not None:
                lat, lon = dlat, dlon

        return ExtractorRecord(
            poi_name=poi_name,
            country=country_name,
            country_code=country_code,
            latitude=lat,
            longitude=lon,
            tags=tags,
            websites=websites,
            hero_image_url=hero_url,
            estimated_visit_hours=est_hours,
            description=desc,
            reason_to_visit=reason,
        )

    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests ranked wonder records from Hillman Wonders index page.

        Returns:
            List of parsed ExtractorRecord items.
        """
        html = self.http.get(HILLMAN_BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.wonder_list") or soup.find("table")
        if not table:
            return []

        records: list[ExtractorRecord] = []
        rows = table.find_all("tr")
        for row in rows:
            if not isinstance(row, Tag):
                continue
            rec = self._parse_row(row)
            if rec:
                records.append(rec)
                if self.config.limit and len(records) >= self.config.limit:
                    break

        return records


@extractor_options(default_output="hillman_wonders.csv")
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
    """Extracts top wonders from Hillman Wonders of the World."""
    run_extractor_cli(
        extractor_cls=HillmanWondersExtractor,
        default_filename="hillman_wonders.csv",
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
