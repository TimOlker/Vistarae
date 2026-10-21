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

"""Common utilities, geocoding helpers, text normalization, and CSV writing for Vistarae extractors."""

import csv
import html
import json
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Sequence
import requests

logger = logging.getLogger("vistarae.extractor_common")

# Standard Nominatim rate limit: max 1 request per second with distinct User-Agent
NOMINATIM_HEADERS = {"User-Agent": "VistaraeTravelEngine/1.0 (contact: admin@vistarae.local)"}
DEFAULT_NOMINATIM_DELAY = 1.1

# Standard columns supported by Vistarae Bulk Import parser
STANDARD_CSV_COLUMNS: list[str] = [
    "title",
    "latitude",
    "longitude",
    "street address",
    "city",
    "state",
    "country",
    "category",
    "Tags",
    "website",
    "description",
]

# Non-decomposing Latin characters and typography to clean English equivalents
SPECIAL_CHAR_MAP: dict[str, str] = {
    "ł": "l", "Ł": "L",
    "ø": "o", "Ø": "O",
    "ß": "ss", "ẞ": "SS",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "TH",
    "đ": "d", "Đ": "D",
    "ı": "i", "İ": "I",
    "Ħ": "H", "ħ": "h",
    "ǂ": "",
    "’": "'", "‘": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "-",
    "…": "...",
}

COUNTRY_NAME_OVERRIDES: dict[str, str] = {
    "Bolivia (Plurinational State of)": "Bolivia",
    "Cabo Verde": "Cape Verde",
    "Czechia": "Czech Republic",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Democratic People's Republic of Korea": "North Korea",
    "Holy See": "Vatican City",
    "Iran (Islamic Republic of)": "Iran",
    "Jerusalem (Site proposed by Jordan)": "Jerusalem",
    "Lao People's Democratic Republic": "Laos",
    "Micronesia (Federated States of)": "Micronesia",
    "Netherlands (Kingdom of the)": "Netherlands",
    "Republic of Korea": "South Korea",
    "Republic of Moldova": "Moldova",
    "Russian Federation": "Russia",
    "State of Palestine": "Palestine",
    "Syrian Arab Republic": "Syria",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    "United Republic of Tanzania": "Tanzania",
    "United States of America": "United States",
    "Venezuela (Bolivarian Republic of)": "Venezuela",
    "Viet Nam": "Vietnam",
}


def fix_mojibake(text: str | None) -> str:
    """Repairs common UTF-8 byte sequences incorrectly decoded as Windows-1252 or ISO-8859-1."""
    if not text:
        return ""
    if any(m in text for m in ("Ã", "Â", "Ä", "Å", "â", "Ÿ")):
        for enc in ("windows-1252", "iso-8859-1"):
            try:
                candidate = text.encode(enc).decode("utf-8")
                if not any(m in candidate for m in ("Ã", "Â", "Ä", "Å")):
                    return candidate
            except Exception:
                pass
    return text


def to_english_name(text: str | None) -> str:
    """Transforms names with accents, diacritics, and corrupted characters into clean English ASCII equivalents."""
    if not text:
        return ""
    text = fix_mojibake(text)
    text = "".join(SPECIAL_CHAR_MAP.get(c, c) for c in text)
    nfkd = unicodedata.normalize("NFKD", text)
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(clean.split()).strip()


def clean_country_names(states_text: str | None) -> str:
    """Normalizes comma-separated country lists to clean standard English names."""
    if not states_text:
        return ""
    fixed = fix_mojibake(states_text)
    parts = [p.strip() for p in fixed.split(",") if p.strip()]
    cleaned = []
    for p in parts:
        eng = COUNTRY_NAME_OVERRIDES.get(p)
        if not eng:
            p_eng = to_english_name(p)
            eng = COUNTRY_NAME_OVERRIDES.get(p_eng, p_eng)
        cleaned.append(eng)
    return ", ".join(cleaned)


