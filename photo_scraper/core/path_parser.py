"""Path parser for extracting location names and geographic hierarchy from folder paths."""

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

# Standard 2-letter US State codes
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}

# Full US State Names mapping to 2-letter codes
US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC"
}

# Default intermediate technical/camera folders to skip over during ancestor traversal
DEFAULT_SKIP_OVER = {
    "2d", "3d", "raw", "dcim", "edited", "export", "exports",
    "selected", "favorites", "jpg", "jpeg", "hdr", "master"
}

# Active skip over set (can be extended via add_skip_over)
_ACTIVE_SKIP_OVER: set[str] = set(DEFAULT_SKIP_OVER)


def add_skip_over(folders: str | list[str] | set[str]) -> None:
    """Adds folder names to the active skip-over registry."""
    if isinstance(folders, str):
        items = [f.strip().lower() for f in folders.split(",") if f.strip()]
    else:
        items = [str(f).strip().lower() for f in folders if str(f).strip()]
    _ACTIVE_SKIP_OVER.update(items)


def get_skip_over() -> set[str]:
    """Returns a copy of the active skip-over set."""
    return set(_ACTIVE_SKIP_OVER)


def reset_skip_over() -> None:
    """Resets the active skip-over set to defaults."""
    global _ACTIVE_SKIP_OVER
    _ACTIVE_SKIP_OVER = set(DEFAULT_SKIP_OVER)


def is_skip_folder(name: str, custom_skip: set[str] | list[str] | None = None) -> bool:
    """Checks if a folder name matches skip-over criteria (e.g. 2d, 3d, raw)."""
    norm = name.strip().lower()
    if not norm:
        return False
    active = _ACTIVE_SKIP_OVER
    if custom_skip:
        active = active | {str(s).strip().lower() for s in custom_skip if str(s).strip()}
    if norm in active:
        return True
    # Match short format tags like 2d, 3d, 4k
    return bool(re.match(r"^\d{1,2}[a-z]{1,3}$", norm))


# UK Constituent Countries and City mapping
UK_CONSTITUENT_COUNTRIES = {"scotland": "Scotland", "wales": "Wales", "england": "England", "northern ireland": "Northern Ireland"}
UK_OVERARCHING = {"great britain", "united kingdom", "uk", "britain"}

UK_CITY_TO_COUNTRY = {
    # Scotland
    "edinburgh": "Scotland", "glasgow": "Scotland", "aberdeen": "Scotland", "inverness": "Scotland",
    "dundee": "Scotland", "stirling": "Scotland", "perth": "Scotland", "st andrews": "Scotland",
    "skye": "Scotland", "isle of skye": "Scotland", "falkirk": "Scotland", "oban": "Scotland",
    # Wales
    "cardiff": "Wales", "swansea": "Wales", "newport": "Wales", "caerphilly": "Wales",
    "conwy": "Wales", "bangor": "Wales", "st davids": "Wales", "wrexham": "Wales",
    "tenby": "Wales", "llandudno": "Wales", "snowdonia": "Wales",
    # England
    "london": "England", "bath": "England", "oxford": "England", "cambridge": "England",
    "york": "England", "manchester": "England", "liverpool": "England", "bristol": "England",
    "birmingham": "England", "newcastle": "England", "leeds": "England", "brighton": "England",
    "windsor": "England", "salisbury": "England", "cotswolds": "England", "cornwall": "England",
    # Northern Ireland
    "belfast": "Northern Ireland", "derry": "Northern Ireland", "londonderry": "Northern Ireland",
}

# Known Countries
KNOWN_COUNTRIES = {
    "china": "China", "usa": "USA", "united states": "USA", "united states of america": "USA",
    "japan": "Japan", "france": "France", "italy": "Italy", "germany": "Germany",
    "spain": "Spain", "canada": "Canada", "mexico": "Mexico", "india": "India",
    "australia": "Australia", "new zealand": "New Zealand", "ireland": "Ireland",
    "switzerland": "Switzerland", "austria": "Austria", "netherlands": "Netherlands",
    "belgium": "Belgium", "norway": "Norway", "sweden": "Sweden", "denmark": "Denmark",
    "greece": "Greece", "portugal": "Portugal", "egypt": "Egypt", "brazil": "Brazil",
    "thailand": "Thailand", "vietnam": "Vietnam", "singapore": "Singapore",
    "south korea": "South Korea", "taiwan": "Taiwan", "turkey": "Turkey",
    "croatia": "Croatia", "iceland": "Iceland", "peru": "Peru", "chile": "Chile",
    "argentina": "Argentina", "south africa": "South Africa"
}

