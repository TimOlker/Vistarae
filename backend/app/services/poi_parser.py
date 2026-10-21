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

"""Universal multi-format parser for POI bulk ingestion with intelligent header mapping and quality evaluation."""

import csv
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.schemas.ingestion import IngestionDataQuality, StandardizedCandidatePOI
from app.services.countries import parse_country_input

logger = logging.getLogger("vistarae.poi_parser")

# Standard synonyms mapped to canonical fields
FIELD_SYNONYMS: dict[str, list[str]] = {
    "name": [
        "name",
        "title",
        "sitename",
        "site_name",
        "place",
        "placename",
        "place_name",
        "poi",
        "poi_name",
        "label",
        "unitname",
        "unit_name",
        "parkname",
        "park_name",
        "namefull",
        "name_full",
        "featurename",
        "feature_name",
        "wptname",
        "wpt_name",
        "placemarkname",
        "placemark_name",
        "location_name",
        "destination",
    ],
    "latitude": [
        "latitude",
        "lat",
        "y",
        "latdeg",
        "lat_deg",
        "latitudedeg",
        "latitude_deg",
        "coordlat",
        "coord_lat",
        "coordinateslat",
        "coordinates_lat",
        "ycoord",
        "y_coord",
        "pointlatitude",
        "point_latitude",
        "latitude_degrees",
    ],
    "longitude": [
        "longitude",
        "long",
        "lng",
        "lon",
        "x",
        "londeg",
        "lon_deg",
        "longitudedeg",
        "longitude_deg",
        "coordlon",
        "coord_lon",
        "coordinateslon",
        "coordinates_lon",
        "xcoord",
        "x_coord",
        "pointlongitude",
        "point_longitude",
        "longitude_degrees",
    ],
    "coordinates": [
        "coordinates",
        "coords",
        "coord",
        "latlng",
        "lat_lng",
        "latlon",
        "lat_lon",
        "position",
        "point",
        "geolocation",
    ],
    "sublocation": [
        "sublocation",
        "street",
        "streetaddress",
        "street_address",
        "address",
        "addressline",
        "address_line",
        "addr",
        "locationaddress",
        "location_address",
    ],
    "city": ["city", "town", "municipality", "locality", "cityname", "city_name"],
    "state": [
        "state",
        "province",
        "region",
        "stateprovince",
        "state_province",
        "adminarea",
        "admin_area",
        "statecode",
        "state_code",
        "prefecture",
        "canton",
    ],
    "country_code": [
        "countrycode",
        "country_code",
        "isocountry",
        "iso_country",
        "cc",
        "countryalpha2",
        "country_alpha2",
        "iso2",
        "iso_3166",
    ],
    "country": ["country", "countryname", "country_name", "nation"],
    "zip_code": ["zip", "zipcode", "zip_code", "postalcode", "postal_code", "postcode"],
    "category_tags": [
        "tags",
        "tag",
        "category",
        "categories",
        "categorytags",
        "category_tags",
        "keywords",
        "designation",
        "type",
        "types",
        "labels",
        "topics",
    ],
    "poi_type": ["poitype", "poi_type", "typeofplace", "type_of_place", "placetype", "place_type"],
    "description": [
        "description",
        "desc",
        "summary",
        "notes",
        "highlights",
        "details",
        "abstract",
        "comment",
        "overview",
        "info",
        "body",
    ],
    "website_official": [
        "website",
        "url",
        "officialwebsite",
        "official_website",
        "link",
        "web",
        "homepage",
        "siteurl",
        "site_url",
        "websiteofficial",
        "website_official",
        "uri",
    ],
    "phone_number": [
        "phone",
        "telephone",
        "contact",
        "phonenumber",
        "phone_number",
        "tel",
        "mobile",
    ],
    "personal_rating": [
        "rating",
        "stars",
        "personalrating",
        "personal_rating",
        "score",
        "user_rating",
    ],
    "visited": ["visited", "hasvisited", "has_visited", "isvisited", "is_visited", "statusvisited"],
    "visit_date": ["visitdate", "visit_date", "datevisited", "date_visited", "visiteddate"],
    "visit_again": [
        "visitagain",
        "visit_again",
        "wanttovisitagain",
        "want_to_visit_again",
        "revisit",
        "would_return",
    ],
    "source_url": ["sourceurl", "source_url", "source_file", "sourcefile", "source", "source_name"],
}