def clean_html(text: str | None) -> str:
    """Strips HTML markup, fixes mojibake, and unescapes entities."""
    if not text:
        return ""
    clean = fix_mojibake(text)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = html.unescape(clean)
    return " ".join(clean.split()).strip()


def clean_wiki_markup(text: str | None) -> str:
    """Strips Wikipedia wikitext formatting, citations, template tags, and interwiki links."""
    if not text:
        return ""
    t = fix_mojibake(text)
    # Remove references <ref...>...</ref> and <ref.../>
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<ref[^>]*/>", "", t, flags=re.IGNORECASE)
    # Extract dts template year
    t = re.sub(r"\{\{dts\|([^}|]+).*?\}\}", r"\1", t, flags=re.IGNORECASE)
    # Remove coord templates
    t = re.sub(r"\{\{[Cc]oord\|.*?\}\}", "", t, flags=re.IGNORECASE)

    # Convert navy ship prefix templates: {{USS|Olympia|C-6|6}}, {{HMS|Victory}}, {{HMCS|Haida|G63}}, etc.
    prefix_map = {
        "uss": "USS", "hms": "HMS", "usns": "USNS", "uscgc": "USCGC", "uscg": "USCGC",
        "hmcs": "HMCS", "hmas": "HMAS", "hmnzs": "HMNZS", "ara": "ARA", "bap": "BAP",
        "ins": "INS", "js": "JS", "kd": "KD", "its": "ITS", "nr": "NR", "ss": "SS", "rv": "R/V",
    }
    def _repl_prefixed(m):
        tmpl = m.group(1).lower()
        parts = [p.strip() for p in m.group(2).split("|") if p.strip()]
        if not parts:
            return ""
        name = parts[0]
        prefix = prefix_map.get(tmpl, tmpl.upper())
        hull = parts[1] if len(parts) > 1 and not parts[1].isdigit() else ""
        if hull:
            return f"{prefix} {name} ({hull})"
        return f"{prefix} {name}"

    t = re.sub(
        r"\{\{(uss|hms|usns|uscgc|uscg|hmcs|hmas|hmnzs|ara|bap|ins|js|kd|its|nr|ss|rv)\|([^}]+)\}\}",
        _repl_prefixed,
        t,
        flags=re.IGNORECASE,
    )

    # Convert generic {{ship|prefix|name|id}} template
    def _repl_ship(m):
        parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
        if len(parts) >= 2:
            prefix, name = parts[0], parts[1]
            hull = parts[2] if len(parts) > 2 and not parts[2].isdigit() else ""
            if hull:
                return f"{prefix} {name} ({hull})"
            return f"{prefix} {name}"
        elif parts:
            return parts[0]
        return ""

    t = re.sub(r"\{\{ship\|([^}]+)\}\}", _repl_ship, t, flags=re.IGNORECASE)

    # Convert {{sclass|Name|type|...}} -> Name-class type
    def _repl_sclass(m):
        parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[0]}-class {parts[1]}"
        elif parts:
            return f"{parts[0]}-class"
        return ""

    t = re.sub(r"\{\{sclass\d?\|([^}]+)\}\}", _repl_sclass, t, flags=re.IGNORECASE)

    # Remove other formatting/metadata templates like {{small|...}}, {{flagicon|...}}, etc.
    t = re.sub(r"\{\{[^}]+\}\}", " ", t)
    # Convert [[Target|Label]] -> Label and [[Target]] -> Target
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", t)
    # Remove HTML tags
    t = re.sub(r"<[^>]+>", " ", t)
    # Remove table styling or sort attributes (e.g. data-sort-value="foo" | or data-sort-value=foo|)
    t = re.sub(r'data-sort-value=(?:"[^"]*"|\'[^\']*\'|[^\s|]+)\s*\|?', "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\|+", "", t.strip())
    t = t.replace("'''", "").replace("''", "")
    t = html.unescape(t)
    return " ".join(t.split()).strip()


