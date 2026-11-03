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

"""Extractor for international castles, palaces, and fortresses."""

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

CASTLES_BASE_URL = "https://www.castlesworld.com/selection/list.php"

COUNTRY_MAP = {
    "Germany": "DE",
    "United Kingdom": "GB",
    "Switzerland": "CH",
    "France": "FR",
    "Austria": "AT",
    "Italy": "IT",
    "Spain": "ES",
    "Czech Republic": "CZ",
    "Poland": "PL",
    "Portugal": "PT",
    "Ireland": "IE",
    "Japan": "JP",
}


class CastlesExtractor(BaseExtractor):
    """Scrapes international castles and fortresses with Fortification baseline tag."""

    name = "Castles"
    default_tags: list[str] = ["Fortification"]

    def _parse_card(self, card: Tag) -> ExtractorRecord | None:
        """Parses a castle DOM card into an ExtractorRecord.

        Args:
            card: BeautifulSoup element containing castle metadata.

        Returns:
            ExtractorRecord or None if invalid.
        """
        title_elem = card.find("h3") or card.find("h2") or card.select_one(".castle-title")
        if not title_elem:
            return None

        link_elem = title_elem.find("a") if isinstance(title_elem, Tag) else None
        poi_name = title_elem.get_text(strip=True)
        if not poi_name:
            return None

        href = ""
        if link_elem and isinstance(link_elem, Tag):
            href = str(link_elem.get("href", ""))
        detail_url = urljoin(CASTLES_BASE_URL, href) if href else ""

        country_elem = card.select_one(".country")
        country_name = country_elem.get_text(strip=True) if country_elem else "Unknown"
        country_code = COUNTRY_MAP.get(country_name, "")

        region_elem = card.select_one(".region")
        region = region_elem.get_text(strip=True) if region_elem else None

        town_elem = card.select_one(".town") or card.select_one(".city")
        town = town_elem.get_text(strip=True) if town_elem else None

        # Coordinates
        lat, lon = None, None
        coords_elem = card.select_one(".coords") or card.select_one(".coordinates")
        if coords_elem and isinstance(coords_elem, Tag):
            dlat = coords_elem.get("data-lat")
            dlon = coords_elem.get("data-lon")
            if dlat and dlon:
                try:
                    lat = float(str(dlat))
                    lon = float(str(dlon))
                except ValueError:
                    pass

        # Hero image
        hero_img = None
        img_elem = card.select_one(".card-img") or card.find("img")
        if img_elem and isinstance(img_elem, Tag) and img_elem.get("src"):
            hero_img = urljoin(CASTLES_BASE_URL, str(img_elem.get("src")))

        # Websites: only populate unique POI URLs, omit directory list URL
        websites: list[WebsiteRecord] = []
        if href and detail_url != CASTLES_BASE_URL:
            websites.append(WebsiteRecord(name="Castles World", url=detail_url))

        # Tag resolution: baseline Fortification ONLY (no architectural classifications)
        tags = self.resolve_tags([])

        return ExtractorRecord(
            poi_name=poi_name,
            town_city=town,
            state_province=region,
            country=country_name,
            country_code=country_code,
            latitude=lat,
            longitude=lon,
            tags=tags,
            websites=websites,
            hero_image_url=hero_img,
        )

    def harvest_records(self) -> list[ExtractorRecord]:
        """Harvests castles from directory.

        Returns:
            List of parsed ExtractorRecord items.
        """
        html = self.http.get(CASTLES_BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".castle-card")
        if not cards:
            cards = soup.find_all(class_=re.compile(r"castle-card|castle-item"))

        records: list[ExtractorRecord] = []
        for card in cards:
            if not isinstance(card, Tag):
                continue
            rec = self._parse_card(card)
            if rec:
                records.append(rec)
                if self.config.limit and len(records) >= self.config.limit:
                    break

        return records


@extractor_options(default_output="castles.csv")
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
    """Extracts international castles and fortresses."""
    run_extractor_cli(
        extractor_cls=CastlesExtractor,
        default_filename="castles.csv",
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