def normalize_header(header: str) -> str:
    """Strips non-alphanumeric characters, converts to lowercase, and trims."""
    return re.sub(r"[^a-zA-Z0-9]", "", header.strip().lower())


def build_header_mapping(headers: list[str]) -> dict[str, str]:
    """Maps actual input headers to standardized schema field names."""
    mapping: dict[str, str] = {}
    normalized_synonyms = {
        std_field: {normalize_header(syn) for syn in syn_list}
        for std_field, syn_list in FIELD_SYNONYMS.items()
    }

    # Match each header against synonyms
    for header in headers:
        norm_h = normalize_header(header)
        if not norm_h:
            continue
        matched = False
        for std_field, syn_set in normalized_synonyms.items():
            if norm_h in syn_set:
                mapping[header] = std_field
                matched = True
                break
        if not matched:
            # Fallback substring checks for compound headers (e.g., "site_name_en")
            for std_field, syn_set in normalized_synonyms.items():
                if any(syn in norm_h for syn in syn_set if len(syn) >= 4):
                    mapping[header] = std_field
                    break

    return mapping


def detect_format(content: str, filename: str | None = None, hint: str | None = None) -> str:
    """Infers data format: csv, tsv, json, geojson, kml, gpx, or xml."""
    if hint:
        hint_clean = hint.strip().lower()
        if hint_clean in ("csv", "tsv", "json", "geojson", "kml", "gpx", "xml"):
            return hint_clean

    if filename:
        fn_lower = filename.strip().lower()
        for ext in ("geojson", "json", "kml", "gpx", "csv", "tsv", "xml"):
            if fn_lower.endswith(f".{ext}"):
                return ext

    sample = content.strip()[:2000].lower()

    if "<kml" in sample or "<placemark" in sample:
        return "kml"
    if "<gpx" in sample or "<wpt" in sample:
        return "gpx"
    if sample.startswith("<?xml") or (
        "<" in sample
        and ">" in sample
        and not sample.startswith("{")
        and not sample.startswith("[")
    ):
        return "xml"

    if sample.startswith("{") or sample.startswith("["):
        try:
            parsed = json.loads(content[:10000]) if len(content) > 10000 else json.loads(content)
            if isinstance(parsed, dict) and parsed.get("type") == "FeatureCollection":
                return "geojson"
            return "json"
        except Exception:
            pass

    # Sniff delimiter for CSV / TSV
    first_lines = [line for line in content.splitlines()[:5] if line.strip()]
    if first_lines:
        first_line = first_lines[0]
        tab_count = first_line.count("\t")
        comma_count = first_line.count(",")
        semicolon_count = first_line.count(";")
        if tab_count > comma_count and tab_count > semicolon_count:
            return "tsv"
        if semicolon_count > comma_count:
            return "csv"

    return "csv"


def fix_mojibake(text: str) -> str:
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


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    s = fix_mojibake(s)
    return s if s else None


