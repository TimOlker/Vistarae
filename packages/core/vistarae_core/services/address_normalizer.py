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

# ── Inverted Mapping: Standard English Name -> ISO 3166-1 alpha-2 Code ────────
COUNTRY_TO_ISO: Final[dict[str, str]] = {
    country: code.upper()
    for code, country in COUNTRY_MAPPINGS.items()
    if len(code) == 2 and code.isalpha()
}
# Canonical overrides for official ISO 3166-1 alpha-2
COUNTRY_TO_ISO["United Kingdom"] = "GB"

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
        norm = cls.normalize_country(country)
        if norm in COUNTRY_TO_ISO:
            return COUNTRY_TO_ISO[norm]
        cleaned = country.strip().upper()
        if len(cleaned) == 2 and cleaned.isalpha():
            return cleaned
        return "XX"

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
    def normalize_address(cls, record: AddressRecord) -> AddressRecord:
        """Normalizes an AddressRecord value object's country, state, city, and street.

        Args:
            record: Raw input AddressRecord.

        Returns:
            New AddressRecord with standard English normalized values.
        """
        norm_country = cls.normalize_country(record.country)
        norm_state = cls.normalize_state_province(record.state_province, country=norm_country)
        clean_city = cls.strip_leading_glyphs(record.city) if record.city else None
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