# Known Chicagoland / Local landmarks fallback mapping
KNOWN_LANDMARKS = {
    "pullman national monument": {"city": "Chicago", "state": "IL", "country": "USA"},
    "pullman": {"city": "Chicago", "state": "IL", "country": "USA"},
    "lippold": {"city": "Batavia", "state": "IL", "country": "USA"},
    "lippold park": {"city": "Batavia", "state": "IL", "country": "USA"},
    "cantigny": {"city": "Wheaton", "state": "IL", "country": "USA"},
    "cantigny park": {"city": "Wheaton", "state": "IL", "country": "USA"},
    "starved rock": {"city": "Oglesby", "state": "IL", "country": "USA"},
    "starved rock state park": {"city": "Oglesby", "state": "IL", "country": "USA"},
    "millennium park": {"city": "Chicago", "state": "IL", "country": "USA"},
    "navy pier": {"city": "Chicago", "state": "IL", "country": "USA"},
    "willis tower": {"city": "Chicago", "state": "IL", "country": "USA"},
    "art institute of chicago": {"city": "Chicago", "state": "IL", "country": "USA"},
    "garfield park conservatory": {"city": "Chicago", "state": "IL", "country": "USA"},
}

# Landmark suffixes used for extracting city names from site names
LANDMARK_SUFFIXES = [
    "National Monument", "National Park", "State Park", "National Historical Park",
    "NHP", "NHS", "Castle", "Palace", "Temple", "Cathedral", "Church",
    "Tower", "Bridge", "Museum", "Monument", "Park", "Gardens", "Garden",
    "Abbey", "Fort", "Square", "Market", "Memorial"
]

# Regex to strip leading numbers, dashes, underscores, dates
# e.g., "1-Beijing" -> "Beijing", "06 Auburn NY" -> "Auburn NY", "01_Eiffel Tower" -> "Eiffel Tower"
LEADING_PREFIX_REGEX = re.compile(r"^(\d{1,4}[-_\s]+)+", re.IGNORECASE)

# Regex to strip trip/vacation prefixes
# e.g., "Trip to China" -> "China", "2002 Trip to China" -> "China", "Vacation in Italy" -> "Italy"
TRIP_PREFIX_REGEX = re.compile(
    r"^(?:(?:19|20)\d{2}\s+)?(?:trip\s+(?:to|in|-)\s+|tour\s+of\s+|vacation\s+(?:to|in)\s+|visit\s+to\s+|travels?\s+(?:to|in)\s+)",
    re.IGNORECASE
)

# Regex to detect state at end of string e.g. "Auburn NY" -> ("Auburn", "NY")
CITY_STATE_REGEX = re.compile(r"^(.*?)[,\s]+([A-Z]{2})$", re.IGNORECASE)

# Known non-location noise patterns
NON_LOCATION_WORDS = {
    "choir", "recital", "birthday", "christmas", "thanksgiving", "easter",
    "halloween", "party", "reunion", "wedding", "portrait", "portraits",
    "scans", "receipts", "documents", "misc", "miscellaneous", "random",
    "iphone", "android", "photos", "pictures", "camera", "backup",
    "screenshot", "screenshots", "dcim", "whatsapp", "lightroom",
    "thumbnails", "export", "exports", "taxes", "finances", "bills",
    "walk", "day", "vacation", "trip"
}


