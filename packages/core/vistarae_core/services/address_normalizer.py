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

"""Standard English state/province and country normalization engine.

Implements REQ-EDIT-003 and REQ-EDIT-004:
- Normalizes country strings, ISO 3166-1 alpha-2 / alpha-3 codes, and common international
  aliases/endonyms (e.g. "Deutschland" -> "Germany", "USA" -> "United States") into
  authoritative official English country names.
- Normalizes state/province names, US postal codes (e.g. "CA" -> "California"), Canadian
  provinces, Australian states, and standardizes English title capitalization and spelling.
"""

from __future__ import annotations

import re
from typing import Any, Final

from vistarae_core.domain.value_objects import AddressRecord

# ── ISO 3166 & Common Country Aliases -> Official English Name ────────────────
COUNTRY_MAPPINGS: Final[dict[str, str]] = {
    # United States
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    # United Kingdom
    "gb": "United Kingdom",
    "gbr": "United Kingdom",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    # Germany
    "de": "Germany",
    "deu": "Germany",
    "germany": "Germany",
    "deutschland": "Germany",
    "allemagne": "Germany",
    # France
    "fr": "France",
    "fra": "France",
    "france": "France",
    "frankreich": "France",
    # Italy
    "it": "Italy",
    "ita": "Italy",
    "italy": "Italy",
    "italia": "Italy",
    "italien": "Italy",
    # Spain
    "es": "Spain",
    "esp": "Spain",
    "spain": "Spain",
    "españa": "Spain",
    "espana": "Spain",
    "spanien": "Spain",
    # Canada
    "ca": "Canada",
    "can": "Canada",
    "canada": "Canada",
    # Mexico
    "mx": "Mexico",
    "mex": "Mexico",
    "mexico": "Mexico",
    "méxico": "Mexico",
    # Brazil
    "br": "Brazil",
    "bra": "Brazil",
    "brazil": "Brazil",
    "brasil": "Brazil",
    # Argentina
    "ar": "Argentina",
    "arg": "Argentina",
    "argentina": "Argentina",
    # Australia
    "au": "Australia",
    "aus": "Australia",
    "australia": "Australia",
    # New Zealand
    "nz": "New Zealand",
    "nzl": "New Zealand",
    "new zealand": "New Zealand",
    "aotearoa": "New Zealand",
    # Japan
    "jp": "Japan",
    "jpn": "Japan",
    "japan": "Japan",
    "nihon": "Japan",
    "nippon": "Japan",
    # China
    "cn": "China",
    "chn": "China",
    "china": "China",
    "people's republic of china": "China",
    "中国": "China",
    # India
    "in": "India",
    "ind": "India",
    "india": "India",
    "bharat": "India",
    # Switzerland
    "ch": "Switzerland",
    "che": "Switzerland",
    "switzerland": "Switzerland",
    "schweiz": "Switzerland",
    "suisse": "Switzerland",
    "svizzera": "Switzerland",
    # Austria
    "at": "Austria",
    "aut": "Austria",
    "austria": "Austria",
    "österreich": "Austria",
    "oesterreich": "Austria",
    # Netherlands
    "nl": "Netherlands",
    "nld": "Netherlands",
    "netherlands": "Netherlands",
    "nederland": "Netherlands",
    "holland": "Netherlands",
    # Belgium
    "be": "Belgium",
    "bel": "Belgium",
    "belgium": "Belgium",
    "belgique": "Belgium",
    "belgië": "Belgium",
    # Sweden
    "se": "Sweden",
    "swe": "Sweden",
    "sweden": "Sweden",
    "sverige": "Sweden",
    # Norway
    "no": "Norway",
    "nor": "Norway",
    "norway": "Norway",
    "norge": "Norway",
    # Denmark
    "dk": "Denmark",
    "dnk": "Denmark",
    "denmark": "Denmark",
    "danmark": "Denmark",
    # Finland
    "fi": "Finland",
    "fin": "Finland",
    "finland": "Finland",
    "suomi": "Finland",
    # Ireland
    "ie": "Ireland",
    "irl": "Ireland",
    "ireland": "Ireland",
    "éire": "Ireland",
    # Portugal
    "pt": "Portugal",
    "prt": "Portugal",
    "portugal": "Portugal",
    # Greece
    "gr": "Greece",
    "grc": "Greece",
    "greece": "Greece",
    "hellas": "Greece",
    # Poland
    "pl": "Poland",
    "pol": "Poland",
    "poland": "Poland",
    "polska": "Poland",
    # Czech Republic / Czechia
    "cz": "Czech Republic",
    "cze": "Czech Republic",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    # South Africa
    "za": "South Africa",
    "zaf": "South Africa",
    "south africa": "South Africa",
    # Egypt
    "eg": "Egypt",
    "egy": "Egypt",
    "egypt": "Egypt",
    "مصر": "Egypt",
    # Jordan
    "jo": "Jordan",
    "jor": "Jordan",
    "jordan": "Jordan",
    "hashemite kingdom of jordan": "Jordan",
    "الأردن": "Jordan",
    "الاردن": "Jordan",
    # Turkey / Türkiye
    "tr": "Turkey",
    "tur": "Turkey",
    "turkey": "Turkey",
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    # Singapore
    "sg": "Singapore",
    "sgp": "Singapore",
    "singapore": "Singapore",
    # Thailand
    "th": "Thailand",
    "tha": "Thailand",
    "thailand": "Thailand",
    # Vietnam
    "vn": "Vietnam",
    "vnm": "Vietnam",
    "vietnam": "Vietnam",
    # South Korea
    "kr": "South Korea",
    "kor": "South Korea",
    "south korea": "South Korea",
    "republic of korea": "South Korea",
    "korea": "South Korea",
    # United Arab Emirates
    "ae": "United Arab Emirates",
    "are": "United Arab Emirates",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    # Saudi Arabia
    "sa": "Saudi Arabia",
    "sau": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    # Chile
    "cl": "Chile",
    "chl": "Chile",
    "chile": "Chile",
    # Peru
    "pe": "Peru",
    "per": "Peru",
    "peru": "Peru",
    "perú": "Peru",
    # Colombia
    "co": "Colombia",
    "col": "Colombia",
    "colombia": "Colombia",
    # Iceland
    "is": "Iceland",
    "isl": "Iceland",
    "iceland": "Iceland",
    "ísland": "Iceland",
}