def _clean_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Handle coordinates with N/S/E/W or degree symbols
    s = re.sub(r"[°º'\"NSEWnsew\s]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _clean_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("true", "1", "yes", "t", "y")


def _clean_tags(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    # String delimited by comma, semicolon, or pipe
    items = re.split(r"[,;|]+", str(val))
    return [item.strip() for item in items if item.strip()]


def parse_csv_tsv_records(
    content: str, delimiter: str = ","
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parses tabular CSV or TSV content into list of row dictionaries."""
    # Strip UTF-8 BOM if present
    if content.startswith("\ufeff"):
        content = content[1:]

    # Remove blank lines
    f = io.StringIO(content.strip())
    reader = csv.reader(f, delimiter=delimiter)
    try:
        header_row = next(reader)
    except StopIteration:
        return [], []

    headers = [h.strip() for h in header_row if h.strip()]
    if not headers:
        return [], []

    rows: list[dict[str, Any]] = []
    for row in reader:
        if not row or not any(field.strip() for field in row):
            continue
        row_dict: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            if idx < len(row):
                row_dict[header] = row[idx].strip()
            else:
                row_dict[header] = ""
        rows.append(row_dict)

    return rows, headers


def parse_json_records(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parses JSON or GeoJSON content into list of flat attribute dictionaries."""
    data = json.loads(content)
    rows: list[dict[str, Any]] = []

    # Case 1: GeoJSON FeatureCollection
    if isinstance(data, dict) and data.get("type") == "FeatureCollection" and "features" in data:
        for feature in data.get("features", []):
            props = dict(feature.get("properties") or {})
            geometry = feature.get("geometry") or {}
            if geometry.get("type") == "Point" and "coordinates" in geometry:
                coords = geometry["coordinates"]
                if len(coords) >= 2:
                    props["longitude"] = coords[0]
                    props["latitude"] = coords[1]
            rows.append(props)
    # Case 2: Dict containing list in known wrapper keys
    elif isinstance(data, dict):
        wrapper_keys = (
            "pois",
            "places",
            "items",
            "records",
            "results",
            "data",
            "features",
            "sites",
        )
        found_list = None
        for key in wrapper_keys:
            if key in data and isinstance(data[key], list):
                found_list = data[key]
                break
        if found_list is not None:
            for item in found_list:
                if isinstance(item, dict):
                    rows.append(item)
        else:
            # Single object
            rows.append(data)
    # Case 3: Direct array of items
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append(item)

    # Collect all unique headers/keys found
    headers_set: set[str] = set()
    for row in rows:
        headers_set.update(str(k) for k in row)

    return rows, sorted(headers_set)


def parse_kml_records(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parses KML content extracting Placemark nodes."""
    # Strip XML namespace prefixes if needed for simple XPath
    clean_xml = re.sub(r'\sxmlns="[^"]+"', "", content, count=1)
    root = ET.fromstring(clean_xml)

    rows: list[dict[str, Any]] = []
    # Find all Placemark elements
    for placemark in root.iter("Placemark"):
        row: dict[str, Any] = {}
        name_elem = placemark.find("name")
        if name_elem is not None and name_elem.text:
            row["name"] = name_elem.text.strip()

        desc_elem = placemark.find("description")
        if desc_elem is not None and desc_elem.text:
            row["description"] = desc_elem.text.strip()

        # Coordinates inside Point or LookAt
        coord_elem = placemark.find(".//coordinates")
        if coord_elem is not None and coord_elem.text:
            raw_coord = coord_elem.text.strip().split()
            if raw_coord:
                parts = raw_coord[0].split(",")
                if len(parts) >= 2:
                    row["longitude"] = parts[0].strip()
                    row["latitude"] = parts[1].strip()

        # Extract ExtendedData / Data
        for data_elem in placemark.iter("Data"):
            key = data_elem.attrib.get("name")
            val_elem = data_elem.find("value")
            if key and val_elem is not None and val_elem.text:
                row[key] = val_elem.text.strip()

        for simple_data in placemark.iter("SimpleData"):
            key = simple_data.attrib.get("name")
            if key and simple_data.text:
                row[key] = simple_data.text.strip()

        if row:
            rows.append(row)

    headers_set: set[str] = set()
    for row in rows:
        headers_set.update(row.keys())

    return rows, sorted(headers_set)


def parse_gpx_records(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parses GPX waypoints into dictionaries."""
    clean_xml = re.sub(r'\sxmlns="[^"]+"', "", content, count=1)
    root = ET.fromstring(clean_xml)

    rows: list[dict[str, Any]] = []
    for wpt in root.iter("wpt"):
        row: dict[str, Any] = {}
        if "lat" in wpt.attrib:
            row["latitude"] = wpt.attrib["lat"]
        if "lon" in wpt.attrib:
            row["longitude"] = wpt.attrib["lon"]

        name_elem = wpt.find("name")
        if name_elem is not None and name_elem.text:
            row["name"] = name_elem.text.strip()

        desc_elem = wpt.find("desc")
        if desc_elem is None:
            desc_elem = wpt.find("cmt")
        if desc_elem is not None and desc_elem.text:
            row["description"] = desc_elem.text.strip()

        type_elem = wpt.find("type")
        if type_elem is not None and type_elem.text:
            row["category_tags"] = type_elem.text.strip()

        link_elem = wpt.find("link")
        if link_elem is not None and "href" in link_elem.attrib:
            row["website_official"] = link_elem.attrib["href"]

        if row:
            rows.append(row)

    headers_set: set[str] = set()
    for row in rows:
        headers_set.update(row.keys())

    return rows, sorted(headers_set)


def parse_generic_xml_records(content: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Fallback XML parser for arbitrary hierarchical POI lists."""
    clean_xml = re.sub(r'\sxmlns="[^"]+"', "", content, count=1)
    root = ET.fromstring(clean_xml)

    rows: list[dict[str, Any]] = []
    # Identify repeated child tags under root or sub-root
    children = list(root)
    if children:
        for child in children:
            row: dict[str, Any] = {}
            for attr_k, attr_v in child.attrib.items():
                row[attr_k] = attr_v
            for sub in child:
                tag_name = sub.tag.split("}")[-1]  # Strip any remaining namespace
                if sub.text and sub.text.strip():
                    row[tag_name] = sub.text.strip()
                elif sub.attrib:
                    row.update(sub.attrib)
            if row:
                rows.append(row)

    headers_set: set[str] = set()
    for row in rows:
        headers_set.update(row.keys())

    return rows, sorted(headers_set)


def extract_raw_records(
    content: str, filename: str | None = None, format_hint: str | None = None
) -> tuple[list[dict[str, Any]], list[str], str]:
    """Detects format and parses content into raw dict records, headers, and detected format."""
    fmt = detect_format(content, filename, format_hint)
    rows: list[dict[str, Any]] = []
    headers: list[str] = []

    if fmt == "csv":
        rows, headers = parse_csv_tsv_records(content, delimiter=",")
    elif fmt == "tsv":
        rows, headers = parse_csv_tsv_records(content, delimiter="\t")
    elif fmt in ("json", "geojson"):
        rows, headers = parse_json_records(content)
    elif fmt == "kml":
        rows, headers = parse_kml_records(content)
    elif fmt == "gpx":
        rows, headers = parse_gpx_records(content)
    elif fmt == "xml":
        # Check if actually KML or GPX inside generic XML tag
        if "<placemark" in content.lower():
            fmt = "kml"
            rows, headers = parse_kml_records(content)
        elif "<wpt" in content.lower():
            fmt = "gpx"
            rows, headers = parse_gpx_records(content)
        else:
            rows, headers = parse_generic_xml_records(content)
    else:
        # Default try CSV
        rows, headers = parse_csv_tsv_records(content, delimiter=",")

    return rows, headers, fmt


def standardize_poi_candidates(
    raw_records: list[dict[str, Any]],
    headers: list[str],
    default_tags: list[str] | None = None,
    filename: str | None = None,
    detected_format: str | None = None,
) -> tuple[list[StandardizedCandidatePOI], dict[str, str]]:
    """Maps raw rows to standardized candidate POIs, validates required fields, and flags missing data."""
    if not raw_records:
        raise HTTPException(
            status_code=422,
            detail="The provided file or input contains no data rows or records.",
        )

    field_mapping = build_header_mapping(headers)
    is_csv = (detected_format == "csv") or (
        bool(filename and filename.strip().lower().endswith(".csv"))
    )
    clean_filename = Path(filename.strip()).name if filename and filename.strip() else None

    # Check if a mapping exists for the required 'name' field
    has_name_mapping = any(target == "name" for target in field_mapping.values())
    if not has_name_mapping:
        raise HTTPException(
            status_code=422,
            detail=(
                "Missing required field: The provided input does not contain a recognizable site name or title column "
                "(e.g., 'name', 'title', 'place', 'site_name'). Please ensure your data includes a column for site names."
            ),
        )

    default_tags_list = default_tags or []
    candidates: list[StandardizedCandidatePOI] = []

    for row in raw_records:
        mapped_dict: dict[str, Any] = {}
        for raw_k, raw_v in row.items():
            std_field = field_mapping.get(raw_k)
            if std_field:
                mapped_dict[std_field] = raw_v

        # Extract name
        name_val = _clean_str(mapped_dict.get("name"))

        # Extract coordinates
        lat_val = _clean_float(mapped_dict.get("latitude"))
        lng_val = _clean_float(mapped_dict.get("longitude"))

        # Check compound coordinates column (e.g., "38.68, -109.57")
        if (lat_val is None or lng_val is None) and "coordinates" in mapped_dict:
            coord_str = str(mapped_dict["coordinates"]).strip()
            parts = re.split(r"[,/ ]+", coord_str)
            if len(parts) >= 2:
                c1 = _clean_float(parts[0])
                c2 = _clean_float(parts[1])
                if c1 is not None and c2 is not None:
                    # Usually lat, lng
                    lat_val = c1
                    lng_val = c2

        # Extract address components
        sublocation_val = _clean_str(mapped_dict.get("sublocation"))
        city_val = _clean_str(mapped_dict.get("city"))
        state_val = _clean_str(mapped_dict.get("state"))
        country_raw = _clean_str(mapped_dict.get("country")) or _clean_str(
            mapped_dict.get("country_code")
        )
        country_code_val, allowed_country_codes = parse_country_input(country_raw)
        zip_code_val = _clean_str(mapped_dict.get("zip_code"))

        # Check if row has an explicit tags column
        has_tags_col = any(
            normalize_header(k) in ("tags", "tag", "categorytags", "category_tags")
            for k, v in row.items()
            if v is not None and str(v).strip()
        )

        # Category tags: prioritize explicit tags column over generic category if both exist
        raw_tags_val = None
        for k, v in row.items():
            if normalize_header(k) in ("tags", "tag", "categorytags", "category_tags"):
                raw_tags_val = v
                break
        if raw_tags_val is None:
            raw_tags_val = mapped_dict.get("category_tags")

        tags = _clean_tags(raw_tags_val)
        for dt in default_tags_list:
            if dt not in tags:
                tags.append(dt)

        # Meta
        desc_val = _clean_str(mapped_dict.get("description"))
        website_val = _clean_str(mapped_dict.get("website_official"))
        phone_val = _clean_str(mapped_dict.get("phone_number"))
        poi_type_val = _clean_str(mapped_dict.get("poi_type")) or "site to see"
        visited_val = _clean_bool(mapped_dict.get("visited"), default=False)
        visit_again_val = _clean_bool(mapped_dict.get("visit_again"), default=False)

        # Source URL: if importing by a CSV, save the CSV file name to the source URL field
        source_url_val = _clean_str(mapped_dict.get("source_url"))
        if is_csv:
            source_url_val = clean_filename or source_url_val or "import.csv"
        elif clean_filename and not source_url_val:
            source_url_val = clean_filename

        # Evaluate Data Quality & Missing Field Flags
        has_name = bool(name_val and name_val.strip())
        has_coords = bool(
            lat_val is not None and lng_val is not None and not (lat_val == 0.0 and lng_val == 0.0)
        )
        has_addr = bool(city_val or state_val or sublocation_val or country_code_val or country_raw)

        quality_flags: list[str] = []
        if not has_name:
            quality_flags.append("missing_name")
        if not has_coords:
            quality_flags.append("missing_coordinates")
        if not has_addr:
            quality_flags.append("missing_address")

        quality = IngestionDataQuality(
            is_valid=has_name,
            has_name=has_name,
            has_coordinates=has_coords,
            has_address=has_addr,
            geocoded_address=False,
            geocoded_coordinates=False,
            flags=quality_flags,
        )

        candidate = StandardizedCandidatePOI(
            name=name_val or "Untitled POI",
            poi_type=poi_type_val,
            personal_rating=3,
            description=desc_val,
            category_tags=tags,
            visited=visited_val,
            visit_again=visit_again_val,
            latitude=lat_val,
            longitude=lng_val,
            website_official=website_val,
            phone_number=phone_val,
            source_url=source_url_val,
            source_type="import",
            iptc_sublocation=sublocation_val,
            iptc_city=city_val,
            iptc_province_state=state_val,
            iptc_country_code=country_code_val,
            iptc_world_region=country_raw or None,
            iptc_zip_code=zip_code_val,
            quality=quality,
            raw_data=dict(row),
        )
        if allowed_country_codes:
            candidate.raw_data["_allowed_country_codes"] = allowed_country_codes
        if has_tags_col:
            candidate.raw_data["_has_tags_col"] = True
        candidates.append(candidate)

    return candidates, field_mapping
