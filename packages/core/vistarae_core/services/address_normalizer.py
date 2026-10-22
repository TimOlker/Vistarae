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
from typing import Final

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

        # US State Check
        if norm_country in ("United States", "") and lookup_key in US_STATE_MAPPINGS:
            return US_STATE_MAPPINGS[lookup_key]

        # Canadian Province Check
        if norm_country in ("Canada", "") and lookup_key in CA_PROVINCE_MAPPINGS:
            return CA_PROVINCE_MAPPINGS[lookup_key]

        # Australian State Check
        if norm_country in ("Australia", "") and lookup_key in AU_STATE_MAPPINGS:
            return AU_STATE_MAPPINGS[lookup_key]

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
        clean_city = record.city.strip() if record.city else None
        clean_street = record.street.strip() if record.street else None
        clean_postal = record.postal_code.strip() if record.postal_code else None

        return AddressRecord(
            street=clean_street if clean_street else None,
            city=_title_case_english(clean_city) if clean_city else None,
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