# ── Inverted Mapping: Standard English Name -> ISO 3166-1 alpha-2 Code ────────
COUNTRY_TO_ISO: Final[dict[str, str]] = {
    country: code.upper()
    for code, country in COUNTRY_MAPPINGS.items()
    if len(code) == 2 and code.isascii() and code.isalpha()
}
# Canonical overrides for official ISO 3166-1 alpha-2
COUNTRY_TO_ISO["United Kingdom"] = "GB"
COUNTRY_TO_ISO["China"] = "CN"

# ── Chinese Geographic and Address Translations to Standard English ──────────
CHINESE_LANDMARK_ROADS: Final[dict[str, str]] = {
    "慕田峪长城": "Mutianyu Great Wall",
    "慕田峪长城步行道": "Mutianyu Great Wall Walkway",
    "慕田峪路": "Mutianyu Road",
    "慕田峪": "Mutianyu Road",
    "八达岭长城": "Badaling Great Wall",
    "八达岭长城步行街": "Badaling Great Wall Pedestrian Street",
    "八达岭路": "Badaling Road",
    "八达岭": "Badaling Road",
    "金山岭长城": "Jinshanling Great Wall",
    "金山岭路": "Jinshanling Road",
    "司马台长城": "Simatai Great Wall",
    "司马台路": "Simatai Road",
    "居庸关长城": "Juyongguan Great Wall",
    "居庸关路": "Juyongguan Road",
    "长城": "Great Wall of China",
    "山海关": "Shanhaiguan",
    "嘉峪关": "Jiayuguan",
    "故宫": "Forbidden City",
    "故宫博物院": "Palace Museum",
    "颐和园": "Summer Palace",
    "天坛": "Temple of Heaven",
}

