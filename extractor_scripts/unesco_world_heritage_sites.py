#!/usr/bin/env python3

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

"""
UNESCO World Heritage Sites Extractor & Coordinate Geocoder.
Fetches the official UNESCO World Heritage XML dataset, extracts verified
latitude and longitude coordinates from geolocation POIs, and outputs an
enriched CSV ready for Vistarae Bulk Import.
"""

import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import requests

from common import (
    NominatimGeocache,
    clean_country_names,
    clean_html,
    deduplicate_tags,
    to_english_name,
    write_standard_csv,
)

# Official direct XML feed of all UNESCO World Heritage Sites
FEED_URL = "https://whc.unesco.org/en/list/xml/"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "unesco_sites_enriched.csv"
CACHE_FILE = Path(__file__).resolve().parent / ".unesco_geocache.json"

# Known coordinates for the 3 serial/transnational properties that lack <poi> entries in the XML feed
KNOWN_COORDINATES: dict[str, tuple[float, float]] = {
    # 1567: Funerary and memory sites of the First World War (Western Front) - Thiepval Memorial
    "1567": (50.005800, 2.685300),
    # 72: Kluane / Wrangell-St. Elias / Glacier Bay / Tatshenshini-Alsek - Park Centroid
    "72": (60.666700, -138.500000),
    # 868: Routes of Santiago de Compostela in France - Saint-André Cathedral, Bordeaux
    "868": (44.837800, -0.579200),
}


def extract_location_hint(location_text: str | None) -> tuple[str, str]:
    """Extracts rudimentary city/state hints from UNESCO's location tag if present."""
    if not location_text:
        return "", ""

    text = location_text.strip()
    m_city = re.match(r"^([\w\s'-]+)\s*\((?:municipality|city|town)\)", text, re.I)
    if m_city:
        return m_city.group(1).strip(), ""

    m_state = re.search(r"(?:State|Province|Region|Department|County|Canton) of\s+([\w\s'-]+)", text, re.I)
    if m_state:
        state_candidate = m_state.group(1).split(",")[0].strip()
        return "", state_candidate

    return "", ""


def extract_unesco_sites(
    enrich_addresses: bool = False,
    limit: int | None = None,
    output_file: Path | str = DEFAULT_OUTPUT,
) -> None:
    """Fetches UNESCO XML, extracts exact POI coordinates, and writes enriched CSV."""
    output_path = Path(output_file)
    print(f"Fetching official UNESCO dataset from {FEED_URL}...")
    resp = requests.get(FEED_URL, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    rows = root.findall(".//row")
    total_rows = len(rows)
    print(f"Total sites loaded from UNESCO XML feed: {total_rows}")

    if limit and limit > 0:
        rows = rows[:limit]
        print(f"Processing limited subset: {len(rows)} sites")

    geocache = NominatimGeocache(CACHE_FILE) if enrich_addresses else None
    processed_count = 0
    with_coords_count = 0
    records: list[dict[str, str]] = []

    for idx, row in enumerate(rows, 1):
        site_id = (row.findtext("id_number") or "").strip()
        title = to_english_name(row.findtext("site") or "")
        category = (row.findtext("category") or "").strip()
        website = (row.findtext("http_url") or "").strip()
        country = clean_country_names(row.findtext("states") or "")
        description = clean_html(row.findtext("short_description") or "")
        location_text = (row.findtext("location") or "").strip()

        # Construct Tags: "UNESCO", "world heritage", category, etc.
        tags_list = ["UNESCO", "world heritage"]
        cat_lower = category.lower()
        if "natural" in cat_lower:
            tags_list.extend(["natural", "nature"])
        elif "cultural" in cat_lower:
            tags_list.extend(["cultural", "historic"])
        elif "mixed" in cat_lower:
            tags_list.extend(["mixed", "nature", "cultural"])
        elif category:
            tags_list.append(category)

        if (row.findtext("transnational") or "0").strip() == "1":
            tags_list.append("transnational")

        tags_str = deduplicate_tags(tags_list)

        # 1. Extract latitude & longitude from <geolocations><poi>
        geo = row.find("geolocations")
        pois = geo.findall("poi") if geo is not None else []

        f_lat: float | None = None
        f_lon: float | None = None

        if pois:
            try:
                f_lat = float(pois[0].findtext("latitude", "").strip())
                f_lon = float(pois[0].findtext("longitude", "").strip())
            except (ValueError, TypeError):
                f_lat = None
                f_lon = None
        elif site_id in KNOWN_COORDINATES:
            f_lat, f_lon = KNOWN_COORDINATES[site_id]

        lat_str = f"{f_lat:.6f}" if f_lat is not None else ""
        lon_str = f"{f_lon:.6f}" if f_lon is not None else ""

        if lat_str and lon_str:
            with_coords_count += 1

        # 2. Extract address components (via location hint or Nominatim reverse geocode)
        city_hint, state_hint = extract_location_hint(location_text)
        street_address = ""
        city = to_english_name(city_hint)
        state = to_english_name(state_hint)

        if enrich_addresses and geocache and f_lat is not None and f_lon is not None:
            rev_street, rev_city, rev_state, rev_country = geocache.reverse_geocode(f_lat, f_lon)
            street_address = to_english_name(rev_street)
            if rev_city:
                city = to_english_name(rev_city)
            if rev_state:
                state = to_english_name(rev_state)
            if not country and rev_country:
                country = clean_country_names(rev_country)

            if idx % 25 == 0:
                geocache.save()

        records.append(
            {
                "title": title,
                "latitude": lat_str,
                "longitude": lon_str,
                "street address": street_address,
                "city": city,
                "state": state,
                "country": country,
                "category": category,
                "Tags": tags_str,
                "website": website,
                "description": description,
            }
        )
        processed_count += 1

        if idx % 100 == 0 or idx == len(rows):
            print(f"Processed {idx}/{len(rows)} records ({with_coords_count} with valid coordinates)...")

    if enrich_addresses and geocache:
        geocache.save()

    saved_path = write_standard_csv(output_path, records)

    print(f"\nExtraction complete! Output saved to: {saved_path}")
    print(f"  Total records written: {processed_count}")
    print(f"  Sites with coordinates: {with_coords_count} ({with_coords_count / processed_count * 100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract UNESCO World Heritage Sites with verified coordinates for Vistarae."
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        default=False,
        help="Reverse geocode coordinates using OpenStreetMap Nominatim (slower, ~1 req/sec).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of sites to extract (useful for testing).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Path to output CSV file (default: {DEFAULT_OUTPUT}).",
    )

    args = parser.parse_args()
    extract_unesco_sites(
        enrich_addresses=args.enrich,
        limit=args.limit,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()