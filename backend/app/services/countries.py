"""ISO 3166-1 alpha-2 country lookup and normalization utility."""

import re

# Comprehensive mapping of country names, aliases, and common spelling variants to ISO 3166-1 alpha-2
COUNTRY_NAME_TO_ALPHA2: dict[str, str] = {
    # Popular & User Example Countries
    "china": "CN",
    "peoples republic of china": "CN",
    "people's republic of china": "CN",
    "prc": "CN",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "america": "US",
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "uk": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "canada": "CA",
    "mexico": "MX",
    "japan": "JP",
    "nippon": "JP",
    "nihon": "JP",
    "south korea": "KR",
    "korea": "KR",
    "republic of korea": "KR",
    "north korea": "KP",
    "taiwan": "TW",
    "hong kong": "HK",
    "macau": "MO",
    "macao": "MO",
    "france": "FR",
    "germany": "DE",
    "deutschland": "DE",
    "italy": "IT",
    "italia": "IT",
    "spain": "ES",
    "espana": "ES",
    "españa": "ES",
    "portugal": "PT",
    "switzerland": "CH",
    "schweiz": "CH",
    "suisse": "CH",
    "austria": "AT",
    "osterreich": "AT",
    "österreich": "AT",
    "netherlands": "NL",
    "holland": "NL",
    "belgium": "BE",
    "ireland": "IE",
    "republic of ireland": "IE",
    "iceland": "IS",
    "norway": "NO",
    "sweden": "SE",
    "finland": "FI",
    "denmark": "DK",
    "greece": "GR",
    "hellas": "GR",
    "turkey": "TR",
    "turkiye": "TR",
    "türkiye": "TR",
    "cyprus": "CY",
    "malta": "MT",
    "russia": "RU",
    "russian federation": "RU",
    "ukraine": "UA",
    "poland": "PL",
    "polska": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "slovakia": "SK",
    "slovak republic": "SK",
    "hungary": "HU",
    "romania": "RO",
    "bulgaria": "BG",
    "croatia": "HR",
    "slovenia": "SI",
    "serbia": "RS",
    "bosnia": "BA",
    "bosnia and herzegovina": "BA",
    "montenegro": "ME",
    "north macedonia": "MK",
    "macedonia": "MK",
    "albania": "AL",
    "estonia": "EE",
    "latvia": "LV",
    "lithuania": "LT",
    "belarus": "BY",
    "moldova": "MD",
    "georgia": "GE",
    "armenia": "AM",
    "azerbaijan": "AZ",
    "australia": "AU",
    "new zealand": "NZ",
    "fiji": "FJ",
    "papua new guinea": "PG",
    "argentina": "AR",
    "brazil": "BR",
    "brasil": "BR",
    "chile": "CL",
    "peru": "PE",
    "colombia": "CO",
    "ecuador": "EC",
    "bolivia": "BO",
    "paraguay": "PY",
    "uruguay": "UY",
    "venezuela": "VE",
    "guyana": "GY",
    "suriname": "SR",
    "costa rica": "CR",
    "panama": "PA",
    "guatemala": "GT",
    "belize": "BZ",
    "honduras": "HN",
    "el salvador": "SV",
    "nicaragua": "NI",
    "cuba": "CU",
    "bahamas": "BS",
    "jamaica": "JM",
    "haiti": "HT",
    "dominican republic": "DO",
    "puerto rico": "PR",
    "trinidad and tobago": "TT",
    "barbados": "BB",
    "saint lucia": "LC",
    "egypt": "EG",
    "morocco": "MA",
    "algeria": "DZ",
    "tunisia": "TN",
    "south africa": "ZA",
    "kenya": "KE",
    "tanzania": "TZ",
    "uganda": "UG",
    "rwanda": "RW",
    "ethiopia": "ET",
    "ghana": "GH",
    "nigeria": "NG",
    "senegal": "SN",
    "namibia": "NA",
    "botswana": "BW",
    "zimbabwe": "ZW",
    "zambia": "ZM",
    "madagascar": "MG",
    "mauritius": "MU",
    "seychelles": "SC",
    "israel": "IL",
    "jordan": "JO",
    "lebanon": "LB",
    "saudi arabia": "SA",
    "united arab emirates": "AE",
    "uae": "AE",
    "dubai": "AE",
    "qatar": "QA",
    "oman": "OM",
    "kuwait": "KW",
    "bahrain": "BH",
    "india": "IN",
    "pakistan": "PK",
    "bangladesh": "BD",
    "sri lanka": "LK",
    "nepal": "NP",
    "bhutan": "BT",
    "maldives": "MV",
    "thailand": "TH",
    "vietnam": "VN",
    "viet nam": "VN",
    "cambodia": "KH",
    "laos": "LA",
    "myanmar": "MM",
    "burma": "MM",
    "malaysia": "MY",
    "singapore": "SG",
    "indonesia": "ID",
    "philippines": "PH",
    "brunei": "BN",
    "mongolia": "MN",
    "kazakhstan": "KZ",
    "uzbekistan": "UZ",
    "kyrgyzstan": "KG",
    "tajikistan": "TJ",
    "turkmenistan": "TM",
    # Additional global and UNESCO-recognized countries & official variants
    "afghanistan": "AF",
    "andorra": "AD",
    "angola": "AO",
    "antigua and barbuda": "AG",
    "benin": "BJ",
    "burkina faso": "BF",
    "cabo verde": "CV",
    "cape verde": "CV",
    "cameroon": "CM",
    "central african republic": "CF",
    "chad": "TD",
    "comoros": "KM",
    "congo": "CG",
    "republic of the congo": "CG",
    "democratic republic of the congo": "CD",
    "dr congo": "CD",
    "drc": "CD",
    "cote d ivoire": "CI",
    "côte d ivoire": "CI",
    "ivory coast": "CI",
    "dominica": "DM",
    "eritrea": "ER",
    "gabon": "GA",
    "gambia": "GM",
    "the gambia": "GM",
    "guinea": "GN",
    "guinea bissau": "GW",
    "guinea-bissau": "GW",
    "holy see": "VA",
    "vatican": "VA",
    "vatican city": "VA",
    "iran": "IR",
    "iran islamic republic of": "IR",
    "islamic republic of iran": "IR",
    "iraq": "IQ",
    "kiribati": "KI",
    "laos": "LA",
    "lao people s democratic republic": "LA",
    "lao people's democratic republic": "LA",
    "lao pdr": "LA",
    "lesotho": "LS",
    "libya": "LY",
    "luxembourg": "LU",
    "malawi": "MW",
    "mali": "ML",
    "marshall islands": "MH",
    "mauritania": "MR",
    "micronesia": "FM",
    "micronesia federated states of": "FM",
    "federated states of micronesia": "FM",
    "mozambique": "MZ",
    "niger": "NE",
    "palau": "PW",
    "saint kitts and nevis": "KN",
    "san marino": "SM",
    "sao tome and principe": "ST",
    "são tomé and príncipe": "ST",
    "sierra leone": "SL",
    "solomon islands": "SB",
    "south sudan": "SS",
    "state of palestine": "PS",
    "palestine": "PS",
    "sudan": "SD",
    "syria": "SY",
    "syrian arab republic": "SY",
    "togo": "TG",
    "vanuatu": "VU",
    "yemen": "YE",
    "tanzania": "TZ",
    "tanzania united republic of": "TZ",
    "united republic of tanzania": "TZ",
    "venezuela": "VE",
    "venezuela bolivarian republic of": "VE",
    "bolivarian republic of venezuela": "VE",
    "bolivia": "BO",
    "bolivia plurinational state of": "BO",
    "plurinational state of bolivia": "BO",
    "moldova": "MD",
    "republic of moldova": "MD",
}