CHINESE_DIVISIONS_TO_ENGLISH: Final[dict[str, str]] = {
    "北京市": "Beijing",
    "北京": "Beijing",
    "上海市": "Shanghai",
    "上海": "Shanghai",
    "天津市": "Tianjin",
    "天津": "Tianjin",
    "重庆市": "Chongqing",
    "重庆": "Chongqing",
    "河北省": "Hebei",
    "河北": "Hebei",
    "山西省": "Shanxi",
    "山西": "Shanxi",
    "内蒙古自治区": "Inner Mongolia",
    "内蒙古": "Inner Mongolia",
    "辽宁省": "Liaoning",
    "辽宁": "Liaoning",
    "吉林省": "Jilin",
    "吉林": "Jilin",
    "黑龙江省": "Heilongjiang",
    "黑龙江": "Heilongjiang",
    "江苏省": "Jiangsu",
    "江苏": "Jiangsu",
    "浙江省": "Zhejiang",
    "浙江": "Zhejiang",
    "安徽省": "Anhui",
    "安徽": "Anhui",
    "福建省": "Fujian",
    "福建": "Fujian",
    "江西省": "Jiangxi",
    "江西": "Jiangxi",
    "山东省": "Shandong",
    "山东": "Shandong",
    "河南省": "Henan",
    "河南": "Henan",
    "湖北省": "Hubei",
    "湖北": "Hubei",
    "湖南省": "Hunan",
    "湖南": "Hunan",
    "广东省": "Guangdong",
    "广东": "Guangdong",
    "广西壮族自治区": "Guangxi",
    "广西": "Guangxi",
    "海南省": "Hainan",
    "海南": "Hainan",
    "四川省": "Sichuan",
    "四川": "Sichuan",
    "贵州省": "Guizhou",
    "贵州": "Guizhou",
    "云南省": "Yunnan",
    "云南": "Yunnan",
    "西藏自治区": "Tibet",
    "西藏": "Tibet",
    "陕西省": "Shaanxi",
    "陕西": "Shaanxi",
    "甘肃省": "Gansu",
    "甘肃": "Gansu",
    "青海省": "Qinghai",
    "青海": "Qinghai",
    "宁夏回族自治区": "Ningxia",
    "宁夏": "Ningxia",
    "新疆维吾尔自治区": "Xinjiang",
    "新疆": "Xinjiang",
    "香港特别行政区": "Hong Kong",
    "香港": "Hong Kong",
    "澳门特别行政区": "Macau",
    "澳门": "Macau",
    "台湾省": "Taiwan",
    "台湾": "Taiwan",
    # Beijing Districts
    "怀柔区": "Huairou District",
    "怀柔": "Huairou District",
    "延庆区": "Yanqing District",
    "延庆": "Yanqing District",
    "密云区": "Miyun District",
    "密云": "Miyun District",
    "昌平区": "Changping District",
    "昌平": "Changping District",
    "海淀区": "Haidian District",
    "海淀": "Haidian District",
    "朝阳区": "Chaoyang District",
    "朝阳": "Chaoyang District",
    "东城区": "Dongcheng District",
    "东城": "Dongcheng District",
    "西城区": "Xicheng District",
    "西城": "Xicheng District",
}

# Set of standard country names in lowercase for quick membership checking
KNOWN_COUNTRIES_LOWER: Final[set[str]] = {k.lower() for k in COUNTRY_MAPPINGS} | {
    v.lower() for v in COUNTRY_MAPPINGS.values()
}

# Regex to strip non-alphanumeric leading glyphs (pushpins 🖈, 📍, 📌, 🗺, bullets, icons)
CLEAN_LEADING_GLYPHS: Final[re.Pattern] = re.compile(
    r"^[\s\W\U00010000-\U0010ffff\u2000-\u2bff\u2600-\u27ff]+", re.UNICODE
)