@dataclass
class ParsedLocationContext:
    """Location information parsed from a directory path hierarchy."""

    folder_path: Path
    leaf_name: str
    cleaned_name: str
    ancestor_context: list[str]
    country: str | None = None
    state: str | None = None
    city: str | None = None
    site: str = ""
    detected_state: str | None = None
    combined_query: str = ""
    is_likely_non_location: bool = False

    def to_dict(self) -> dict[str, str]:
        """Returns standard dictionary mapping country, state, city, and site."""
        return {
            "country": self.country or "",
            "state": self.state or "",
            "city": self.city or "",
            "site": self.site or self.cleaned_name or "",
        }

    def summary(self) -> str:
        """Returns standard string summary e.g. 'Country=China, City=Beijing, Site=Behai Temple'."""
        parts = []
        if self.country:
            parts.append(f"Country={self.country}")
        if self.state:
            parts.append(f"State={self.state}")
        if self.city:
            parts.append(f"City={self.city}")
        parts.append(f"Site={self.site or self.cleaned_name}")
        return ", ".join(parts)


def is_path_excluded(path: Path, exclusion_patterns: list[str]) -> bool:
    """Checks if any component of the path or the full path matches exclusion patterns."""
    path_str = str(path).replace("\\", "/")
    parts = [p.lower() for p in path.parts]

    for pattern in exclusion_patterns:
        pat = pattern.strip().lower()
        if not pat:
            continue
        if fnmatch.fnmatch(path_str.lower(), pat):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pat):
                return True
    return False


def clean_folder_name(name: str) -> str:
    """Cleans numeric prefixes, trip prefixes, dates, and delimiters from a folder name."""
    name = name.strip()
    # Strip leading numbers/dates like '06 ', '1-', '01 '
    name = LEADING_PREFIX_REGEX.sub("", name).strip()
    # Strip trip/vacation prefixes like 'Trip to China' -> 'China'
    name = TRIP_PREFIX_REGEX.sub("", name).strip()
    # Replace underscores with spaces
    name = name.replace("_", " ").strip()
    return name


def is_probable_non_location(name: str) -> bool:
    """Detects event/personal folder names that are not travel/geographical places."""
    lower = name.lower()
    words = re.findall(r"\b\w+\b", lower)
    for word in words:
        if word in NON_LOCATION_WORDS:
            return True
    return bool(re.match(r"^[\d\W]+$", name))