# Set of all valid 2-letter uppercase ISO country codes for instant validation
VALID_ALPHA2_CODES: set[str] = set(COUNTRY_NAME_TO_ALPHA2.values()) | {
    "AD", "AF", "AG", "AI", "AO", "AQ", "AS", "AW", "AX", "BI", "BJ", "BL", "BM", "BQ",
    "BV", "CC", "CD", "CF", "CG", "CI", "CK", "CM", "CV", "CW", "CX", "DJ", "DM", "EH",
    "ER", "FM", "FO", "GA", "GD", "GF", "GG", "GI", "GL", "GM", "GN", "GP", "GQ", "GS",
    "GU", "GW", "HM", "IM", "IO", "IQ", "IR", "JE", "KI", "KM", "KN", "KY", "LC", "LI",
    "LR", "LS", "LY", "MC", "MF", "MH", "ML", "MM", "MN", "MP", "MQ", "MR", "MS", "MU",
    "MV", "MW", "MZ", "NA", "NC", "NE", "NF", "NR", "NU", "PF", "PG", "PM", "PN", "PW",
    "RE", "SB", "SD", "SH", "SJ", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SX", "SY",
    "SZ", "TC", "TD", "TF", "TG", "TK", "TL", "TO", "TT", "TV", "TZ", "UG", "UM", "VA",
    "VC", "VG", "VI", "VU", "WF", "WS", "YE", "YT", "ZM", "ZW",
}


