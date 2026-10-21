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
Museum Ships Worldwide Extractor & Geocoder.

Extracts museum ships, historic vessels, and submarines on public display
from around the world using Wikipedia's curated global registries
(List of museum ships, List of museum ships in North America, List of submarines on display)
and enriches coordinates with OpenStreetMap Nominatim and local geocaching.

Outputs a standardized CSV ready for Vistarae Bulk Import.
"""

import argparse
import html
import logging
from pathlib import Path
import re
import sys
from typing import Any
import requests

from common import (
    NominatimGeocache,
    clean_country_names,
    clean_wiki_markup,
    deduplicate_tags,
    parse_coord_template,
    to_english_name,
    write_standard_csv,
)

logger = logging.getLogger("vistarae.museum_ships")

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "museum_ships.csv"
CACHE_FILE = Path(__file__).resolve().parent / ".museum_ships_geocache.json"

WIKI_SOURCES = [
    {
        "title": "List_of_museum_ships",
        "default_category": "Museum Ship",
        "description": "Global list of museum ships and historic surface vessels",
    },
    {
        "title": "List_of_museum_ships_in_North_America",
        "default_category": "Museum Ship",
        "description": "Museum ships and historic vessels in North America",
    },
    {
        "title": "List_of_museum_ships_of_the_United_States_military",
        "default_category": "Museum Ship",
        "description": "Preserved museum ships of the United States military",
    },
    {
        "title": "List_of_submarines_on_display",
        "default_category": "Museum Submarine",
        "description": "Preserved submarines and submersibles on display worldwide",
    },
]

# Specific ship type classifications for tagging
NAVAL_WARSHIP_TERMS = {
    "battleship",
    "aircraft carrier",
    "cruiser",
    "destroyer",
    "frigate",
    "corvette",
    "submarine",
    "patrol boat",
    "patrol vessel",
    "torpedo boat",
    "gunboat",
    "minesweeper",
    "minelayer",
    "sloop-of-war",
    "ship of the line",
    "ironclad",
    "monitor",
    "dreadnought",
    "cutter",
    "landing craft",
    "naval",
    "warship",
}

MARITIME_VESSEL_TERMS = {
    "tall ship",
    "schooner",
    "clipper",
    "barque",
    "bark",
    "brig",
    "sloop",
    "steamship",
    "steamboat",
    "paddle steamer",
    "tugboat",
    "tug",
    "lightship",
    "lightvessel",
    "ferry",
    "icebreaker",
    "ocean liner",
    "cargo ship",
    "freighter",
    "trawler",
    "whaler",
    "yacht",
}


def parse_wikitable_rows(table_text: str) -> tuple[list[str], list[list[str]]]:
    """Extracts lowercase header names and cell arrays from a MediaWiki table text."""
    body = re.sub(r"^\{\|[^\n]*\n", "", table_text)
    body = re.sub(r"\n\|\}$", "", body)
    raw_rows = re.split(r"\n\|-+[^\n]*\n", "\n" + body + "\n")
    headers: list[str] = []
    data_rows: list[list[str]] = []

    for r in raw_rows:
        r = r.strip()
        if not r:
            continue
        lines = r.split("\n")
        cells: list[str] = []
        is_header = False

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("!"):
                is_header = True
                content = line_str[1:].strip()
                subcells = re.split(r"!!|\|\|", content)
                for sc in subcells:
                    cells.append(sc.strip())
            elif line_str.startswith("|"):
                content = line_str[1:].strip()
                subcells = re.split(r"\|\|", content)
                for sc in subcells:
                    cells.append(sc.strip())
            else:
                if cells:
                    cells[-1] += " " + line_str

        if not cells:
            continue
        if is_header and not headers:
            headers = [clean_wiki_markup(c).lower() for c in cells]
        elif not is_header:
            data_rows.append(cells)

    return headers, data_rows


def extract_ships_from_wikitext(wikitext: str, default_cat: str) -> list[dict[str, Any]]:
    """Parses a Wikipedia list article, capturing continent, country/state, headers, and rows."""
    lines = wikitext.split("\n")
    current_continent = ""
    current_country = ""
    table_buffer: list[str] = []
    in_table = False
    extracted: list[dict[str, Any]] = []

    for line in lines:
        ls = line.strip()
        if ls.startswith("==") and not ls.startswith("==="):
            h = ls.strip("= ").strip()
            if h not in ("See also", "References", "External links", "Notes", "Bibliography", "Sources"):
                current_continent = h
                current_country = ""
        elif ls.startswith("===") and not ls.startswith("===="):
            current_country = ls.strip("= ").strip()
        elif ls.startswith("{|"):
            in_table = True
            table_buffer = [line]
        elif ls.startswith("|}"):
            in_table = False
            table_buffer.append(line)
            table_text = "\n".join(table_buffer)
            headers, rows = parse_wikitable_rows(table_text)

            col_name = next((i for i, h in enumerate(headers) if "ship" in h or "name" in h or "boat" in h), 0)
            col_type = next((i for i, h in enumerate(headers) if "type" in h or "class" in h), None)
            col_loc = next((i for i, h in enumerate(headers) if "location" in h or "place" in h or "city" in h), None)
            col_coords = next((i for i, h in enumerate(headers) if "coord" in h), None)
            col_notes = next((i for i, h in enumerate(headers) if "note" in h or "remark" in h or "history" in h), None)
            col_year = next((i for i, h in enumerate(headers) if "year" in h or "launch" in h), None)
            col_origin = next((i for i, h in enumerate(headers) if "origin" in h or "national" in h), None)

            for r in rows:
                raw_name = r[col_name] if col_name < len(r) else ""
                raw_type = r[col_type] if col_type is not None and col_type < len(r) else ""
                raw_loc = r[col_loc] if col_loc is not None and col_loc < len(r) else ""
                raw_coords = r[col_coords] if col_coords is not None and col_coords < len(r) else ""
                raw_notes = r[col_notes] if col_notes is not None and col_notes < len(r) else ""
                raw_year = r[col_year] if col_year is not None and col_year < len(r) else ""
                raw_origin = r[col_origin] if col_origin is not None and col_origin < len(r) else ""
                full_raw = " ".join(r)

                # Parse coordinates from coordinates column, location cell, or row
                lat, lon = (None, None)
                if raw_coords:
                    lat, lon = parse_coord_template(raw_coords)
                if not lat and raw_loc:
                    lat, lon = parse_coord_template(raw_loc)
                if not lat:
                    lat, lon = parse_coord_template(full_raw)

                # Clean cell-level attributes before parsing name
                cleaned_name_cell = re.sub(r'data-sort-value=(?:"[^"]*"|\'[^\']*\'|[^\s|]+)\s*\|', "", raw_name)
                # If there is a wikilink [[Target|Display]] or [[Target]]
                m_wikilink = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", cleaned_name_cell)
                if m_wikilink:
                    name = to_english_name(clean_wiki_markup(m_wikilink.group(1)))
                else:
                    name = to_english_name(clean_wiki_markup(cleaned_name_cell))

                # Strip any leftover sorting key or pipes e.g. "More|J.R. More" -> "J.R. More"
                if "|" in name:
                    name = name.split("|")[-1].strip()

                if not name or name.lower() in ("ship", "name", "vessel", "image"):
                    continue

                type_str = to_english_name(clean_wiki_markup(raw_type))
                loc_str = to_english_name(clean_wiki_markup(raw_loc))
                notes_str = to_english_name(clean_wiki_markup(raw_notes))
                year_str = clean_wiki_markup(raw_year).strip()
                origin_str = to_english_name(clean_wiki_markup(raw_origin))

                # Extract Wikipedia article title if linked via [[Article]] or {{USS|...}} / {{HMS|...}}
                wiki_article = ""
                m_link = re.search(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", raw_name)
                if m_link:
                    wiki_article = m_link.group(1).strip()
                else:
                    m_tmpl = re.search(r"\{\{(uss|hms|usns|uscgc|uscg|hmcs|hmas|hmnzs|ara|bap|ins|js|kd|its)\|([^}]+)\}\}", raw_name, re.IGNORECASE)
                    if m_tmpl:
                        t_prefix = m_tmpl.group(1).upper()
                        t_parts = [p.strip() for p in m_tmpl.group(2).split("|") if p.strip()]
                        if t_parts:
                            t_name = t_parts[0]
                            t_hull = t_parts[1] if len(t_parts) > 1 and not t_parts[1].isdigit() else ""
                            if t_hull:
                                wiki_article = f"{t_prefix} {t_name} ({t_hull})"
                            else:
                                wiki_article = f"{t_prefix} {t_name}"

                extracted.append(
                    {
                        "name": name,
                        "type": type_str,
                        "location": loc_str,
                        "notes": notes_str,
                        "year": year_str,
                        "origin": origin_str,
                        "country_context": current_country,
                        "continent_context": current_continent,
                        "lat": lat,
                        "lon": lon,
                        "wiki_article": wiki_article,
                        "default_category": default_cat,
                    }
                )

            table_buffer = []
        elif in_table:
            table_buffer.append(line)

    return extracted


def generate_ship_tags(ship: dict[str, Any]) -> str:
    """Generates standard, categorized comma-separated tags for a museum ship."""
    tags: list[str] = ["Museum", "Museum Ship", "Maritime", "Historic"]

    ship_type = (ship.get("type") or "").lower()
    name = (ship.get("name") or "").lower()
    notes = (ship.get("notes") or "").lower()
    corpus = f"{name} {ship_type} {notes}"

    # Submarine distinction
    if "submarine" in corpus or "submersible" in corpus or ship.get("default_category") == "Museum Submarine":
        tags.append("Submarine")

    # Naval & Military distinction
    is_naval = any(term in corpus for term in NAVAL_WARSHIP_TERMS)
    if is_naval:
        tags.extend(["Military", "Naval"])

    # Specific ship types
    if "battleship" in corpus:
        tags.append("Battleship")
    elif "aircraft carrier" in corpus or "carrier" in corpus:
        tags.append("Aircraft Carrier")
    elif "cruiser" in corpus:
        tags.append("Cruiser")
    elif "destroyer" in corpus:
        tags.append("Destroyer")
    elif "frigate" in corpus:
        tags.append("Frigate")
    elif "corvette" in corpus:
        tags.append("Corvette")
    elif "tall ship" in corpus or "schooner" in corpus or "clipper" in corpus or "barque" in corpus or "brig" in corpus:
        tags.append("Sailing Ship")
    elif "steamer" in corpus or "steamship" in corpus or "steamboat" in corpus:
        tags.append("Steamship")
    elif "tug" in corpus or "tugboat" in corpus:
        tags.append("Tugboat")
    elif "lightship" in corpus or "lightvessel" in corpus:
        tags.append("Lightship")
    elif "icebreaker" in corpus:
        tags.append("Icebreaker")
    elif "liner" in corpus or "passenger" in corpus:
        tags.append("Ocean Liner")

    # Conflict tags
    if "world war ii" in corpus or "wwii" in corpus or "second world war" in corpus:
        tags.append("World War II")
    elif "world war i" in corpus or "wwi" in corpus or "first world war" in corpus:
        tags.append("World War I")
    elif "cold war" in corpus:
        tags.append("Cold War")
    elif "civil war" in corpus:
        tags.append("Civil War")

    return deduplicate_tags(tags)


def determine_category(ship: dict[str, Any]) -> str:
    """Categorizes the POI as Museum Ship, Museum Submarine, or Maritime Museum."""
    ship_type = (ship.get("type") or "").lower()
    corpus = f"{ship.get('name', '').lower()} {ship_type}"
    if "submarine" in corpus or "submersible" in corpus or ship.get("default_category") == "Museum Submarine":
        return "Museum Submarine"
    return "Museum Ship"


US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
    "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming", "District of Columbia", "Guam", "Puerto Rico", "Virgin Islands"
}


def parse_location_components(location_str: str, country_context: str) -> tuple[str, str, str, str]:
    """Heuristically extracts (street, city, state, country) from location string and section headers."""
    street, city, state, country = "", "", "", ""
    parts = [p.strip() for p in location_str.split(",") if p.strip()]

    clean_ctx = clean_country_names(country_context)
    if clean_ctx:
        country = clean_ctx

    # Check if context is actually a US state (e.g. from North America page sections)
    if country_context in US_STATES:
        state = country_context
        country = "United States"

    if len(parts) >= 3:
        city = parts[-2]
        candidate = parts[-1]
        if candidate in US_STATES:
            state = candidate
            country = "United States"
        elif not country:
            country = clean_country_names(candidate)
        else:
            state = candidate
    elif len(parts) == 2:
        city = parts[0]
        candidate = parts[1]
        if candidate in US_STATES:
            state = candidate
            country = "United States"
        elif not country:
            country = clean_country_names(candidate)
        else:
            state = candidate
    elif len(parts) == 1:
        city = parts[0]

    return street, to_english_name(city), to_english_name(state), country


def fetch_wikipedia_coordinates(wiki_titles: list[str]) -> dict[str, tuple[float, float]]:
    """Batch queries the MediaWiki API for page primary coordinates in chunks of 50.
    
    Returns a mapping of normalized title -> (latitude, longitude).
    """
    coords_map: dict[str, tuple[float, float]] = {}
    if not wiki_titles:
        return coords_map

    clean_titles = list(dict.fromkeys(t.replace(" ", "_") for t in wiki_titles if t))
    chunk_size = 50

    for i in range(0, len(clean_titles), chunk_size):
        chunk = clean_titles[i : i + chunk_size]
        titles_param = "|".join(chunk)
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "coordinates",
            "titles": titles_param,
            "format": "json",
            "colimit": "max",
        }
        headers = {"User-Agent": "VistaraeTravelEngine/1.0 (contact: admin@vistarae.local)"}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("query", {})
                norm_map = {n["to"]: n["from"] for n in data.get("normalized", [])}
                pages = data.get("pages", {})
                for pid, p in pages.items():
                    coords = p.get("coordinates")
                    if coords:
                        c = coords[0]
                        lat = round(float(c["lat"]), 6)
                        lon = round(float(c["lon"]), 6)
                        page_title = p.get("title", "")
                        coords_map[page_title] = (lat, lon)
                        coords_map[page_title.replace(" ", "_")] = (lat, lon)
                        orig = norm_map.get(page_title)
                        if orig:
                            coords_map[orig] = (lat, lon)
                            coords_map[orig.replace(" ", "_")] = (lat, lon)
        except Exception as exc:
            logger.warning(f"Failed batch Wikipedia coordinate fetch for chunk starting at {i}: {exc}")

    return coords_map


def extract_museum_ships(
    output_file: Path | str = DEFAULT_OUTPUT,
    enrich_addresses: bool = False,
    limit: int | None = None,
) -> None:
    """Orchestrates extraction of museum ships from Wikipedia, geocoding coordinates, and saving CSV."""
    output_path = Path(output_file)
    geocache = NominatimGeocache(CACHE_FILE)
    all_raw_ships: list[dict[str, Any]] = []

    print("Fetching museum ships lists from Wikipedia...")
    for src in WIKI_SOURCES:
        url = f"https://en.wikipedia.org/w/index.php?title={src['title']}&action=raw"
        print(f"  Fetching '{src['title']}'...")
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "VistaraeTravelEngine/1.0 (contact: admin@vistarae.local)"},
                timeout=30,
            )
            resp.raise_for_status()
            ships = extract_ships_from_wikitext(resp.text, src["default_category"])
            print(f"  Parsed {len(ships)} ship records from '{src['title']}'.")
            all_raw_ships.extend(ships)
        except Exception as exc:
            print(f"  Warning: Failed to fetch '{src['title']}': {exc}", file=sys.stderr)

    # Deduplicate ships across multiple articles by normalized name and country
    seen_ships: dict[str, dict[str, Any]] = {}
    for s in all_raw_ships:
        name_key = re.sub(r"[^\w]", "", s["name"].lower())
        if not name_key:
            continue
        existing = seen_ships.get(name_key)
        if not existing:
            seen_ships[name_key] = s
        else:
            # Merge information: prefer record with coordinates or longer notes
            if existing["lat"] is None and s["lat"] is not None:
                existing["lat"] = s["lat"]
                existing["lon"] = s["lon"]
            if not existing.get("type") and s.get("type"):
                existing["type"] = s["type"]
            if not existing.get("location") and s.get("location"):
                existing["location"] = s["location"]
            if len(s.get("notes", "")) > len(existing.get("notes", "")):
                existing["notes"] = s["notes"]
            if not existing.get("wiki_article") and s.get("wiki_article"):
                existing["wiki_article"] = s["wiki_article"]

    unique_ships = list(seen_ships.values())
    print(f"\nTotal unique museum ships identified: {len(unique_ships)}")

    # Enrich missing coordinates directly from Wikipedia page coordinates API
    missing_coord_articles = [
        s["wiki_article"]
        for s in unique_ships
        if s["lat"] is None and s.get("wiki_article")
    ]
    if missing_coord_articles:
        print(f"Batch querying Wikipedia page coordinates for {len(missing_coord_articles)} ships lacking coordinates...")
        wiki_coords = fetch_wikipedia_coordinates(missing_coord_articles)
        resolved_count = 0
        for s in unique_ships:
            if s["lat"] is None and s.get("wiki_article"):
                art = s["wiki_article"]
                if art in wiki_coords or art.replace(" ", "_") in wiki_coords:
                    lat, lon = wiki_coords.get(art) or wiki_coords.get(art.replace(" ", "_"))
                    s["lat"] = lat
                    s["lon"] = lon
                    resolved_count += 1
        print(f"Successfully resolved {resolved_count} additional vessel coordinates from Wikipedia page geocodes!")

    if limit and limit > 0:
        unique_ships = unique_ships[:limit]
        print(f"Limiting processing to first {len(unique_ships)} ships.")

    records: list[dict[str, str]] = []
    with_coords_count = 0
    geocoded_count = 0

    print("\nProcessing records, geocoding and normalizing addresses...")
    for idx, s in enumerate(unique_ships, 1):
        name = s["name"]
        lat = s["lat"]
        lon = s["lon"]
        loc_str = s.get("location", "")
        country_ctx = s.get("country_context", "")

        street, city, state, country = parse_location_components(loc_str, country_ctx)

        # 1. Reverse geocode if coordinates present and address incomplete
        if lat is not None and lon is not None:
            with_coords_count += 1
            if enrich_addresses:
                rev_street, rev_city, rev_state, rev_country = geocache.reverse_geocode(lat, lon)
                if rev_street:
                    street = to_english_name(rev_street)
                if rev_city:
                    city = to_english_name(rev_city)
                if rev_state:
                    state = to_english_name(rev_state)
                if rev_country:
                    country = clean_country_names(rev_country)

        # 2. Forward geocode if coordinates missing but name and location known
        elif enrich_addresses and (loc_str or country):
            search_query = f"{name}, {loc_str}".strip(", ")
            f_lat, f_lon, f_street, f_city, f_state, f_country = geocache.forward_geocode(search_query)
            if f_lat is not None and f_lon is not None:
                lat = f_lat
                lon = f_lon
                with_coords_count += 1
                geocoded_count += 1
                if f_street:
                    street = to_english_name(f_street)
                if f_city:
                    city = to_english_name(f_city)
                if f_state:
                    state = to_english_name(f_state)
                if f_country:
                    country = clean_country_names(f_country)

        lat_str = f"{lat:.6f}" if lat is not None else ""
        lon_str = f"{lon:.6f}" if lon is not None else ""

        category = determine_category(s)
        tags_str = generate_ship_tags(s)

        # Generate website: Official Wikipedia article URL
        website = ""
        if s.get("wiki_article"):
            wiki_slug = s["wiki_article"].replace(" ", "_")
            website = f"https://en.wikipedia.org/wiki/{wiki_slug}"

        # Construct comprehensive description
        desc_parts = []
        if s.get("type"):
            desc_parts.append(f"Type: {s['type']}.")
        if s.get("year"):
            desc_parts.append(f"Launched: {s['year']}.")
        if s.get("origin"):
            desc_parts.append(f"Origin: {s['origin']}.")
        if s.get("location"):
            desc_parts.append(f"Preserved at: {s['location']}.")
        if s.get("notes"):
            desc_parts.append(s["notes"])

        description = " ".join(desc_parts).strip()

        records.append(
            {
                "title": name,
                "latitude": lat_str,
                "longitude": lon_str,
                "street address": street,
                "city": city,
                "state": state,
                "country": country,
                "category": category,
                "Tags": tags_str,
                "website": website,
                "description": description,
            }
        )

        if idx % 25 == 0:
            geocache.save()

        if idx % 100 == 0 or idx == len(unique_ships):
            print(f"Processed {idx}/{len(unique_ships)} ships ({with_coords_count} with valid coordinates)...")

    geocache.save()

    # Sort records alphabetically by title
    records.sort(key=lambda r: r["title"])

    saved = write_standard_csv(output_path, records)
    print(f"\nExtraction complete! Output saved to: {saved}")
    print(f"  Total museum ships written: {len(records)}")
    print(f"  Sites with coordinates: {with_coords_count} ({with_coords_count / len(records) * 100:.1f}%)")
    if geocoded_count > 0:
        print(f"  Sites geocoded via OpenStreetMap Nominatim: {geocoded_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract museum ships and historic vessels from around the world for Vistarae Bulk Import."
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Path to output CSV file (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        default=False,
        help="Perform bi-directional OpenStreetMap Nominatim geocoding (~1 req/sec with cache).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of ships to process (useful for quick testing).",
    )

    args = parser.parse_args()
    extract_museum_ships(
        output_file=args.output,
        enrich_addresses=args.enrich,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
