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

"""Unit tests for multi-format POI parser, header mapping, and quality flags."""

import pytest
from fastapi import HTTPException

from app.services.poi_parser import (
    build_header_mapping,
    detect_format,
    extract_raw_records,
    standardize_poi_candidates,
)


def test_detect_format():
    assert detect_format("name,latitude,longitude\nGrand Canyon,36.0,-112.0") == "csv"
    assert detect_format("name\tlat\tlng\nGrand Canyon\t36.0\t-112.0") == "tsv"
    assert detect_format('[{"name": "Zion"}]') == "json"
    assert detect_format('{"type": "FeatureCollection", "features": []}') == "geojson"
    assert detect_format("<kml><Placemark><name>Arches</name></Placemark></kml>") == "kml"
    assert detect_format('<gpx><wpt lat="38.5" lon="-109.5"><name>Moab</name></wpt></gpx>') == "gpx"


def test_build_header_mapping():
    headers = ["Park Name", "LAT_DEG", "Longitude", "City", "State/Province", "Web Link", "Tags"]
    mapping = build_header_mapping(headers)
    assert mapping["Park Name"] == "name"
    assert mapping["LAT_DEG"] == "latitude"
    assert mapping["Longitude"] == "longitude"
    assert mapping["City"] == "city"
    assert mapping["State/Province"] == "state"
    assert mapping["Web Link"] == "website_official"
    assert mapping["Tags"] == "category_tags"


def test_parse_csv_with_complete_fields():
    content = """name,latitude,longitude,city,state,tags,description,visit_again
Yosemite National Park,37.85,-119.57,Yosemite Village,California,NPS;nature,Iconic granite cliffs,true
Zion National Park,37.30,-113.05,Springdale,Utah,NPS;canyons,Red rock wonderland,false
"""
    raw_records, headers, fmt = extract_raw_records(content, filename="parks.csv")
    assert fmt == "csv"
    assert len(raw_records) == 2

    candidates, mappings = standardize_poi_candidates(
        raw_records,
        headers,
        default_tags=["national park"],
        filename="parks.csv",
        detected_format=fmt,
    )
    assert len(candidates) == 2

    # Yosemite
    yosemite = candidates[0]
    assert yosemite.name == "Yosemite National Park"
    assert yosemite.source_url == "parks.csv"
    assert yosemite.latitude == 37.85
    assert yosemite.longitude == -119.57
    assert yosemite.iptc_city == "Yosemite Village"
    assert yosemite.iptc_province_state == "California"
    assert yosemite.visit_again is True
    assert "NPS" in yosemite.category_tags
    assert "national park" in yosemite.category_tags
    assert yosemite.quality.is_valid is True
    assert yosemite.quality.has_name is True
    assert yosemite.quality.has_coordinates is True
    assert yosemite.quality.has_address is True
    assert len(yosemite.quality.flags) == 0

    # Zion
    zion = candidates[1]
    assert zion.name == "Zion National Park"
    assert zion.visit_again is False


def test_parse_missing_name_header_raises_422():
    content = """lat,long,description,city
37.85,-119.57,Some place without name column,Yosemite
"""
    raw_records, headers, _ = extract_raw_records(content)
    with pytest.raises(HTTPException) as exc_info:
        standardize_poi_candidates(raw_records, headers)
    assert exc_info.value.status_code == 422
    assert "Missing required field" in exc_info.value.detail


def test_parse_missing_coordinates_and_address_flags():
    content = """Site Title,Address,Description
Obscure Overlook,123 Ridge Rd,Just an address without coordinates
Ghost Point,,No address and no coordinates
"""
    raw_records, headers, _ = extract_raw_records(content)
    candidates, _ = standardize_poi_candidates(raw_records, headers)

    assert len(candidates) == 2

    # Row 1: has address, missing coordinates
    r1 = candidates[0]
    assert r1.name == "Obscure Overlook"
    assert r1.quality.has_coordinates is False
    assert "missing_coordinates" in r1.quality.flags
    assert r1.quality.has_address is True

    # Row 2: missing both coordinates and address
    r2 = candidates[1]
    assert r2.name == "Ghost Point"
    assert r2.quality.has_coordinates is False
    assert r2.quality.has_address is False
    assert "missing_coordinates" in r2.quality.flags
    assert "missing_address" in r2.quality.flags