def _extract_city_from_site(site: str) -> str | None:
    """Extracts candidate city prefix from landmark names like 'Caerphilly Castle' -> 'Caerphilly'."""
    for suffix in LANDMARK_SUFFIXES:
        pattern = rf"^(.*?)\s+{re.escape(suffix)}$"
        match = re.match(pattern, site, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate and len(candidate) > 2 and not is_probable_non_location(candidate):
                return candidate
    return None


def parse_directory_path(
    folder_path: Path,
    root_path: Path | None = None,
    skip_over: set[str] | list[str] | None = None,
) -> ParsedLocationContext:
    """Extracts country, state, city, and site from directory path hierarchy.

    Supports:
        - Skipping over intermediate folders like '2d', '3d', 'RAW'
        - Cleaning trip prefixes ('Trip to China' -> 'China')
        - UK Constituent countries ('04 Wales', '01 Edinburgh' in 'Great Britain')
        - City and State detection ('06 Auburn NY')
        - Known landmark and metropolitan fallback ('Pullman National Monument' -> Chicago, IL, USA)
    """
    leaf_raw = folder_path.name
    cleaned_leaf = clean_folder_name(leaf_raw)
    site = cleaned_leaf

    is_non_loc = is_probable_non_location(cleaned_leaf)

    # Walk ancestors between folder_path and root_path (up to 6 levels to account for skip folders)
    ancestors: list[str] = []
    current = folder_path.parent
    depth = 0

    while current and current != current.parent and depth < 6:
        if root_path and (current == root_path or current in root_path.parents):
            break

        c_name = current.name

        # Skip intermediate technical/camera folders (e.g. 2d, 3d, raw)
        if is_skip_folder(c_name, skip_over):
            current = current.parent
            continue

        cleaned_ancestor = clean_folder_name(c_name)

        # Skip pure year folders like "2002", "2025" and noise folders
        if not re.match(r"^(19|20)\d{2}$", cleaned_ancestor) and not is_probable_non_location(cleaned_ancestor):
            ancestors.append(cleaned_ancestor)

        depth += 1
        current = current.parent

    country: str | None = None
    state: str | None = None
    city: str | None = None

    # 1. Inspect ancestors for UK overarching context ("Great Britain", "UK")
    has_uk_overarching = any(anc.lower() in UK_OVERARCHING for anc in ancestors)

    # 2. Check for UK Constituent countries in ancestors (Scotland, Wales, England, Northern Ireland)
    for anc in ancestors:
        anc_lower = anc.lower()
        if anc_lower in UK_CONSTITUENT_COUNTRIES:
            country = UK_CONSTITUENT_COUNTRIES[anc_lower]
            break

    # 3. Check for Known Countries in ancestors
    if not country:
        for anc in ancestors:
            anc_lower = anc.lower()
            if anc_lower in KNOWN_COUNTRIES:
                country = KNOWN_COUNTRIES[anc_lower]
                break

    # 4. Check for US States in ancestors or leaf
    # 4a. Check full US state names in ancestors
    for anc in ancestors:
        anc_lower = anc.lower()
        if anc_lower in US_STATE_NAMES:
            state = US_STATE_NAMES[anc_lower]
            country = "USA"
            break

    # 4b. Check "City ST" pattern in leaf
    state_match = CITY_STATE_REGEX.match(cleaned_leaf)
    if state_match:
        cand_city = state_match.group(1).strip()
        cand_state = state_match.group(2).upper()
        if cand_state in US_STATE_CODES:
            state = cand_state
            country = "USA"
            if cand_city:
                city = cand_city

    # 4c. Check "City ST" pattern in ancestors
    if not state or not city:
        for anc in ancestors:
            sm = CITY_STATE_REGEX.match(anc)
            if sm and sm.group(2).upper() in US_STATE_CODES:
                if not state:
                    state = sm.group(2).upper()
                if not country:
                    country = "USA"
                if not city and sm.group(1).strip():
                    city = sm.group(1).strip()
                break

    # 5. Extract City from ancestors
    if not city:
        for anc in ancestors:
            anc_lower = anc.lower()
            # Skip if this ancestor is the country, UK overarching, or a state
            if anc_lower in UK_OVERARCHING or anc_lower in UK_CONSTITUENT_COUNTRIES or anc_lower in KNOWN_COUNTRIES:
                continue
            if anc_lower in US_STATE_NAMES or anc.upper() in US_STATE_CODES:
                continue
            # Also check if this ancestor is a known UK city
            if anc_lower in UK_CITY_TO_COUNTRY:
                city = anc.title()
                if has_uk_overarching or not country:
                    country = UK_CITY_TO_COUNTRY[anc_lower]
                break
            # Otherwise, this non-country ancestor under country is our city candidate
            city = anc
            break

    # 6. If in UK and city known, assign constituent country if not yet set
    if city and city.lower() in UK_CITY_TO_COUNTRY and (has_uk_overarching or not country):
        country = UK_CITY_TO_COUNTRY[city.lower()]

    # 7. If country is set (e.g. Wales) but city is not, try extracting city from site name
    if country and not city:
        extracted = _extract_city_from_site(site)
        if extracted:
            city = extracted

    # 8. Check Known Chicagoland / US landmark fallbacks if country/city are still unset
    site_lower = site.lower()
    if (not country or country == "USA") and site_lower in KNOWN_LANDMARKS:
        lm = KNOWN_LANDMARKS[site_lower]
        country = lm.get("country", country or "USA")
        state = lm.get("state", state)
        city = lm.get("city", city)

    # 9. Build combined search query for geocoding
    query_parts: list[str] = [site]
    if city and city.lower() not in site.lower():
        query_parts.append(city)
    if state and state not in query_parts:
        query_parts.append(state)
    if country and country not in query_parts:
        query_parts.append(country)

    # If query parts only has site, also append any non-redundant ancestor names
    if len(query_parts) == 1:
        for anc in ancestors:
            if anc.lower() not in site.lower() and anc not in query_parts:
                query_parts.append(anc)

    combined_query = ", ".join(query_parts)

    return ParsedLocationContext(
        folder_path=folder_path,
        leaf_name=leaf_raw,
        cleaned_name=cleaned_leaf,
        ancestor_context=ancestors,
        country=country,
        state=state,
        city=city,
        site=site,
        detected_state=state,
        combined_query=combined_query,
        is_likely_non_location=is_non_loc,
    )
