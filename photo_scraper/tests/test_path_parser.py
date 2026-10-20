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

"""Unit tests for path parser."""

from pathlib import Path

from photo_scraper.core.path_parser import (
    add_skip_over,
    clean_folder_name,
    get_skip_over,
    is_path_excluded,
    is_probable_non_location,
    is_skip_folder,
    parse_directory_path,
    reset_skip_over,
)


def test_clean_folder_name():
    assert clean_folder_name("1-Beijing") == "Beijing"
    assert clean_folder_name("06 Auburn NY") == "Auburn NY"
    assert clean_folder_name("21 Camden ME") == "Camden ME"
    assert clean_folder_name("01_Eiffel_Tower") == "Eiffel Tower"
    assert clean_folder_name("2024-05-12 Paris") == "Paris"
    assert clean_folder_name("03 - Grand Canyon") == "Grand Canyon"
    assert clean_folder_name("Lippold") == "Lippold"
    assert clean_folder_name("Trip to China") == "China"
    assert clean_folder_name("2002 Trip to China") == "China"
    assert clean_folder_name("Vacation in Italy") == "Italy"


def test_is_path_excluded():
    patterns = ["*Kids*", "*iPhone*", "*Personal*"]

    assert is_path_excluded(Path("M:/Photos/master/Tim/Kids/Soccer"), patterns) is True
    assert is_path_excluded(Path("M:/Photos/master/Tim/My_iPhone_Photos"), patterns) is True
    assert is_path_excluded(Path("M:/Photos/master/Tim/Personal/Taxes"), patterns) is True
    assert is_path_excluded(Path("M:/Photos/master/Tim/2018/China/1-Beijing"), patterns) is False
    assert is_path_excluded(Path("M:/Photos/master/Tim/2022/Lippold"), patterns) is False


def test_is_probable_non_location():
    assert is_probable_non_location("Sophia 6th Grade Choir") is True
    assert is_probable_non_location("Christmas 2021") is True
    assert is_probable_non_location("Birthday Party") is True
    assert is_probable_non_location("Receipts") is True
    assert is_probable_non_location("Behai Temple") is False
    assert is_probable_non_location("Charminar") is False
    assert is_probable_non_location("Harriet Tubman NHP") is False
    assert is_probable_non_location("Mount Battie") is False


def test_skip_over_registry():
    reset_skip_over()
    assert is_skip_folder("2d") is True
    assert is_skip_folder("3d") is True
    assert is_skip_folder("raw") is True
    assert is_skip_folder("RAW") is True
    assert is_skip_folder("Beijing") is False

    add_skip_over("gopro, drone_footage")
    assert is_skip_folder("gopro") is True
    assert is_skip_folder("drone_footage") is True
    assert "gopro" in get_skip_over()

    reset_skip_over()
    assert is_skip_folder("gopro") is False


def test_user_examples_path_hierarchy_extraction():
    """Tests the exact 7 user-provided hierarchy examples."""
    root = Path("M:/Photos/master/Tim")

    # 1. Behai Temple in Beijing, China
    p1 = Path("M:/Photos/master/Tim/2002/Trip to China/1-Beijing/Behai Temple")
    ctx1 = parse_directory_path(p1, root)
    assert ctx1.country == "China"
    assert ctx1.city == "Beijing"
    assert ctx1.site == "Behai Temple"
    assert ctx1.summary() == "Country=China, City=Beijing, Site=Behai Temple"
    assert ctx1.to_dict() == {
        "country": "China",
        "state": "",
        "city": "Beijing",
        "site": "Behai Temple",
    }

    # 2. Summer Palace in Beijing, China
    p2 = Path("M:/Photos/master/Tim/2002/Trip to China/1-Beijing/Summer Palace")
    ctx2 = parse_directory_path(p2, root)
    assert ctx2.country == "China"
    assert ctx2.city == "Beijing"
    assert ctx2.site == "Summer Palace"
    assert ctx2.summary() == "Country=China, City=Beijing, Site=Summer Palace"

    # 3. Master of Nets Garden in Suzhou, China
    p3 = Path("M:/Photos/master/Tim/2002/Trip to China/6-Suzhou/Master of Nets Garden")
    ctx3 = parse_directory_path(p3, root)
    assert ctx3.country == "China"
    assert ctx3.city == "Suzhou"
    assert ctx3.site == "Master of Nets Garden"
    assert ctx3.summary() == "Country=China, City=Suzhou, Site=Master of Nets Garden"

    # 4. Pullman National Monument (Chicago, IL, USA)
    p4 = Path("M:/Photos/master/Tim/2025/Pullman National Monument")
    ctx4 = parse_directory_path(p4, root)
    assert ctx4.country == "USA"
    assert ctx4.city == "Chicago"
    assert ctx4.site == "Pullman National Monument"
    assert "Country=USA" in ctx4.summary()
    assert "City=Chicago" in ctx4.summary()
    assert "Site=Pullman National Monument" in ctx4.summary()

    # 5. Dean Village in Edinburgh, Scotland (with '2d' intermediate skip over)
    p5 = Path("M:/Photos/master/Tim/2025/Great Britain/2d/01 Edinburgh/Dean Village")
    ctx5 = parse_directory_path(p5, root)
    assert ctx5.country == "Scotland"
    assert ctx5.city == "Edinburgh"
    assert ctx5.site == "Dean Village"
    assert ctx5.summary() == "Country=Scotland, City=Edinburgh, Site=Dean Village"

    # 6. Caerphilly Castle in Wales (with '2d' intermediate skip over)
    p6 = Path("M:/Photos/master/Tim/2025/Great Britain/2d/04 Wales/Caerphilly Castle")
    ctx6 = parse_directory_path(p6, root)
    assert ctx6.country == "Wales"
    assert ctx6.city == "Caerphilly"
    assert ctx6.site == "Caerphilly Castle"
    assert ctx6.summary() == "Country=Wales, City=Caerphilly, Site=Caerphilly Castle"

    # 7. Big Ben in London, England (with '2d' intermediate skip over)
    p7 = Path("M:/Photos/master/Tim/2025/Great Britain/2d/07 London/Big Ben")
    ctx7 = parse_directory_path(p7, root)
    assert ctx7.country == "England"
    assert ctx7.city == "London"
    assert ctx7.site == "Big Ben"
    assert ctx7.summary() == "Country=England, City=London, Site=Big Ben"


def test_parse_directory_path_hierarchical_us_states():
    root = Path("M:/Photos/master/Tim")

    # Harriet Tubman NHP in Auburn NY
    p2 = Path("M:/Photos/master/Tim/2019/New York/06 Auburn NY/Harriet Tubman NHP")
    ctx2 = parse_directory_path(p2, root)
    assert ctx2.site == "Harriet Tubman NHP"
    assert ctx2.country == "USA"
    assert ctx2.state == "NY"
    assert ctx2.city == "Auburn"

    # Mount Battie in Camden ME
    p3 = Path("M:/Photos/master/Tim/Maine/21 Camden ME/Mount Battie")
    ctx3 = parse_directory_path(p3, root)
    assert ctx3.site == "Mount Battie"
    assert ctx3.country == "USA"
    assert ctx3.state == "ME"
    assert ctx3.city == "Camden"

    # Lippold with no state context (resolves to Batavia, IL via Chicagoland landmark fallback)
    p4 = Path("M:/Photos/master/Tim/2022/Lippold")
    ctx4 = parse_directory_path(p4, root)
    assert ctx4.site == "Lippold"
    assert ctx4.country == "USA"
    assert ctx4.city == "Batavia"
    assert ctx4.state == "IL"