def test_parse_geojson_feature_collection():
    geojson_str = """{
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "geometry": {
            "type": "Point",
            "coordinates": [-112.14, 36.06]
          },
          "properties": {
            "title": "Grand Canyon South Rim",
            "city": "Grand Canyon Village",
            "state": "Arizona",
            "website": "https://nps.gov/grca"
          }
        }
      ]
    }"""
    raw_records, headers, fmt = extract_raw_records(geojson_str)
    assert fmt == "geojson"
    assert len(raw_records) == 1
    candidates, _ = standardize_poi_candidates(raw_records, headers)
    assert len(candidates) == 1
    assert candidates[0].name == "Grand Canyon South Rim"
    assert candidates[0].latitude == 36.06
    assert candidates[0].longitude == -112.14
    assert candidates[0].website_official == "https://nps.gov/grca"


def test_parse_kml():
    kml_str = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <Placemark>
          <name>Delicate Arch</name>
          <description>Famous free-standing arch in Arches National Park</description>
          <Point>
            <coordinates>-109.499,38.743,0</coordinates>
          </Point>
        </Placemark>
      </Document>
    </kml>
    """
    raw_records, headers, fmt = extract_raw_records(kml_str)
    assert fmt == "kml"
    assert len(raw_records) == 1
    candidates, _ = standardize_poi_candidates(raw_records, headers)
    assert candidates[0].name == "Delicate Arch"
    assert candidates[0].latitude == 38.743
    assert candidates[0].longitude == -109.499
    assert "Arches National Park" in candidates[0].description


def test_parse_gpx():
    gpx_str = """<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" creator="Vistarae">
      <wpt lat="44.428" lon="-110.588">
        <name>Old Faithful</name>
        <desc>Famous cone geyser in Yellowstone</desc>
        <type>geothermal</type>
      </wpt>
    </gpx>
    """
    raw_records, headers, fmt = extract_raw_records(gpx_str)
    assert fmt == "gpx"
    assert len(raw_records) == 1
    candidates, _ = standardize_poi_candidates(raw_records, headers)
    assert candidates[0].name == "Old Faithful"
    assert candidates[0].latitude == 44.428
    assert candidates[0].longitude == -110.588
    assert "geothermal" in candidates[0].category_tags


def test_parse_csv_with_country_and_multinational_unesco():
    content = """title,country,category
"Ancient and Primeval Beech Forests of the Carpathians and Other Regions of Europe","Albania,Austria,Belgium,Germany,Ukraine",Natural
"Qhapaq Ñan, Andean Road System","Argentina,Bolivia (Plurinational State of),Chile,Colombia,Ecuador,Peru",Cultural
"Eiffel Tower",France,Landmark
"""
    raw_records, headers, fmt = extract_raw_records(content, filename="unesco.csv")
    assert fmt == "csv"
    assert len(raw_records) == 3

    candidates, _ = standardize_poi_candidates(raw_records, headers)
    assert len(candidates) == 3

    # Beech forests: multinational European site
    beech = candidates[0]
    assert beech.name.startswith("Ancient and Primeval Beech Forests")
    assert beech.iptc_country_code == "AL"
    assert beech.raw_data["_allowed_country_codes"] == ["AL", "AT", "BE", "DE", "UA"]
    assert "Ukraine" in beech.iptc_world_region

    # Qhapaq Ñan: Andean South America
    qhapaq = candidates[1]
    assert "Qhapaq Ñan" in qhapaq.name
    assert qhapaq.iptc_country_code == "AR"
    assert "EC" in qhapaq.raw_data["_allowed_country_codes"]
    assert "PE" in qhapaq.raw_data["_allowed_country_codes"]

    # Eiffel Tower: single country France
    eiffel = candidates[2]
    assert eiffel.name == "Eiffel Tower"
    assert eiffel.iptc_country_code == "FR"
    assert eiffel.iptc_country_code != "US"