def parse_coord_template(text: str | None) -> tuple[float | None, float | None]:
    """Parses Wikipedia {{coord|...}} template into decimal (latitude, longitude).
    
    Handles:
    - {{coord|29.99370|31.11968}}
    - {{coord|38|53|N|77|00|W}}
    - {{coord|38|53|38|N|77|00|43|W}}
    """
    if not text:
        return None, None
    m = re.search(r"\{\{[Cc]oord\|([^}]+)\}\}", text)
    if not m:
        return None, None
    raw_parts = [p.strip() for p in m.group(1).split("|") if p.strip() and "=" not in p]
    if not raw_parts:
        return None, None

    # Filter out formatting parameters
    parts = [p for p in raw_parts if not any(p.startswith(x) for x in ("display", "name", "title", "globe"))]

    # Format 1: {{coord|lat|lon}}
    if len(parts) == 2:
        try:
            return round(float(parts[0]), 6), round(float(parts[1]), 6)
        except ValueError:
            pass

    # Format 2: {{coord|lat|N/S|lon|E/W}}
    if len(parts) == 4 and parts[1].upper() in ("N", "S") and parts[3].upper() in ("E", "W"):
        try:
            lat = float(parts[0]) * (-1 if parts[1].upper() == "S" else 1)
            lon = float(parts[2]) * (-1 if parts[3].upper() == "W" else 1)
            return round(lat, 6), round(lon, 6)
        except ValueError:
            pass

    # Format 3: {{coord|deg|min|N/S|deg|min|E/W}}
    if len(parts) == 6 and parts[2].upper() in ("N", "S") and parts[5].upper() in ("E", "W"):
        try:
            lat = (float(parts[0]) + float(parts[1]) / 60.0) * (-1 if parts[2].upper() == "S" else 1)
            lon = (float(parts[3]) + float(parts[4]) / 60.0) * (-1 if parts[5].upper() == "W" else 1)
            return round(lat, 6), round(lon, 6)
        except ValueError:
            pass

    # Format 4: {{coord|deg|min|sec|N/S|deg|min|sec|E/W}}
    if len(parts) >= 8 and parts[3].upper() in ("N", "S") and parts[7].upper() in ("E", "W"):
        try:
            lat = (float(parts[0]) + float(parts[1]) / 60.0 + float(parts[2]) / 3600.0) * (-1 if parts[3].upper() == "S" else 1)
            lon = (float(parts[4]) + float(parts[5]) / 60.0 + float(parts[6]) / 3600.0) * (-1 if parts[7].upper() == "W" else 1)
            return round(lat, 6), round(lon, 6)
        except ValueError:
            pass

    return None, None