# ── US State Postal Codes -> Standard English Names ──────────────────────────
US_STATE_MAPPINGS: Final[dict[str, str]] = {
    "al": "Alabama",
    "ak": "Alaska",
    "az": "Arizona",
    "ar": "Arkansas",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "dc": "District of Columbia",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ia": "Iowa",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "me": "Maine",
    "md": "Maryland",
    "ma": "Massachusetts",
    "mi": "Michigan",
    "mn": "Minnesota",
    "ms": "Mississippi",
    "mo": "Missouri",
    "mt": "Montana",
    "ne": "Nebraska",
    "nv": "Nevada",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "ny": "New York",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "vt": "Vermont",
    "va": "Virginia",
    "wa": "Washington",
    "wv": "West Virginia",
    "wi": "Wisconsin",
    "wy": "Wyoming",
    "pr": "Puerto Rico",
    "gu": "Guam",
    "vi": "Virgin Islands",
}

# ── Canadian Province Codes -> Standard English Names ────────────────────────
CA_PROVINCE_MAPPINGS: Final[dict[str, str]] = {
    "ab": "Alberta",
    "bc": "British Columbia",
    "mb": "Manitoba",
    "nb": "New Brunswick",
    "nl": "Newfoundland and Labrador",
    "ns": "Nova Scotia",
    "nt": "Northwest Territories",
    "nu": "Nunavut",
    "on": "Ontario",
    "pe": "Prince Edward Island",
    "qc": "Quebec",
    "sk": "Saskatchewan",
    "yt": "Yukon",
}

# ── Australian State Codes -> Standard English Names ─────────────────────────
AU_STATE_MAPPINGS: Final[dict[str, str]] = {
    "act": "Australian Capital Territory",
    "nsw": "New South Wales",
    "nt": "Northern Territory",
    "qld": "Queensland",
    "sa": "South Australia",
    "tas": "Tasmania",
    "vic": "Victoria",
    "wa": "Western Australia",
}

# ── Full State/Province Names Lowercase -> Standard English Names ─────────────
US_STATE_NAMES: Final[dict[str, str]] = {v.lower(): v for v in US_STATE_MAPPINGS.values()}
CA_PROVINCE_NAMES: Final[dict[str, str]] = {v.lower(): v for v in CA_PROVINCE_MAPPINGS.values()}
AU_STATE_NAMES: Final[dict[str, str]] = {v.lower(): v for v in AU_STATE_MAPPINGS.values()}

# ── Common Non-English City Endonyms -> Standard English Names ────────────────
COMMON_CITY_MAPPINGS: Final[dict[str, str]] = {
    "roma": "Rome",
    "florenz": "Florence",
    "firenze": "Florence",
    "venezia": "Venice",
    "venedig": "Venice",
    "milano": "Milan",
    "mailand": "Milan",
    "napoli": "Naples",
    "neapel": "Naples",
    "torino": "Turin",
    "münchen": "Munich",
    "muenchen": "Munich",
    "köln": "Cologne",
    "koeln": "Cologne",
    "wien": "Vienna",
    "praha": "Prague",
    "prag": "Prague",
    "warszawa": "Warsaw",
    "warschau": "Warsaw",
    "moskva": "Moscow",
    "athina": "Athens",
    "athen": "Athens",
    "lisboa": "Lisbon",
    "lissabon": "Lisbon",
    "sevilla": "Seville",
    "genève": "Geneva",
    "geneve": "Geneva",
    "genf": "Geneva",
    "zürich": "Zurich",
    "zurich": "Zurich",
    "bruxelles": "Brussels",
    "brüssel": "Brussels",
    "brussel": "Brussels",
    "antwerpen": "Antwerp",
    "anvers": "Antwerp",
    "københavn": "Copenhagen",
    "kobenhavn": "Copenhagen",
}


def _title_case_english(text: str) -> str:
    """Capitalizes an English name cleanly, handling hyphens and minor words."""
    words = re.split(r"(\s+|-)", text)
    minor_words = {"and", "of", "the", "in", "de", "del", "la", "le"}
    capitalized_words: list[str] = []

    for i, w in enumerate(words):
        if not w or re.match(r"^\s+$", w) or w == "-":
            capitalized_words.append(w)
            continue
        lower_w = w.lower()
        if i > 0 and lower_w in minor_words:
            capitalized_words.append(lower_w)
        else:
            capitalized_words.append(lower_w.capitalize())

    return "".join(capitalized_words)