def normalize_country_key(text: str) -> str:
    """Normalizes text by lowercasing, decomposing accents, and stripping punctuation/extra whitespace."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s]", " ", cleaned.lower())
    return " ".join(cleaned.split())


def map_country_to_code(country_input: str | None) -> str | None:
    """Attempts to resolve a single country input string to its 2-letter ISO 3166-1 alpha-2 code.

    Examples:
        'China' -> 'CN'
        'china' -> 'CN'
        'CN'    -> 'CN'
        'cn'    -> 'CN'
        'United States' -> 'US'
        'Bolivia (Plurinational State of)' -> 'BO'
        'Unknown' -> None
    """
    if not country_input:
        return None

    raw = country_input.strip()
    if not raw:
        return None

    # 1. Normalized dictionary match (handles 'China', 'United States', and aliases like 'uk' -> 'GB')
    norm = normalize_country_key(raw)
    if norm in COUNTRY_NAME_TO_ALPHA2:
        return COUNTRY_NAME_TO_ALPHA2[norm]

    # 2. Direct 2-letter ISO check (if already a valid 2-letter code)
    if len(raw) == 2:
        code_upper = raw.upper()
        if code_upper in VALID_ALPHA2_CODES or code_upper.isalpha():
            return code_upper

    # 3. Match without parenthetical qualifiers (e.g., 'Bolivia (Plurinational State of)' -> 'Bolivia')
    raw_no_paren = re.sub(r"\([^)]*\)", "", raw).strip()
    if raw_no_paren and raw_no_paren != raw:
        norm_no_paren = normalize_country_key(raw_no_paren)
        if norm_no_paren in COUNTRY_NAME_TO_ALPHA2:
            return COUNTRY_NAME_TO_ALPHA2[norm_no_paren]

    # 4. Substring match fallback (e.g. "Republic of China", "Federation of Russia")
    for key, code in COUNTRY_NAME_TO_ALPHA2.items():
        if len(key) >= 4 and (norm == key or norm.startswith(f"{key} ") or norm.endswith(f" {key}")):
            return code

    return None


def parse_country_input(country_input: str | None) -> tuple[str | None, list[str]]:
    """Resolves a country input string to:
    1. Primary 2-letter ISO 3166-1 alpha-2 code (or None).
    2. List of all recognized 2-letter ISO codes (for multi-country / transnational sites).

    Handles single countries, full names, 2-letter codes, and comma/semicolon/slash delimited lists.
    Examples:
        'Albania,North Macedonia' -> ('AL', ['AL', 'MK'])
        'Argentina,Bolivia (Plurinational State of),Chile' -> ('AR', ['AR', 'BO', 'CL'])
        'Ecuador' -> ('EC', ['EC'])
        'US' -> ('US', ['US'])
    """
    if not country_input:
        return None, []

    raw = country_input.strip()
    if not raw:
        return None, []

    # If delimiters exist, split into constituent parts first
    if any(delim in raw for delim in (",", ";", "/")):
        parts = [p.strip() for p in re.split(r"[,;/]+", raw) if p.strip()]
        matched_codes: list[str] = []
        for part in parts:
            code = map_country_to_code(part)
            if code and code not in matched_codes:
                matched_codes.append(code)
        if matched_codes:
            return matched_codes[0], matched_codes

    # Otherwise, check as a single country string
    single_code = map_country_to_code(raw)
    if single_code:
        return single_code, [single_code]

    return None, []