def deduplicate_tags(tags: Sequence[str]) -> str:
    """Takes a list of tags, deduplicates them case-insensitively while preserving original order and capitalization."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for t in tags:
        if not t:
            continue
        t_clean = t.strip()
        tl = t_clean.lower()
        if t_clean and tl not in seen:
            seen.add(tl)
            cleaned.append(t_clean)
    return ", ".join(cleaned)


class NominatimGeocache:
    """Persistent JSON disk cache for OpenStreetMap Nominatim reverse and forward geocoding."""

    def __init__(self, cache_file: Path | str):
        self.cache_file = Path(cache_file)
        self.cache: dict[str, dict[str, str]] = self._load()

    def _load(self) -> dict[str, dict[str, str]]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load geocache from {self.cache_file}: {e}")
        return {}

    def save(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"Failed to save geocache to {self.cache_file}: {exc}")

    def reverse_geocode(
        self,
        lat: float,
        lon: float,
        delay: float = DEFAULT_NOMINATIM_DELAY,
    ) -> tuple[str, str, str, str]:
        """Reverse geocodes (lat, lon) to (street, city, state, country)."""
        cache_key = f"rev:{lat:.5f},{lon:.5f}"
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            return entry.get("street", ""), entry.get("city", ""), entry.get("state", ""), entry.get("country", "")

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": str(lat), "lon": str(lon), "format": "jsonv2", "addressdetails": "1"}

        try:
            time.sleep(delay)
            resp = requests.get(url, headers=NOMINATIM_HEADERS, params=params, timeout=10)
            if resp.status_code == 200:
                addr = resp.json().get("address", {})
                road = addr.get("road") or addr.get("pedestrian") or ""
                house = addr.get("house_number", "")
                street = f"{house} {road}".strip() if road else ""
                city = (
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("municipality")
                    or addr.get("village")
                    or addr.get("county")
                    or ""
                )
                state = addr.get("state") or addr.get("province") or addr.get("region") or ""
                country = addr.get("country", "")

                self.cache[cache_key] = {"street": street, "city": city, "state": state, "country": country}
                return street, city, state, country
        except Exception as exc:
            logger.warning(f"Nominatim reverse geocode failed for ({lat}, {lon}): {exc}")

        return "", "", "", ""

    def forward_geocode(
        self,
        query: str,
        delay: float = DEFAULT_NOMINATIM_DELAY,
    ) -> tuple[float | None, float | None, str, str, str, str]:
        """Forward geocodes query string to (lat, lon, street, city, state, country)."""
        clean_q = query.strip()
        if not clean_q:
            return None, None, "", "", "", ""

        cache_key = f"fwd:{clean_q.lower()}"
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            lat = float(entry["lat"]) if entry.get("lat") else None
            lon = float(entry["lon"]) if entry.get("lon") else None
            return (
                lat,
                lon,
                entry.get("street", ""),
                entry.get("city", ""),
                entry.get("state", ""),
                entry.get("country", ""),
            )

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": clean_q, "format": "jsonv2", "addressdetails": "1", "limit": "1"}

        try:
            time.sleep(delay)
            resp = requests.get(url, headers=NOMINATIM_HEADERS, params=params, timeout=10)
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    r0 = results[0]
                    lat = round(float(r0["lat"]), 6)
                    lon = round(float(r0["lon"]), 6)
                    addr = r0.get("address", {})
                    road = addr.get("road") or addr.get("pedestrian") or ""
                    house = addr.get("house_number", "")
                    street = f"{house} {road}".strip() if road else ""
                    city = (
                        addr.get("city")
                        or addr.get("town")
                        or addr.get("municipality")
                        or addr.get("village")
                        or addr.get("county")
                        or ""
                    )
                    state = addr.get("state") or addr.get("province") or addr.get("region") or ""
                    country = addr.get("country", "")

                    self.cache[cache_key] = {
                        "lat": str(lat),
                        "lon": str(lon),
                        "street": street,
                        "city": city,
                        "state": state,
                        "country": country,
                    }
                    return lat, lon, street, city, state, country
        except Exception as exc:
            logger.warning(f"Nominatim forward geocode failed for query '{query}': {exc}")

        return None, None, "", "", "", ""


def write_standard_csv(
    output_path: Path | str,
    records: list[dict[str, Any]],
    fieldnames: Sequence[str] = STANDARD_CSV_COLUMNS,
) -> Path:
    """Writes standardized POI dictionaries to CSV with UTF-8 BOM encoding for Excel/Vistarae import."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Handle file locking gracefully
    try:
        f_out = open(target, "w", newline="", encoding="utf-8-sig")
    except PermissionError:
        fallback = target.with_name(f"{target.stem}_clean{target.suffix}")
        print(
            f"Warning: '{target.name}' is open/locked by another application. Writing to '{fallback.name}' instead.",
            file=sys.stderr,
        )
        target = fallback
        f_out = open(target, "w", newline="", encoding="utf-8-sig")

    with f_out as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    return target