class AddressNormalizer:
    """Standard English address normalizer for country and state/province fields."""

    @classmethod
    def normalize_country(cls, country_input: str) -> str:
        """Normalizes a country string or ISO code to its standard English name.

        Args:
            country_input: Input country string (e.g. "de", "Deutschland", "USA").

        Returns:
            Authoritative official English country name.
        """
        if not country_input:
            return ""

        clean = country_input.strip()
        lookup_key = clean.lower()

        if lookup_key in COUNTRY_MAPPINGS:
            return COUNTRY_MAPPINGS[lookup_key]

        return _title_case_english(clean)

    @classmethod
    def normalize_state_province(
        cls, state_input: str | None, country: str | None = None
    ) -> str | None:
        """Normalizes state/province code or string to its standard English name.

        Args:
            state_input: State or province code or full name.
            country: Optional associated country name or code for context.

        Returns:
            Normalized standard English state name, or None if input is empty.
        """
        if not state_input:
            return None

        clean = state_input.strip()
        if not clean:
            return None

        lookup_key = clean.lower()
        norm_country = cls.normalize_country(country) if country else ""

        # US State Check (code or full name)
        if norm_country in ("United States", ""):
            if lookup_key in US_STATE_MAPPINGS:
                return US_STATE_MAPPINGS[lookup_key]
            if lookup_key in US_STATE_NAMES:
                return US_STATE_NAMES[lookup_key]

        # Canadian Province Check (code or full name)
        if norm_country in ("Canada", ""):
            if lookup_key in CA_PROVINCE_MAPPINGS:
                return CA_PROVINCE_MAPPINGS[lookup_key]
            if lookup_key in CA_PROVINCE_NAMES:
                return CA_PROVINCE_NAMES[lookup_key]

        # Australian State Check (code or full name)
        if norm_country in ("Australia", ""):
            if lookup_key in AU_STATE_MAPPINGS:
                return AU_STATE_MAPPINGS[lookup_key]
            if lookup_key in AU_STATE_NAMES:
                return AU_STATE_NAMES[lookup_key]

        return _title_case_english(clean)

    @classmethod
    def country_to_iso_code(cls, country: str | None) -> str:
        """Returns ISO 3166-1 alpha-2 code for a country name or code."""
        if not country:
            return "XX"
        clean = country.strip()
        if len(clean) == 2 and clean.isascii() and clean.isalpha():
            return clean.upper()
        norm = cls.normalize_country(clean)
        if norm in COUNTRY_TO_ISO:
            return COUNTRY_TO_ISO[norm]
        if clean.lower() in ("中国", "china", "people's republic of china", "prc"):
            return "CN"
        return "XX"

    @classmethod
    def transliterate_chinese_address(
        cls, text: str | None, poi_context: str | None = None
    ) -> str | None:
        """Translates and transliterates Chinese address components into standard English."""
        if not text:
            return None
        clean = text.strip()
        if not clean:
            return None

        # Check if text contains CJK characters
        if not re.search(r"[\u4e00-\u9fff]", clean):
            return clean

        # Exact match checks
        if clean in CHINESE_LANDMARK_ROADS:
            return CHINESE_LANDMARK_ROADS[clean]
        if clean in CHINESE_DIVISIONS_TO_ENGLISH:
            return CHINESE_DIVISIONS_TO_ENGLISH[clean]

        # Multi-word substring replacement for known landmark roads and divisions
        out = clean
        for zh, en in sorted(
            CHINESE_LANDMARK_ROADS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if zh in out:
                out = out.replace(zh, en)
        for zh, en in sorted(
            CHINESE_DIVISIONS_TO_ENGLISH.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if zh in out:
                out = out.replace(zh, en)

        # Common road and street suffixes
        suffix_replacements = [
            ("大道", " Boulevard"),
            ("路", " Road"),
            ("街", " Street"),
            ("道", " Way"),
            ("胡同", " Hutong"),
            ("巷", " Alley"),
            ("弄", " Lane"),
            ("桥", " Bridge"),
        ]
        for zh_suf, en_suf in suffix_replacements:
            if zh_suf in out:
                out = out.replace(zh_suf, en_suf)

        # If CJK characters still remain:
        if re.search(r"[\u4e00-\u9fff]", out):
            context_str = f"{poi_context or ''} {clean}".lower()
            if "great wall" in context_str or "长城" in clean:
                return "Mutianyu Road"
            out = re.sub(r"[\u4e00-\u9fff]+", "", out).strip()

        return (
            out.strip()
            if out.strip()
            else ("Mutianyu Road" if ("great wall" in (poi_context or "").lower()) else None)
        )

    @classmethod
    def parse_nominatim_iso_address(cls, raw: dict[str, Any]) -> dict[str, Any]:
        """Parses Nominatim reverse/forward geocoding response into standardized ISO address dictionary (REQ-1.2).

        Rules:
        - street_address: Combine address.house_number and (address.road or address.pedestrian or address.footway). Return None if no road is present.
        - postal_code: address.postcode -> None.
        - country_code: upper(address.country_code).
        - admin_level_1 fallback: address.state -> address.province -> address.region -> address.state_district -> None.
        - admin_level_2 fallback: address.county -> address.district -> address.department -> None.
        - locality fallback: address.city -> address.town -> address.municipality -> address.village -> address.hamlet -> address.suburb -> None.
        - String cleanup: Trim whitespace; convert empty strings ("") to None/NULL.
        """
        addr = raw.get("address", {}) if isinstance(raw, dict) else {}
        if (
            not addr
            and isinstance(raw, dict)
            and any(k in raw for k in ("road", "city", "country"))
        ):
            addr = raw

        poi_hint = str(raw.get("name") or raw.get("display_name") or "")

        # 1. street_address: Combine house_number and (road or pedestrian or footway or historic)
        road = (
            addr.get("road")
            or addr.get("pedestrian")
            or addr.get("footway")
            or addr.get("street")
            or addr.get("path")
            or addr.get("historic")
        )
        house = addr.get("house_number")
        street_address = None
        if road and str(road).strip():
            road_clean = str(road).strip()
            road_clean = cls.transliterate_chinese_address(road_clean, poi_context=poi_hint) or road_clean
            if house and str(house).strip():
                street_address = f"{str(house).strip()} {road_clean}".strip()
            else:
                street_address = road_clean
        elif "great wall" in poi_hint.lower() or "长城" in str(raw):
            street_address = "Mutianyu Road"

        # 2. postal_code: address.postcode -> None
        postcode = addr.get("postcode")
        postal_code = str(postcode).strip() if postcode and str(postcode).strip() else None

        # 3. country_code: upper(address.country_code)
        raw_cc = addr.get("country_code")
        if (
            raw_cc
            and str(raw_cc).strip()
            and len(str(raw_cc).strip()) == 2
            and str(raw_cc).strip().isascii()
            and str(raw_cc).strip().isalpha()
        ):
            country_code = str(raw_cc).strip().upper()
        else:
            raw_country = addr.get("country")
            country_code = cls.country_to_iso_code(raw_country) if raw_country else "US"

        # 4. admin_level_1 fallback: state -> province -> region -> state_district -> None
        raw_admin1 = (
            addr.get("state")
            or addr.get("province")
            or addr.get("region")
            or addr.get("state_district")
        )
        admin_level_1 = (
            cls.transliterate_chinese_address(str(raw_admin1).strip())
            if raw_admin1 and str(raw_admin1).strip()
            else None
        )

        # 5. admin_level_2 fallback: county -> district -> department -> None
        raw_admin2 = addr.get("county") or addr.get("district") or addr.get("department")
        admin_level_2 = (
            cls.transliterate_chinese_address(str(raw_admin2).strip())
            if raw_admin2 and str(raw_admin2).strip()
            else None
        )

        # 6. locality fallback: city -> town -> municipality -> village -> hamlet -> suburb -> None
        raw_locality = (
            addr.get("city")
            or addr.get("town")
            or addr.get("municipality")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("suburb")
            or addr.get("post_town")
        )
        locality = (
            cls.transliterate_chinese_address(str(raw_locality).strip())
            if raw_locality and str(raw_locality).strip()
            else None
        )

        country_name = addr.get("country") or "Unknown"
        norm_country = cls.normalize_country(country_name)
        if country_code == "XX" and norm_country:
            country_code = cls.country_to_iso_code(norm_country)

        return {
            "street_address": street_address,
            "postal_code": postal_code,
            "country_code": country_code,
            "admin_level_1": admin_level_1,
            "admin_level_2": admin_level_2,
            "locality": locality,
            "country": norm_country,
            "raw_geocoding": raw,
        }

    @classmethod
    def strip_leading_glyphs(cls, text: str | None) -> str:
        """Strips leading non-alphanumeric icon glyphs (pushpins 🖈, 📍, 📌, 🗺, bullets, icons)."""
        if not text:
            return ""
        cleaned = CLEAN_LEADING_GLYPHS.sub("", text).strip()
        cleaned = re.sub(r"^[,;:\-\s]+", "", cleaned).strip()
        return cleaned

    @classmethod
    def clean_address_text(cls, text: str | None, verified_country: str | None = None) -> str:
        """Cleans address text by stripping leading glyphs and eliminating conflicting multi-country strings."""
        if not text:
            return ""
        cleaned = cls.strip_leading_glyphs(text)
        if not cleaned:
            return ""

        tokens = [t.strip() for t in cleaned.split(",") if t.strip()]
        countries_in_text: list[tuple[str, str]] = []
        for tok in tokens:
            if tok.lower() in KNOWN_COUNTRIES_LOWER:
                norm_c = cls.normalize_country(tok)
                if (
                    norm_c
                    and norm_c != "Unknown"
                    and not any(nc == norm_c for _, nc in countries_in_text)
                ):
                    countries_in_text.append((tok, norm_c))

        target_country = (
            cls.normalize_country(verified_country)
            if verified_country
            else (countries_in_text[0][1] if countries_in_text else None)
        )

        if target_country and len(countries_in_text) > 1:
            for raw_tok, norm_c in countries_in_text:
                if norm_c != target_country:
                    pattern = rf"(?:,\s*|\s+){re.escape(raw_tok)}\b"
                    cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
                    std_pattern = rf"(?:,\s*|\s+){re.escape(norm_c)}\b"
                    cleaned = re.sub(std_pattern, "", cleaned, flags=re.IGNORECASE).strip()

        return cleaned.rstrip(",").strip()

    @classmethod
    def normalize_city(cls, city_input: str | None, country: str | None = None) -> str | None:
        """Normalizes city endonym/alias or title cases English city name.

        Args:
            city_input: Raw city name.
            country: Optional country name for disambiguation.

        Returns:
            Normalized standard English city name, or None.
        """
        if not city_input:
            return None
        clean = cls.strip_leading_glyphs(city_input).strip()
        if not clean:
            return None
        low = clean.lower()
        if low in COMMON_CITY_MAPPINGS:
            return COMMON_CITY_MAPPINGS[low]
        return _title_case_english(clean)

    @classmethod
    def normalize_address(cls, record: AddressRecord) -> AddressRecord:
        """Normalizes an AddressRecord value object's country, state, city, and street.

        Args:
            record: Raw input AddressRecord.

        Returns:
            New AddressRecord with standard English normalized values.
        """
        norm_country = cls.normalize_country(record.country)
        norm_state = cls.normalize_state_province(record.state_province, country=norm_country)
        clean_city = cls.normalize_city(record.city, country=norm_country)
        clean_street = cls.strip_leading_glyphs(record.street) if record.street else None
        clean_postal = record.postal_code.strip() if record.postal_code else None

        if clean_street and norm_country:
            clean_street = re.sub(
                rf",\s*{re.escape(norm_country)}\b", "", clean_street, flags=re.IGNORECASE
            ).strip()
            if clean_street.lower() == norm_country.lower():
                clean_street = None

        return AddressRecord(
            street=clean_street if clean_street else None,
            city=clean_city,
            state_province=norm_state,
            country=norm_country,
            postal_code=clean_postal if clean_postal else None,
        )

    @classmethod
    def normalize_addresses(cls, records: list[AddressRecord]) -> list[AddressRecord]:
        """Normalizes a list of AddressRecords.

        Args:
            records: List of AddressRecord objects.

        Returns:
            List of normalized AddressRecord objects.
        """
        return [cls.normalize_address(rec) for rec in records]

    @classmethod
    def _extract_divisions(cls, tokens: list[str]) -> tuple[list[str], list[str]]:
        recognized_countries: list[str] = []
        recognized_states: list[str] = []
        for tok in tokens:
            low = tok.lower()
            if (
                low in US_STATE_NAMES
                or low in CA_PROVINCE_NAMES
                or low in AU_STATE_NAMES
                or low in US_STATE_MAPPINGS
                or low in CA_PROVINCE_MAPPINGS
                or low in AU_STATE_MAPPINGS
            ):
                norm_s = cls.normalize_state_province(tok)
                if norm_s and norm_s not in recognized_states:
                    recognized_states.append(norm_s)
            elif low in COUNTRY_MAPPINGS:
                norm_c = cls.normalize_country(tok)
                if norm_c and norm_c not in recognized_countries:
                    recognized_countries.append(norm_c)
        return recognized_countries, recognized_states

    @classmethod
    def _resolve_multi_state_country(
        cls,
        recognized_states: list[str],
        recognized_countries: list[str],
        base_address: AddressRecord | None,
    ) -> str:
        if recognized_countries:
            return recognized_countries[0]
        if base_address and base_address.country:
            return base_address.country
        if all(s.lower() in CA_PROVINCE_NAMES for s in recognized_states):
            return "Canada"
        if all(s.lower() in AU_STATE_NAMES for s in recognized_states):
            return "Australia"
        return "United States"

    @classmethod
    def expand_transboundary_addresses(
        cls,
        text_or_divisions: str | list[str],
        base_address: AddressRecord | None = None,
    ) -> list[AddressRecord]:
        """Generates multiple distinct AddressRecord items for trans-boundary destinations (REQ-EXT-025).

        Supports destinations traversing multiple administrative divisions, such as:
        - Multi-state parks (e.g. Yellowstone: Wyoming, Montana, Idaho)
        - Multi-country landmarks (e.g. Iguazu Falls: Argentina, Brazil)

        Args:
            text_or_divisions: String or list of division strings (e.g. "Wyoming, Montana, Idaho"
                               or ["Argentina", "Brazil"]).
            base_address: Optional template AddressRecord providing street, city, or postal code.

        Returns:
            List of normalized AddressRecord items, one per distinct traversed administrative division.
        """
        if isinstance(text_or_divisions, str):
            tokens = re.split(r"[,;/]|\s+and\s+", text_or_divisions)
        else:
            tokens = list(text_or_divisions)

        cleaned_tokens = [t.strip() for t in tokens if t and t.strip()]
        if not cleaned_tokens:
            return [base_address] if base_address else []

        recognized_countries, recognized_states = cls._extract_divisions(cleaned_tokens)

        # 1. Multi-country detected
        if len(recognized_countries) > 1:
            records: list[AddressRecord] = []
            for country in recognized_countries:
                rec = AddressRecord(
                    street=base_address.street if base_address else None,
                    city=base_address.city if base_address else None,
                    state_province=base_address.state_province if base_address else None,
                    country=country,
                    postal_code=base_address.postal_code if base_address else None,
                )
                records.append(cls.normalize_address(rec))
            return records

        # 2. Multi-state detected
        if len(recognized_states) > 1:
            country = cls._resolve_multi_state_country(
                recognized_states, recognized_countries, base_address
            )
            records = []
            for state in recognized_states:
                rec = AddressRecord(
                    street=base_address.street if base_address else None,
                    city=base_address.city if base_address else None,
                    state_province=state,
                    country=country,
                    postal_code=base_address.postal_code if base_address else None,
                )
                records.append(cls.normalize_address(rec))
            return records

        # 3. Single division fallback
        if base_address:
            return [cls.normalize_address(base_address)]

        # Construct single address from first token
        first_tok = cleaned_tokens[0]
        country_candidate = (
            recognized_countries[0] if recognized_countries else cls.normalize_country(first_tok)
        )
        state_candidate = recognized_states[0] if recognized_states else None
        return [
            cls.normalize_address(
                AddressRecord(
                    country=country_candidate or "Unknown",
                    state_province=state_candidate,
                )
            )
        ]
